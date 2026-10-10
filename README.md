# Sauvegarde EBANISTA n8n

Sauvegarde automatique quotidienne (cron, tous les jours à 3h du matin, heure de Paris) de :
- `postgres_dumps/` — dump complet de la base Postgres n8n (contient les credentials, **chiffrés** avec la clé d'instance n8n)
- `workflows/` — export JSON de chaque workflow n8n (via l'API n8n)
- `docker-compose.yml` — configuration des services (secrets remplacés par des variables `${...}`, valeurs réelles **non présentes** dans ce dépôt)

## Restauration

1. Récupérer les vraies valeurs de secrets (mots de passe Postgres/n8n, clé de chiffrement n8n) depuis le gestionnaire de mots de passe — **elles ne sont pas dans ce dépôt**.
2. Créer un fichier `.env` à côté de `docker-compose.yml` avec :
   ```
   POSTGRES_PASSWORD=...
   N8N_BASIC_AUTH_PASSWORD=...
   ```
3. Avant de démarrer n8n, écrire la clé de chiffrement dans `~/.n8n/config` (volume `n8n_data`) au format :
   ```json
   {"encryptionKey": "..."}
   ```
   Sans cette clé, les credentials du dump Postgres (IMAP, SMTP, Telegram, Claude API) sont illisibles.
4. `docker compose up -d postgres`, attendre qu'il soit healthy.
5. Restaurer le dump le plus récent : `cat postgres_dumps/n8n_YYYY-MM-DD.sql | docker compose exec -T postgres psql -U n8n n8n`
6. `docker compose up -d n8n`
7. Vérifier dans l'UI n8n que les credentials et workflows sont bien présents et actifs.

Les fichiers `workflows/*.json` servent de sauvegarde secondaire lisible (re-import possible via l'UI n8n si le dump Postgres est indisponible), mais ne contiennent pas les credentials.

## Relais Telegram (assistant e-mails)

Le dossier `telegram-bridge/` contient `bridge.py` : un petit service qui récupère les messages du bot Telegram (long polling) et les transmet au workflow n8n « Assistant e-mails Telegram » par le réseau interne Docker. Rien n'est exposé sur Internet, et seul le compte Telegram autorisé est relayé.

**Les secrets ne sont PAS dans ce dépôt.** À recréer à la main sur le serveur :

1. `mkdir -p /root/telegram-bridge/data && chmod 700 /root/telegram-bridge` puis copier `bridge.py` dedans.
2. `/root/telegram-bridge/.env` (droits 600) :
   ```
   TELEGRAM_BOT_TOKEN=<jeton du bot, à redemander à @BotFather (/mybots)>
   ALLOWED_CHAT_ID=8848139246
   ```
3. `/root/telegram-bridge/secret.env` (droits 600) : `BRIDGE_SECRET=<même valeur que le credential n8n « Pont Telegram (secret) »>` (si besoin, recréer les deux avec une nouvelle valeur).
4. Lancer le conteneur (le chemin du webhook se lit dans le nœud « Webhook Telegram » du workflow) :
   ```
   docker run -d --name telegram-bridge --restart unless-stopped --network root_default \
     --env-file /root/telegram-bridge/.env --env-file /root/telegram-bridge/secret.env \
     -e N8N_WEBHOOK_URL="http://n8n:5678/webhook/<chemin-du-webhook>" -e OFFSET_FILE=/app/data/offset \
     -v /root/telegram-bridge/bridge.py:/app/bridge.py:ro -v /root/telegram-bridge/data:/app/data \
     python:3.12-alpine python -u /app/bridge.py
   ```
5. Vérifier : `docker logs telegram-bridge` doit afficher « relais démarré ».
