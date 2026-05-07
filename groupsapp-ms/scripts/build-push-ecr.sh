#!/bin/bash
# ─────────────────────────────────────────────────────────────
# Build & Push de imágenes a ECR
#
# Uso (desde la raíz del proyecto):
#   chmod +x scripts/build-push-ecr.sh
#   ./scripts/build-push-ecr.sh
#
# Prerequisitos:
#   - Docker instalado y corriendo
#   - AWS CLI configurado con credenciales del lab
# ─────────────────────────────────────────────────────────────
set -euo pipefail

ACCOUNT_ID=$(aws sts get-caller-identity --query 'Account' --output text)
REGION="${AWS_REGION:-us-east-1}"
ECR_BASE="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/groupsapp"

echo "═══ Autenticando en ECR ═══"
aws ecr get-login-password --region ${REGION} | \
  docker login --username AWS --password-stdin ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com

SERVICES=(auth users groups messaging files notifications gateway)

for svc in "${SERVICES[@]}"; do
  echo ""
  echo "═══ Building ${svc} ═══"
  docker build -t groupsapp-${svc}:latest -f services/${svc}/Dockerfile .
  
  echo "═══ Tagging ${svc} ═══"
  docker tag groupsapp-${svc}:latest ${ECR_BASE}/${svc}:latest
  
  echo "═══ Pushing ${svc} ═══"
  docker push ${ECR_BASE}/${svc}:latest
  
  echo "✓ ${svc} pushed to ${ECR_BASE}/${svc}:latest"
done

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  ✅ TODAS LAS IMÁGENES SUBIDAS A ECR          ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "Siguiente paso: actualizar image: en los manifiestos K8s"
echo "  Reemplazar jeanguillot/groupsapp-XXX:v1"
echo "  Por:         ${ECR_BASE}/XXX:latest"
