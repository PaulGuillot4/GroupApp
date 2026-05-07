#!/bin/bash
# ─────────────────────────────────────────────────────────────
# GroupsApp — Script de despliegue completo para AWS Academy
#
# Uso:
#   1. Clonar/subir el repo a CloudShell o EC2 bastion
#   2. chmod +x scripts/deploy-eks.sh
#   3. ./scripts/deploy-eks.sh
#
# Este script:
#   - Reemplaza ACCOUNT_ID en los manifiestos automáticamente
#   - Despliega infra y servicios en orden correcto
#   - Instala NGINX Ingress Controller
#   - Configura HPA con Metrics Server
# ─────────────────────────────────────────────────────────────
set -euo pipefail

# ── Variables ──
ACCOUNT_ID=$(aws sts get-caller-identity --query 'Account' --output text)
REGION="us-east-1"
NAMESPACE="groupsapp"

echo "╔══════════════════════════════════════════════════╗"
echo "║  GroupsApp — Despliegue en EKS (AWS Academy)     ║"
echo "║  Account: ${ACCOUNT_ID}                          ║"
echo "║  Region:  ${REGION}                              ║"
echo "╚══════════════════════════════════════════════════╝"

# ── Paso 0: Reemplazar ACCOUNT_ID en todos los manifiestos ──
echo ""
echo "═══ [0/6] Reemplazando ACCOUNT_ID en manifiestos ═══"
find k8s/ -name "*.yaml" -exec sed -i "s/ACCOUNT_ID/${ACCOUNT_ID}/g" {} +
echo "✓ ACCOUNT_ID → ${ACCOUNT_ID} en todos los .yaml"

# ── Paso 1: Namespace y configuración ──
echo ""
echo "═══ [1/6] Namespace + ConfigMap + Secret ═══"
kubectl apply -f k8s/cluster/namespace.yaml
kubectl apply -f k8s/shared/shared-configmap.yaml
kubectl apply -f k8s/shared/shared-secret.yaml
echo "✓ Namespace y configuración aplicados"

# ── Paso 2: Infraestructura stateful ──
echo ""
echo "═══ [2/6] Infraestructura (PostgreSQL, MongoDB, Zookeeper, Kafka) ═══"

echo "  [2.1] PostgreSQL..."
kubectl apply -f k8s/infra/postgres-statefulset.yaml
kubectl -n ${NAMESPACE} rollout status statefulset/postgres --timeout=180s

echo "  [2.2] MongoDB..."
kubectl apply -f k8s/infra/mongodb-statefulset.yaml
kubectl -n ${NAMESPACE} rollout status statefulset/mongodb --timeout=180s

echo "  [2.3] Zookeeper..."
kubectl apply -f k8s/infra/zookeeper-statefulset.yaml
kubectl -n ${NAMESPACE} rollout status statefulset/zookeeper --timeout=180s

echo "  [2.4] Kafka..."
kubectl apply -f k8s/infra/kafka-statefulset.yaml
kubectl -n ${NAMESPACE} rollout status statefulset/kafka --timeout=180s

echo "✓ Infraestructura lista"

# ── Paso 3: Microservicios ──
echo ""
echo "═══ [3/6] Microservicios ═══"
for svc in auth users groups files messaging notifications gateway; do
  echo "  Desplegando ${svc}..."
  kubectl apply -f k8s/services/${svc}.yaml
done
echo ""
echo "  Esperando rollouts..."
for svc in auth users groups files messaging notifications gateway; do
  kubectl -n ${NAMESPACE} rollout status deployment/${svc} --timeout=120s \
    && echo "  ✓ ${svc}" \
    || echo "  ⚠ ${svc} aún arrancando"
done

# ── Paso 4: NGINX Ingress Controller + Ingress ──
echo ""
echo "═══ [4/6] NGINX Ingress Controller ═══"
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.9.4/deploy/static/provider/aws/deploy.yaml 2>/dev/null \
  || echo "  (Ingress controller ya instalado)"

echo "  Esperando controller (hasta 3 min)..."
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=180s \
  || echo "  ⚠ Controller aún arrancando"

kubectl apply -f k8s/ingress/ingress.yaml
echo "✓ Ingress configurado"

# ── Paso 5: Metrics Server + HPA ──
echo ""
echo "═══ [5/6] Autoescalado (HPA + Metrics Server) ═══"
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml 2>/dev/null \
  || echo "  (Metrics server ya instalado)"
kubectl apply -f k8s/autoscaling/hpa.yaml
echo "✓ HPA configurado"

# ── Paso 6: Verificación ──
echo ""
echo "═══ [6/6] Verificación final ═══"
echo ""
echo "── Pods ──"
kubectl get pods -n ${NAMESPACE} -o wide
echo ""
echo "── Servicios ──"
kubectl get svc -n ${NAMESPACE}
echo ""
echo "── HPAs ──"
kubectl get hpa -n ${NAMESPACE}
echo ""
echo "── Ingress ──"
kubectl get ingress -n ${NAMESPACE}
echo ""

LB_URL=$(kubectl get svc -n ingress-nginx ingress-nginx-controller \
  -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || echo "PENDIENTE")

echo "╔══════════════════════════════════════════════════╗"
echo "║  ✅ DESPLIEGUE COMPLETADO                        ║"
echo "╠══════════════════════════════════════════════════╣"
echo "║  URL: http://${LB_URL}                           ║"
echo "╠══════════════════════════════════════════════════╣"
echo "║  Probar con:                                     ║"
echo "║  curl http://${LB_URL}/health                    ║"
echo "╚══════════════════════════════════════════════════╝"
