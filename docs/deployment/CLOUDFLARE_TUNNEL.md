# Cloudflare Tunnel - Guia de Configuração

## 🌐 Arquitetura Completa

```
┌─────────────────────────────────────────────────┐
│          Docker Container (localhost)           │
│                                                 │
│  app.py           → http://localhost:8501       │
│  radar_vendedor.py → http://localhost:8502      │
└─────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│         Cloudflare Tunnel (no host)             │
│                                                 │
│  Túnel: gm-limpeza                              │
└─────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│              Internet (HTTPS)                   │
│                                                 │
│  https://sistemas.gmlimpeza.net  → 8501         │
│  https://radar.gmlimpeza.net     → 8502         │
└─────────────────────────────────────────────────┘
```

---

## ✅ Status Atual

**Dashboards Docker:**
- ✅ Dashboard de Vendas: http://localhost:8501
- ✅ Radar de Risco: http://localhost:8502

**Cloudflare Tunnel:**
- Túnel configurado: `gm-limpeza`
- Rodando no **host** (não no Docker)

---

## 🚀 Iniciar Cloudflare Tunnel

### Opção 1: Manualmente (Testing)

```bash
# Iniciar túnel
cloudflared tunnel run gm-limpeza

# Verificar se está rodando
pgrep -f "cloudflared tunnel run"

# Ver logs
cloudflared tunnel logs gm-limpeza
```

### Opção 2: Background (Produção)

```bash
# Iniciar em background
nohup cloudflared tunnel run gm-limpeza > /tmp/cf_tunnel.log 2>&1 &

# Verificar logs
tail -f /tmp/cf_tunnel.log
```

### Opção 3: Systemd Service (Recomendado)

```bash
# Criar service
sudo cloudflared service install

# Iniciar
sudo systemctl start cloudflared

# Habilitar auto-start
sudo systemctl enable cloudflared

# Status
sudo systemctl status cloudflared
```

---

## 🔧 Configuração do Túnel

O túnel `gm-limpeza` já está configurado e aponta para:

**Arquivo de config:** `~/.cloudflared/config.yml`

```yaml
tunnel: gm-limpeza
credentials-file: /home/vicmo/.cloudflared/<UUID>.json

ingress:
  # Dashboard de Vendas
  - hostname: sistemas.gmlimpeza.net
    service: http://localhost:8501

  # Radar de Risco
  - hostname: radar.gmlimpeza.net
    service: http://localhost:8502

  # Catch-all
  - service: http_status:404
```

---

## 📋 Script de Inicialização Completo

Usar o script existente `scripts/reiniciar.sh` foi **substituído** pelo Docker.

### Novo Workflow:

```bash
# 1. Subir Docker (já sobe os 2 dashboards)
make up

# 2. Iniciar Cloudflare Tunnel (no host)
nohup cloudflared tunnel run gm-limpeza > /tmp/cf_tunnel.log 2>&1 &

# 3. Verificar
make status
pgrep -f cloudflared
```

### Script Automatizado (criar arquivo `start-all.sh`):

```bash
#!/bin/bash

echo "🚀 Iniciando GM Limpeza Analytics..."

# 1. Subir Docker
cd ~/gm-limpeza-analytics
make up

# 2. Aguardar containers subirem
sleep 5

# 3. Iniciar Cloudflare Tunnel
pkill -f cloudflared 2>/dev/null
nohup cloudflared tunnel run gm-limpeza > /tmp/cf_tunnel.log 2>&1 &

# 4. Verificar
sleep 3
echo ""
echo "✅ Status:"
make status
echo ""
if pgrep -f cloudflared > /dev/null; then
    echo "✅ Cloudflare Tunnel ativo"
    echo "   🌐 https://sistemas.gmlimpeza.net"
    echo "   🎯 https://radar.gmlimpeza.net"
else
    echo "❌ Cloudflare Tunnel não iniciou"
    echo "   Ver logs: tail -f /tmp/cf_tunnel.log"
fi
```

---

## 🔍 Troubleshooting

### Túnel não conecta

```bash
# Ver logs
tail -f /tmp/cf_tunnel.log

# Verificar credenciais
cloudflared tunnel info gm-limpeza

# Reconectar
pkill -f cloudflared
cloudflared tunnel run gm-limpeza
```

### Dashboards não acessíveis

```bash
# Verificar se portas estão expostas
make status

# Testar localmente
curl http://localhost:8501/_stcore/health
curl http://localhost:8502/_stcore/health

# Ver logs dos dashboards
make logs
```

### Portas ocupadas

```bash
# Verificar o que está usando as portas
lsof -i :8501
lsof -i :8502

# Parar Streamlit local (se ainda rodando)
pkill -f streamlit
```

---

## 📝 Comandos Úteis

```bash
# Ver todos os túneis
cloudflared tunnel list

# Info do túnel
cloudflared tunnel info gm-limpeza

# Testar rota específica
cloudflared tunnel route ip show

# Limpar sessões antigas
cloudflared tunnel cleanup gm-limpeza
```

---

## 🎯 URLs de Acesso

**Local (Docker):**
- Dashboard de Vendas: http://localhost:8501
- Radar de Risco: http://localhost:8502

**Externo (Cloudflare Tunnel):**
- Dashboard de Vendas: https://sistemas.gmlimpeza.net
- Radar de Risco: https://radar.gmlimpeza.net

---

## ⚡ Auto-start no Boot

### Opção 1: Crontab

```bash
crontab -e

# Adicionar linha:
@reboot cd /home/vicmo/gm-limpeza-analytics && make up && sleep 10 && /usr/local/bin/cloudflared tunnel run gm-limpeza > /tmp/cf_tunnel.log 2>&1
```

### Opção 2: Systemd (Recomendado)

**Cloudflare:** Já tem service nativo
```bash
sudo systemctl enable cloudflared
```

**Docker:** Configurado para auto-restart
```yaml
restart: unless-stopped  # Já está no docker-compose.yml
```

---

**✅ Setup completo! Docker + Cloudflare Tunnel integrados.**
