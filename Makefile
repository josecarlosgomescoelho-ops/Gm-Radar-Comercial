.PHONY: help build up down restart logs shell etl clean status rebuild

# Ajuda (comando padrão)
help:
	@echo "========================================="
	@echo "GM Limpeza Analytics - Comandos Docker"
	@echo "========================================="
	@echo ""
	@echo "Comandos disponíveis:"
	@echo "  make build     - Build da imagem Docker"
	@echo "  make up        - Subir aplicação (detached)"
	@echo "  make down      - Parar aplicação"
	@echo "  make restart   - Restart completo"
	@echo "  make logs      - Ver logs em tempo real"
	@echo "  make shell     - Acessar shell do container"
	@echo "  make etl       - Executar ETL manualmente"
	@echo "  make clean     - Limpar tudo (cuidado!)"
	@echo "  make status    - Verificar status dos containers"
	@echo "  make rebuild   - Rebuild completo (clean + build + up)"
	@echo ""

# Build da imagem
build:
	@echo "🔨 Building Docker image..."
	docker-compose build

# Subir containers
up:
	@echo "🚀 Starting containers..."
	docker-compose up -d
	@echo "✅ Aplicação rodando em http://localhost:8501"

# Parar containers
down:
	@echo "🛑 Stopping containers..."
	docker-compose down

# Restart completo
restart: down up

# Ver logs em tempo real
logs:
	@echo "📋 Exibindo logs (Ctrl+C para sair)..."
	docker-compose logs -f

# Acessar shell do container
shell:
	@echo "🐚 Acessando shell do container..."
	docker-compose exec app bash

# Executar ETL manualmente
etl:
	@echo "⚙️ Executando ETL manualmente..."
	docker-compose exec app python /app/scripts/etl_cache.py

# Limpar tudo (cuidado!)
clean:
	@echo "🗑️ Limpando containers, volumes e imagens..."
	docker-compose down -v
	docker rmi gm-limpeza-analytics:latest 2>/dev/null || true
	@echo "✅ Limpeza concluída!"

# Verificar status
status:
	@echo "📊 Status dos containers:"
	docker-compose ps

# Rebuild completo (útil após mudanças no código)
rebuild:
	@echo "🔄 Rebuild completo..."
	$(MAKE) down
	$(MAKE) build
	$(MAKE) up
	@echo "✅ Rebuild concluído!"
