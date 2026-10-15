#!/bin/bash
# ============================================
# GM Limpeza — Parar Tudo
# Para Docker + Cloudflare Tunnel
# ============================================

set -e

echo "🛑 ========================================="
echo "🛑 GM Limpeza Analytics - Parando Sistema"
echo "🛑 ========================================="
echo ""

# Ir para o diretório do projeto
cd "$(dirname "$0")/.."

# Passo 1: Parar Cloudflare Tunnel
echo "☁️  Parando Cloudflare Tunnel..."
if pgrep -f "cloudflared tunnel run" > /dev/null; then
    pkill -f "cloudflared tunnel run"
    echo "✅ Cloudflare Tunnel parado"
else
    echo "ℹ️  Cloudflare Tunnel já estava parado"
fi

# Passo 2: Parar Docker
echo ""
echo "🐳 Parando containers Docker..."
make down

echo ""
echo "✅ Sistema completamente parado"
echo ""
echo "Para reiniciar:"
echo "  ./scripts/start-all.sh       - Iniciar tudo"
echo "  ./scripts/start-docker.sh    - Apenas Docker"
echo "  ./scripts/start-cloudflare.sh - Apenas Cloudflare"
