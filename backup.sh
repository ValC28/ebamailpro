#!/bin/bash
set -e

REPO_DIR="/root/ebanista-backup"
DATE=$(date +%Y%m%d_%H%M%S)
DAY=$(date +%Y-%m-%d)
API_KEY=$(cat /root/.n8n_api_key)

cd "$REPO_DIR"

# --- Postgres dump ---
mkdir -p postgres_dumps
docker compose -f /root/docker-compose.yml exec -T postgres pg_dump -U n8n n8n > "postgres_dumps/n8n_${DAY}.sql"

# --- n8n workflows export (via API) ---
mkdir -p workflows
rm -f workflows/*.json
ids=$(curl -s -H "X-N8N-API-KEY: $API_KEY" "http://localhost:5678/api/v1/workflows?limit=250" | python3 -c "import json,sys; [print(w['id']) for w in json.load(sys.stdin)['data']]")
for id in $ids; do
  name=$(curl -s -H "X-N8N-API-KEY: $API_KEY" "http://localhost:5678/api/v1/workflows/$id" | python3 -c "
import json,sys
d = json.load(sys.stdin)
safe = ''.join(c if c.isalnum() or c in '-_ ' else '_' for c in d['name']).strip().replace(' ', '_')
print(safe)
data = {k: d[k] for k in ('name','nodes','connections','settings','active') if k in d}
json.dump(data, open(f'workflows/{safe}__{d[\"id\"]}.json', 'w'), ensure_ascii=False, indent=2)
")
done

# --- keep only last 30 days of dumps ---
find postgres_dumps -name "n8n_*.sql" -mtime +30 -delete

# --- commit + push ---
git add -A
if ! git diff --cached --quiet; then
  git commit -m "Backup automatique ${DATE}" -q
  git push origin main -q
  echo "Backup ${DATE}: committed and pushed"
else
  echo "Backup ${DATE}: no changes"
fi
