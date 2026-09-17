#!/bin/bash
# Lancement de NewsStreamAI sur le port configurable (défaut 8888 pour éviter le conflit macOS 8000)
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

PORT="${PORT:-8888}"

# Tuer tout processus existant sur ce port
kill $(lsof -t -i:$PORT) 2>/dev/null || true
sleep 1

# Lancer uvicorn en arrière-plan
python3 -m uvicorn api.server:app --host 0.0.0.0 --port $PORT > /tmp/newsstream_api.log 2>&1 &
PID=$!
echo "NewsStreamAI démarré avec PID $PID sur http://localhost:$PORT"
sleep 2

# Vérifier la réponse
curl -s http://localhost:$PORT/api/health
