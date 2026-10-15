#!/bin/bash
# ============================================
# GM Limpeza — Reiniciar Dashboards
# Mata processos ativos e sobe tudo de novo
# ============================================

echo "🔴 Parando processos..."
pkill -f "streamlit run app.py" 2>/dev/null
pkill -f "streamlit run radar_vendedor.py" 2>/dev/null
pkill -f cloudflared 2>/dev/null
pkill -f ngrok 2>/dev/null
sleep 2

echo "🟢 Ativando ambiente..."
source ~/gm-limpeza-analytics/venv/bin/activate
cd ~/gm-limpeza-analytics/dashboards || { echo "❌ Pasta dashboards não encontrada"; exit 1; }

echo "🚀 Subindo Dashboard Principal (porta 8501)..."
nohup streamlit run app.py --server.port 8501 > /tmp/streamlit_main.log 2>&1 &

echo "🚀 Subindo Radar de Risco (porta 8502)..."
nohup streamlit run radar_vendedor.py --server.port 8502 > /tmp/streamlit_radar.log 2>&1 &

sleep 3

# Verificar se estão rodando
if curl -s http://localhost:8501 | head -1 | grep -q "<!doctype"; then
    echo "✅ Dashboard Principal OK — http://localhost:8501"
else
    echo "❌ Dashboard Principal não subiu. Veja: cat /tmp/streamlit_main.log"
fi

if curl -s http://localhost:8502 | head -1 | grep -q "<!doctype"; then
    echo "✅ Radar de Risco OK — http://localhost:8502"
else
    echo "❌ Radar não subiu. Veja: cat /tmp/streamlit_radar.log"
fi

sleep 2

echo "🌐 Subindo túnel Cloudflare (gm-limpeza)..."
nohup cloudflared tunnel run gm-limpeza > /tmp/cf_tunnel.log 2>&1 &

sleep 5

if pgrep -f "cloudflared tunnel run" > /dev/null; then
    echo "✅ Túnel ativo"
    echo "   Dashboard de Vendas → https://sistemas.gmlimpeza.net"
    echo "   Radar de Risco      → https://radar.gmlimpeza.net"
else
    echo "❌ Túnel não subiu. Veja: cat /tmp/cf_tunnel.log"
fi