# Deploy em PC Dedicado em Rede Local

Guia para hospedar os dashboards da GM Limpeza em um PC dedicado usando Cloudflare Tunnel.
O túnel `gm-limpeza` já existe — não precisa ser recriado, apenas as credenciais são transferidas.

---

## Pré-requisitos no PC novo

- Ubuntu/Debian instalado (recomendo Ubuntu Server 24.04 LTS)
- SSH habilitado para operar remotamente

---

## 1. Transferir o projeto

No WSL2 atual, rode:

```bash
rsync -avz ~/gm-limpeza-analytics/ usuario@IP_DO_PC:~/gm-limpeza-analytics/ \
  --exclude venv --exclude cache --exclude __pycache__

scp ~/.cloudflared/cert.pem usuario@IP_DO_PC:~/.cloudflared/
scp ~/.cloudflared/846fbdea-*.json usuario@IP_DO_PC:~/.cloudflared/
scp ~/.cloudflared/config.yml usuario@IP_DO_PC:~/.cloudflared/
```

---

## 2. Instalar dependências no PC dedicado

```bash
sudo apt update && sudo apt install -y python3 python3-venv python3-pip

# Instalar cloudflared
curl -L -o cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared.deb

# Criar venv e instalar pacotes Python
cd ~/gm-limpeza-analytics
python3 -m venv venv
source venv/bin/activate
pip install streamlit pandas pyarrow pymssql plotly
```

---

## 3. Configurar auto-start com systemd

Crie 3 serviços — um para cada dashboard e um para o túnel.

### Dashboard principal

`/etc/systemd/system/gm-dashboard.service`

```ini
[Unit]
Description=GM Limpeza Dashboard Principal
After=network.target

[Service]
User=usuario
WorkingDirectory=/home/usuario/gm-limpeza-analytics/dashboards
ExecStart=/home/usuario/gm-limpeza-analytics/venv/bin/streamlit run app.py --server.port 8501
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Radar de risco

`/etc/systemd/system/gm-radar.service`

```ini
[Unit]
Description=GM Limpeza Radar de Risco
After=network.target

[Service]
User=usuario
WorkingDirectory=/home/usuario/gm-limpeza-analytics/dashboards
ExecStart=/home/usuario/gm-limpeza-analytics/venv/bin/streamlit run radar_vendedor.py --server.port 8502
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Cloudflare Tunnel

`/etc/systemd/system/gm-tunnel.service`

```ini
[Unit]
Description=GM Limpeza Cloudflare Tunnel
After=network.target gm-dashboard.service gm-radar.service

[Service]
User=usuario
ExecStart=/usr/local/bin/cloudflared tunnel run gm-limpeza
Restart=always
RestartSec=15

[Install]
WantedBy=multi-user.target
```

### Ativar tudo

```bash
sudo systemctl daemon-reload
sudo systemctl enable gm-dashboard gm-radar gm-tunnel
sudo systemctl start gm-dashboard gm-radar gm-tunnel

# Verificar status
sudo systemctl status gm-dashboard gm-radar gm-tunnel
```

---

## 4. ETL nightly (cron no PC dedicado)

```bash
crontab -e
```

```
0 1 * * * /home/usuario/gm-limpeza-analytics/venv/bin/python /home/usuario/gm-limpeza-analytics/scripts/etl_cache.py >> /tmp/etl.log 2>&1
```

---

## 5. Verificar config.yml do cloudflared

Confirmar que o caminho do usuário está correto no novo PC:

```bash
nano ~/.cloudflared/config.yml
```

O arquivo deve ficar assim (ajuste `usuario` para o nome real):

```yaml
tunnel: 846fbdea-0819-4dad-82d8-1a09778709cd
credentials-file: /home/usuario/.cloudflared/846fbdea-0819-4dad-82d8-1a09778709cd.json

ingress:
  - hostname: dashboard.gmlimpeza.net
    service: http://localhost:8501
  - hostname: radar.gmlimpeza.net
    service: http://localhost:8502
  - service: http_status:404
```

---

## Resultado

Após reiniciar o PC, tudo sobe automaticamente via systemd.

- Dashboard de vendas → https://dashboard.gmlimpeza.net
- Radar de risco → https://radar.gmlimpeza.net

> O Cloudflare Tunnel faz conexão de saída — não é necessário abrir portas no roteador.
