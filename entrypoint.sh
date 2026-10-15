#!/bin/bash
set -e

echo "========================================="
echo "🚀 GM Limpeza Analytics - Iniciando..."
echo "========================================="

# Iniciar cron em background
echo "⏰ Iniciando cron para ETL agendado (01:00 diariamente)..."
cron

# Executar ETL sempre ao subir (incremental ou full load)
echo "⚙️ Executando ETL..."
if [ ! -f "/app/cache/movimentos.parquet" ]; then
    echo "📦 Cache vazio detectado. Executando ETL FULL LOAD..."
else
    echo "📦 Cache encontrado. Executando ETL INCREMENTAL..."
fi

python /app/scripts/etl_cache.py

if [ $? -eq 0 ]; then
    echo "✅ ETL concluído com sucesso!"
else
    echo "❌ ETL falhou! Continuando inicialização..."
fi

# Iniciar Streamlit - Dashboard Principal (porta 8501)
echo "========================================="
echo "🎯 Iniciando Dashboards..."
echo "📍 Dashboard de Vendas: http://localhost:8501"
echo "📍 Radar de Risco:      http://localhost:8502"
echo "📍 Painel de Gestão:    http://localhost:8503"
echo "========================================="

streamlit run /app/dashboards/app.py \
    --server.port=8501 \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.fileWatcherType=none \
    --browser.gatherUsageStats=false &

# Aguardar Streamlit 1 iniciar
sleep 3

# Iniciar Streamlit - Radar de Risco (porta 8502)
streamlit run /app/dashboards/radar_vendedor.py \
    --server.port=8502 \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.fileWatcherType=none \
    --browser.gatherUsageStats=false &

# Aguardar Streamlit 2 iniciar
sleep 3

# Iniciar Streamlit - Painel de Gestão (porta 8503)
exec streamlit run /app/dashboards/gestao.py \
    --server.port=8503 \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.fileWatcherType=none \
    --browser.gatherUsageStats=false
