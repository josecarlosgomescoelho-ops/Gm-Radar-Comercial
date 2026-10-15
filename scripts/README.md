# Scripts de Gerenciamento - GM Limpeza Analytics

Scripts simplificados para gerenciar a aplicação com Docker + Cloudflare Tunnel.

---

## 📋 Scripts Disponíveis

### 🐳 `start-docker.sh`
**Inicia apenas o Docker** com os 2 dashboards (portas 8501 e 8502).

```bash
./scripts/start-docker.sh
```

**O que faz:**
- Para containers existentes
- Inicia containers Docker
- Verifica health dos dashboards
- Mostra URLs locais

**Uso:** Desenvolvimento local sem exposição externa.

---

### ☁️ `start-cloudflare.sh`
**Inicia apenas o Cloudflare Tunnel** (assume que Docker já está rodando).

```bash
./scripts/start-cloudflare.sh
```

**O que faz:**
- Para túnel existente
- Verifica se Docker está rodando
- Verifica se dashboards estão respondendo
- Inicia túnel Cloudflare
- Mostra URLs públicas (HTTPS)

**Uso:** Quando Docker já está rodando e só precisa ativar o túnel público.

---

### 🚀 `start-all.sh` ⭐ (Recomendado)
**Inicia TUDO** - Docker + Cloudflare Tunnel.

```bash
./scripts/start-all.sh
```

**O que faz:**
- Executa `start-docker.sh`
- Executa `start-cloudflare.sh`
- Mostra resumo completo do sistema
- Exibe todas as URLs (local + público)

**Uso:** Inicialização completa da aplicação em produção.

---

### 🛑 `stop-all.sh`
**Para TUDO** - Docker + Cloudflare Tunnel.

```bash
./scripts/stop-all.sh
```

**O que faz:**
- Para Cloudflare Tunnel
- Para containers Docker
- Remove networks

**Uso:** Desligar completamente a aplicação.

---

## 🎯 Fluxo Recomendado

### Desenvolvimento Local
```bash
# Iniciar apenas Docker
./scripts/start-docker.sh

# Acessar
# http://localhost:8501
# http://localhost:8502

# Parar
make down
```

### Produção (com Cloudflare)
```bash
# Iniciar tudo
./scripts/start-all.sh

# Acessar
# https://sistemas.gmlimpeza.net
# https://radar.gmlimpeza.net

# Parar tudo
./scripts/stop-all.sh
```

---

## 📊 Comparação

| Script | Docker | Cloudflare | Uso |
|--------|--------|------------|-----|
| `start-docker.sh` | ✅ | ❌ | Dev local |
| `start-cloudflare.sh` | Requer já rodando | ✅ | Expor público |
| `start-all.sh` | ✅ | ✅ | Produção completa |
| `stop-all.sh` | 🛑 Para | 🛑 Para | Desligar tudo |

---

## 🔧 Requisitos

- **Docker & Docker Compose** instalados
- **cloudflared** instalado e configurado
- **Túnel Cloudflare** `gm-limpeza` configurado
- **Permissões de execução** nos scripts (`chmod +x`)

---

## 🐛 Troubleshooting

### Script não executa
```bash
chmod +x scripts/*.sh
```

### Docker não inicia
```bash
# Ver logs
make logs

# Verificar se porta está ocupada
lsof -i :8501
lsof -i :8502
```

### Cloudflare não conecta
```bash
# Ver logs
tail -f /tmp/cf_tunnel.log

# Verificar túnel
cloudflared tunnel info gm-limpeza
```

### Verificar tudo
```bash
# Status Docker
make status

# Status Cloudflare
pgrep -f cloudflared

# Testar dashboards
curl http://localhost:8501/_stcore/health
curl http://localhost:8502/_stcore/health
```

---

## 🎨 Customização

Para ajustar os scripts, edite:
- `scripts/start-docker.sh` - Configurações Docker
- `scripts/start-cloudflare.sh` - Configurações Cloudflare
- `scripts/start-all.sh` - Orquestração completa

---

**✅ Scripts prontos para uso!**
