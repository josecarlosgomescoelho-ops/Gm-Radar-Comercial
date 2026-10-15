#!/bin/bash
# ============================================
# GM Limpeza — Iniciar Cloudflare Tunnel
# Apenas reinicia o túnel Cloudflare
# (Assume que Docker já está rodando)
# ============================================

set -e

echo "☁️  ========================================="
echo "☁️  Iniciando Cloudflare Tunnel"
echo "☁️  ========================================="
echo ""

# Verificar se cloudflared está instalado
if ! command -v cloudflared &> /dev/null; then
    echo "❌ cloudflared não encontrado. Instale primeiro:"
    echo "   https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/"
    exit 1
fi

# Parar túnel existente
echo "🛑 Parando túnel existente..."
pkill -f "cloudflared tunnel run" 2>/dev/null || true
sleep 2

# Verificar se Docker está rodando
echo "🔍 Verificando se Docker está rodando..."
if ! docker ps | grep -q gm-analytics; then
    echo "⚠️  Container Docker não está rodando!"
    echo "   Execute primeiro: ./scripts/start-docker.sh"
    echo ""
    read -p "Deseja iniciar o Docker agora? (s/N): " resposta
    if [[ "$resposta" =~ ^[Ss]$ ]]; then
        "$(dirname "$0")/start-docker.sh"
    else
        exit 1
    fi
fi

# Verificar se dashboards estão respondendo
echo "🔍 Verificando dashboards locais..."
if ! curl -s http://localhost:8501/_stcore/health | grep -q "ok"; then
    echo "❌ Dashboard de Vendas (porta 8501) não está respondendo"
    exit 1
fi

if ! curl -s http://localhost:8502/_stcore/health | grep -q "ok"; then
    echo "❌ Radar de Risco (porta 8502) não está respondendo"
    exit 1
fi

echo "✅ Dashboards locais OK"

# Iniciar túnel em background
echo ""
echo "🚀 Iniciando Cloudflare Tunnel..."
nohup cloudflared tunnel run gm-limpeza > /tmp/cf_tunnel.log 2>&1 &

# Aguardar túnel conectar
echo "⏳ Aguardando conexão..."
sleep 5

# Verificar se está rodando
if pgrep -f "cloudflared tunnel run" > /dev/null; then
    echo ""
    echo "✅ Cloudflare Tunnel iniciado com sucesso!"
    echo ""
    echo "🌐 URLs Públicas (HTTPS):"
    echo "   Dashboard de Vendas: https://sistemas.gmlimpeza.net"
    echo "   Radar de Risco:      https://radar.gmlimpeza.net"
    echo ""
    echo "📋 Comandos úteis:"
    echo "   tail -f /tmp/cf_tunnel.log  - Ver logs do túnel"
    echo "   pkill -f cloudflared        - Parar túnel"
    echo "   cloudflared tunnel info gm-limpeza  - Info do túnel"
else
    echo ""
    echo "❌ Erro ao iniciar Cloudflare Tunnel"
    echo "   Ver logs: tail -f /tmp/cf_tunnel.log"
    exit 1
fi
