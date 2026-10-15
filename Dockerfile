# GM Limpeza Analytics - Dockerfile
# Imagem base leve com Python 3.12
FROM python:3.12-slim

# Configurar timezone para Brasília
ENV TZ=America/Sao_Paulo
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Metadados
LABEL maintainer="Victor Monteiro"
LABEL description="GM Limpeza Analytics - Dashboard e ETL"

# Instalar cron, curl (healthcheck) e dependências do pymssql
RUN apt-get update && apt-get install -y \
    cron \
    curl \
    freetds-dev \
    freetds-bin \
    && rm -rf /var/lib/apt/lists/*

# Diretório de trabalho
WORKDIR /app

# Copiar requirements e instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código da aplicação
COPY dashboards/ /app/dashboards/
COPY scripts/ /app/scripts/
COPY .streamlit/ /app/.streamlit/
COPY .env /app/.env

# Criar diretórios necessários
RUN mkdir -p /app/cache /app/logs

# Configurar cron para ETL (08:00, 10:00, 12:00, 14:00, 16:00, 18:00 - horário de Brasília)
RUN echo "0 8,10,12,14,16,18 * * * cd /app && /usr/local/bin/python scripts/etl_cache.py >> logs/etl.log 2>&1" > /etc/cron.d/etl-job && \
    chmod 0644 /etc/cron.d/etl-job && \
    crontab /etc/cron.d/etl-job



# Expor portas dos Streamlits
EXPOSE 8501 8502 8503

# Healthcheck para monitorar saúde da aplicação
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Copiar e executar entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
