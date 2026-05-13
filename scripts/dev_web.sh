#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="$ROOT_DIR/web_service/frontend"
BACKEND_URL="http://127.0.0.1:8000"
FRONTEND_URL="http://127.0.0.1:3000"

cd "$ROOT_DIR"

if [ ! -x "$ROOT_DIR/.venv/bin/python" ]; then
  echo ".venv가 없습니다. 먼저 아래 명령을 실행하세요:"
  echo "python -m venv .venv"
  echo "source .venv/bin/activate"
  echo "pip install -r web_service/backend/requirements.txt"
  exit 1
fi

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  echo "프론트엔드 패키지가 없습니다. 먼저 아래 명령을 실행하세요:"
  echo "cd web_service/frontend"
  echo "npm install"
  exit 1
fi

cleanup() {
  echo ""
  echo "개발 서버를 종료합니다."
  if [ -n "${BACKEND_PID:-}" ]; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  if [ -n "${FRONTEND_PID:-}" ]; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
}

trap cleanup INT TERM EXIT

echo "FastAPI 백엔드를 자동 업데이트 모드로 시작합니다: $BACKEND_URL"
"$ROOT_DIR/.venv/bin/uvicorn" web_service.backend.main:app \
  --host 127.0.0.1 \
  --port 8000 \
  --reload &
BACKEND_PID=$!

echo "Next.js 프론트엔드를 자동 업데이트 모드로 시작합니다: $FRONTEND_URL"
(
  cd "$FRONTEND_DIR"
  npm run dev
) &
FRONTEND_PID=$!

echo ""
echo "준비되면 브라우저에서 여세요:"
echo "$FRONTEND_URL"
echo ""
echo "코드를 수정하면 백엔드와 프론트엔드가 자동으로 다시 반영됩니다."
echo "종료하려면 Ctrl+C를 누르세요."

wait "$BACKEND_PID" "$FRONTEND_PID"
