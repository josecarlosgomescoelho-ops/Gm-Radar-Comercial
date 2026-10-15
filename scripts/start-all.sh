#!/bin/bash
# ============================================
# GM Limpeza — Iniciar Tudo
# Docker + Cloudflare Tunnel
# ============================================

set -e

echo "🚀 ========================================="
echo "🚀 GM Limpeza Analytics - Inicialização Completa"
echo "🚀 ========================================="
echo ""

# Ir para o diretório do projeto
cd "$(dirname "$0")/.."

# Passo 1: Iniciar Docker
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 PASSO 1: Iniciando Docker"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
./scripts/start-docker.sh

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "☁️  PASSO 2: Iniciando Cloudflare Tunnel"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
./scripts/start-cloudflare.sh

# Resumo final
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ SISTEMA COMPLETO INICIADO"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🐳 Docker:"
echo "   Status: $(docker inspect gm-analytics --format='{{.State.Status}}' 2>/dev/null || echo 'Error')"
echo "   Health: $(docker inspect gm-analytics --format='{{.State.Health.Status}}' 2>/dev/null || echo 'N/A')"
echo ""
echo "☁️  Cloudflare Tunnel:"
if pgrep -f "cloudflared tunnel run" > /dev/null; then
    echo "   Status: Running (PID: $(pgrep -f 'cloudflared tunnel run'))"
else
    echo "   Status: Not Running"
fi
echo ""
echo "🌐 URLs de Acesso:"
echo ""
echo "   LOCAL (desenvolvimento):"
echo "   • Dashboard de Vendas: http://localhost:8501"
echo "   • Radar de Risco:      http://localhost:8502"
echo ""
echo "   PÚBLICO (produção - HTTPS):"
echo "   • Dashboard de Vendas: https://sistemas.gmlimpeza.net"
echo "   • Radar de Risco:      https://radar.gmlimpeza.net"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📋 Comandos úteis:"
echo "   make logs                    - Ver logs do Docker"
echo "   tail -f /tmp/cf_tunnel.log  - Ver logs do Cloudflare"
echo "   make status                  - Status dos containers"
echo "   pkill -f cloudflared         - Parar Cloudflare Tunnel"
echo "   make down                    - Parar Docker"
echo ""
