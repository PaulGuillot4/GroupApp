# ─────────────────────────────────────────────────────────────
# Build & Push de imágenes a ECR (Versión nativa para PowerShell Windows)
#
# Uso (desde la raíz del proyecto):
#   .\scripts\build-push-ecr.ps1
#
# Prerequisitos:
#   - Docker Desktop instalado y corriendo
#   - AWS CLI configurado con credenciales del lab (.aws/credentials)
# ─────────────────────────────────────────────────────────────

$ErrorActionPreference = "Stop"

Write-Host "Obteniendo Account ID de AWS..."
$ACCOUNT_ID = aws sts get-caller-identity --query 'Account' --output text
$REGION = "us-east-1"
$ECR_BASE = "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/groupsapp"

Write-Host "═══ Autenticando Docker en ECR ═══"
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"

$SERVICES = @("auth", "users", "groups", "messaging", "files", "notifications", "gateway")

foreach ($svc in $SERVICES) {
    Write-Host ""
    Write-Host "═══ Construyendo imagen: $svc ═══" -ForegroundColor Cyan
    docker build -t "groupsapp-${svc}:latest" -f "services/${svc}/Dockerfile" .
    
    Write-Host "═══ Etiquetando imagen: $svc ═══" -ForegroundColor Cyan
    docker tag "groupsapp-${svc}:latest" "${ECR_BASE}/${svc}:latest"
    
    Write-Host "═══ Subiendo a AWS ECR: $svc ═══" -ForegroundColor Cyan
    docker push "${ECR_BASE}/${svc}:latest"
    
    Write-Host "✓ $svc subido exitosamente a ${ECR_BASE}/${svc}:latest" -ForegroundColor Green
}

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║  ✅ TODAS LAS IMÁGENES SUBIDAS A ECR             ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "Tus imágenes están listas en AWS. Puedes continuar con el despliegue en CloudShell."
