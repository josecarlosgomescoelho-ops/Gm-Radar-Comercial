# Radar isolado. Não inicia ETL e não inclui credenciais ou dados na imagem.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY deploy/radar/requirements.lock /app/requirements.lock
RUN pip install --no-cache-dir -r requirements.lock
RUN groupadd --gid 10001 radar && useradd --uid 10001 --gid 10001 --create-home radar
COPY --chown=10001:10001 dashboards/radar_vendedor.py dashboards/radar_auth_store.py dashboards/radar_leitura.py dashboards/radar_dados.py dashboards/radar_cache_local.py dashboards/radar_metas.py dashboards/radar_pdf.py dashboards/radar_validado.py dashboards/radar_acessos.py dashboards/radar_equipe.py dashboards/radar_ordem.py dashboards/radar_instalacao.py dashboards/auth.py /app/dashboards/
COPY --chown=10001:10001 dashboards/radar_component/index.html dashboards/radar_component/estilo.css dashboards/radar_component/contrato.js dashboards/radar_component/admin.js dashboards/radar_component/app.js /app/dashboards/radar_component/
COPY --chown=10001:10001 dashboards/assets /app/dashboards/assets
COPY --chown=10001:10001 deploy/radar/healthcheck.py /app/healthcheck.py
USER 10001:10001
ENV RADAR_AUTH_DB=/radar-data/radar_auth.sqlite3 RADAR_DATA_DIR=/radar-data RADAR_AMBIENTE=VPS
EXPOSE 8504
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 CMD ["python", "/app/healthcheck.py"]
CMD ["python", "-m", "streamlit", "run", "dashboards/radar_vendedor.py", "--server.port", "8504", "--server.address", "0.0.0.0", "--server.headless", "true", "--server.fileWatcherType", "none", "--browser.gatherUsageStats", "false", "--client.showErrorDetails", "false", "--client.toolbarMode", "minimal", "--theme.base", "light"]
