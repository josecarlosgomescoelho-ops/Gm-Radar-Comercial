#!/bin/bash
# GM Limpeza — Iniciar dashboards localmente (sem túnel)

BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "🔴 Parando instâncias anteriores..."
pkill -f "streamlit run app.py" 2>/dev/null
pkill -f "streamlit run radar_vendedor.py" 2>/dev/null
sleep 2

echo "🟢 Ativando ambiente..."
source "$BASE_DIR/venv/bin/activate"
cd "$BASE_DIR/dashboards" || { echo "❌ Pasta dashboards não encontrada"; exit 1; }

echo "🚀 Subindo Dashboard Principal (porta 8501)..."
nohup streamlit run app.py --server.port 8501 > /tmp/streamlit_main.log 2>&1 &

echo "🚀 Subindo Radar de Risco (porta 8502)..."
nohup streamlit run radar_vendedor.py --server.port 8502 > /tmp/streamlit_radar.log 2>&1 &

sleep 6

if curl -s -o /dev/null -w "%{http_code}" http://localhost:8501 | grep -q "200"; then
    echo "✅ Dashboard de Vendas → http://localhost:8501"
else
    echo "❌ Dashboard não subiu. Veja: cat /tmp/streamlit_main.log"
fi

if curl -s -o /dev/null -w "%{http_code}" http://localhost:8502 | grep -q "200"; then
    echo "✅ Radar de Risco      → http://localhost:8502"
else
    echo "❌ Radar não subiu. Veja: cat /tmp/streamlit_radar.log"
fi
