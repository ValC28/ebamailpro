#!/usr/bin/env python3
"""Relais Telegram -> n8n : récupère les messages du bot (long polling) et les transmet à n8n en interne.
Rien n'est exposé sur Internet. Seul le compte Telegram autorisé est relayé. Le jeton reste dans l'environnement (jamais écrit dans les logs)."""
import json, os, sys, time, urllib.request, urllib.error

TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
ALLOWED = int(os.environ['ALLOWED_CHAT_ID'])
SECRET = os.environ['BRIDGE_SECRET']
HOOK = os.environ['N8N_WEBHOOK_URL']
OFFSET_FILE = os.environ.get('OFFSET_FILE', '/app/offset')
API = f'https://api.telegram.org/bot{TOKEN}/'


def log(msg):
    print(time.strftime('%Y-%m-%d %H:%M:%S'), msg, flush=True)


def telegram(method, payload, timeout):
    req = urllib.request.Request(API + method, data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def forward(update):
    body = json.dumps(update).encode()
    for attempt in range(1, 4):
        try:
            req = urllib.request.Request(HOOK, data=body, headers={'Content-Type': 'application/json', 'X-Bridge-Secret': SECRET})
            with urllib.request.urlopen(req, timeout=200) as r:
                r.read()
            return True
        except urllib.error.HTTPError as e:
            log(f'n8n a répondu HTTP {e.code} (tentative {attempt}/3)')
            if e.code in (401, 403, 404):   # mauvais secret ou workflow inactif : inutile de répéter vite
                time.sleep(5)
        except Exception as e:
            log(f'envoi à n8n impossible : {type(e).__name__} (tentative {attempt}/3)')
        time.sleep(3)
    return False


def read_offset():
    try:
        return int(open(OFFSET_FILE).read().strip())
    except Exception:
        return None


def write_offset(value):
    try:
        with open(OFFSET_FILE, 'w') as f:
            f.write(str(value))
    except Exception as e:
        log(f"écriture de l'offset impossible : {type(e).__name__}")


def sender_id(update):
    for key in ('message', 'callback_query'):
        if key in update:
            return (update[key].get('from') or {}).get('id')
    return None


def main():
    offset = read_offset()
    log(f'relais démarré (compte autorisé : {ALLOWED}, offset : {offset})')
    while True:
        try:
            payload = {'timeout': 50, 'allowed_updates': ['message', 'callback_query']}
            if offset is not None:
                payload['offset'] = offset
            res = telegram('getUpdates', payload, timeout=70)
            for update in res.get('result', []):
                uid = update['update_id']
                if sender_id(update) != ALLOWED:
                    log(f'mise à jour {uid} ignorée (expéditeur non autorisé)')
                else:
                    ok = forward(update)
                    log(f'mise à jour {uid} transmise à n8n' if ok else f'mise à jour {uid} abandonnée après 3 échecs')
                offset = uid + 1
                write_offset(offset)
        except urllib.error.HTTPError as e:
            log(f'Telegram a répondu HTTP {e.code}' + (' (un autre processus ou un webhook utilise ce bot)' if e.code == 409 else ''))
            time.sleep(10)
        except Exception as e:
            log(f'erreur de connexion à Telegram : {type(e).__name__}')
            time.sleep(5)


if __name__ == '__main__':
    main()
