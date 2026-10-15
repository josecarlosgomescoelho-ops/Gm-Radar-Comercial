#!/bin/bash
# ============================================
# GM Limpeza — Iniciar Docker
# Apenas sobe os containers Docker localmente
# ============================================

set -e

echo "🐳 ========================================="
echo "🐳 Iniciando Docker - GM Limpeza Analytics"
echo "🐳 ========================================="
echo ""

# Ir para o diretório do projeto
cd "$(dirname "$0")/.."

# Verificar se docker-compose está disponível
if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose não encontrado. Instale primeiro."
    exit 1
fi

# Parar containers antigos (se existirem)
echo "🛑 Parando containers existentes..."
docker-compose down 2>/dev/null || true

# Subir containers
echo "🚀 Iniciando containers..."
make up

# Aguardar containers iniciarem
echo "⏳ Aguardando containers iniciarem..."
sleep 8

# Verificar health
echo ""
echo "🔍 Verificando saúde dos dashboards..."
if curl -s http://localhost:8501/_stcore/health | grep -q "ok"; then
    echo "✅ Dashboard de Vendas: http://localhost:8501"
else
    echo "❌ Dashboard de Vendas não respondeu"
fi

if curl -s http://localhost:8502/_stcore/health | grep -q "ok"; then
    echo "✅ Radar de Risco: http://localhost:8502"
else
    echo "❌ Radar de Risco não respondeu"
fi

# Status final
echo ""
echo "📊 Status dos containers:"
make status

echo ""
echo "✅ Docker iniciado com sucesso!"
echo ""
echo "🌐 URLs Locais:"
echo "   Dashboard de Vendas: http://localhost:8501"
echo "   Radar de Risco:      http://localhost:8502"
echo ""
echo "📋 Comandos úteis:"
echo "   make logs    - Ver logs em tempo real"
echo "   make shell   - Acessar shell do container"
echo "   make down    - Parar containers"
