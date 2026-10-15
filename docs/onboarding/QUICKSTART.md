# 🚀 Quick Start - GM Limpeza Analytics

Guia rápido de inicialização do sistema.

---

## ⚡ Início Rápido (1 comando)

### Produção Completa (Docker + Cloudflare)
```bash
./scripts/start-all.sh
```

Isso inicia:
- ✅ Docker com 2 dashboards (8501 e 8502)
- ✅ Cloudflare Tunnel (HTTPS público)

### Desenvolvimento Local (Sem Cloudflare)
```bash
./scripts/start-docker.sh
```

---

## 📋 Comandos Principais

| Comando | Descrição |
|---------|-----------|
| `./scripts/start-all.sh` | Inicia tudo (recomendado) |
| `./scripts/start-docker.sh` | Apenas Docker local |
| `./scripts/start-cloudflare.sh` | Apenas Cloudflare |
| `./scripts/stop-all.sh` | Para tudo |
| `make status` | Ver status dos containers |
| `make logs` | Ver logs em tempo real |

---

## 🌐 URLs de Acesso

**Local (Desenvolvimento):**
- Dashboard de Vendas: http://localhost:8501
- Radar de Risco: http://localhost:8502

**Público (Produção - HTTPS):**
- Dashboard de Vendas: https://sistemas.gmlimpeza.net
- Radar de Risco: https://radar.gmlimpeza.net

---

## 🔧 Troubleshooting Rápido

### Container não sobe
```bash
make logs                    # Ver erro
docker-compose down          # Limpar
./scripts/start-docker.sh   # Tentar novamente
```

### Cloudflare não conecta
```bash
tail -f /tmp/cf_tunnel.log  # Ver logs
pkill -f cloudflared         # Parar
./scripts/start-cloudflare.sh  # Reiniciar
```

### Porta ocupada
```bash
lsof -i :8501               # Ver o que está usando
pkill -f streamlit          # Parar Streamlit local
make down                    # Parar Docker
```

### Reset completo
```bash
./scripts/stop-all.sh       # Para tudo
make clean                   # Limpa Docker
./scripts/start-all.sh      # Inicia do zero
```

---

## 🛠️ Manutenção

### Ver logs
```bash
# Docker
make logs

# Cloudflare
tail -f /tmp/cf_tunnel.log

# ETL
tail -f logs/etl.log
```

### Executar ETL manualmente
```bash
make etl
```

### Acessar shell do container
```bash
make shell
```

### Atualizar código
```bash
./scripts/stop-all.sh       # Para
make rebuild                 # Rebuild
./scripts/start-all.sh      # Inicia
```

---

## 📊 Verificação de Saúde

```bash
# Status geral
make status

# Health checks
curl http://localhost:8501/_stcore/health
curl http://localhost:8502/_stcore/health

# Processos
docker ps
pgrep -f cloudflared
```

---

## 🔄 Auto-start no Boot

### Opção 1: Crontab
```bash
crontab -e

# Adicionar:
@reboot cd /home/vicmo/gm-limpeza-analytics && ./scripts/start-all.sh
```

### Opção 2: Systemd (Cloudflare)
```bash
sudo systemctl enable cloudflared
```

---

## 📚 Documentação Completa

- **README.md** - Visão geral do projeto
- **scripts/README.md** - Detalhes dos scripts
- **CLOUDFLARE_TUNNEL.md** - Guia Cloudflare
- **Makefile** - Comandos disponíveis

---

**✅ Sistema pronto! Use `./scripts/start-all.sh` para começar.**
