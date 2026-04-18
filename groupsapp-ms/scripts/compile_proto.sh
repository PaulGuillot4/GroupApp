#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROTO_DIR="$ROOT/proto"
SERVICES=(gateway auth users groups messaging files notifications)

python -c "import grpc_tools" 2>/dev/null || {
  echo "grpcio-tools no instalado. Ejecuta: pip install grpcio-tools==1.63.0"
  exit 1
}

for svc in "${SERVICES[@]}"; do
  OUT="$ROOT/services/$svc/generated"
  mkdir -p "$OUT"
  touch "$OUT/__init__.py"
  python -m grpc_tools.protoc \
    -I "$PROTO_DIR" \
    --python_out="$OUT" \
    --grpc_python_out="$OUT" \
    "$PROTO_DIR"/*.proto
  echo "Compiled protos for $svc → $OUT"
done
