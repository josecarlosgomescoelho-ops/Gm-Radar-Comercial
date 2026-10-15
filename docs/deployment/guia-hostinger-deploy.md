# Guia: Hospedando Aplicações com Domínio gmlimpeza.net

Este guia explica como usar o domínio `gmlimpeza.net` (registrado na Hostinger) para hospedar os dashboards e outras aplicações do projeto GM Limpeza Analytics.

## Visão Geral

### Domínio Atual do Projeto

- **Domínio**: `gmlimpeza.net`
- **Registrador**: Hostinger
- **Gerenciamento DNS**: Cloudflare (nameservers apontados para Cloudflare)
- **Túnel**: Cloudflare Tunnel `gm-limpeza`
- **SSL/TLS**: Automático via Cloudflare

### URLs Ativas

| Aplicação | URL | Porta Local |
|-----------|-----|-------------|
| Dashboard de Vendas | https://sistemas.gmlimpeza.net | 8501 |
| Radar de Risco | https://radar.gmlimpeza.net | 8502 |

### Arquitetura Atual

```
Internet
   ↓
Cloudflare DNS (gmlimpeza.net)
   ↓
Cloudflare Tunnel (gm-limpeza)
   ↓
VPS Hostinger (/opt/gm-analytics)
   ↓
Docker Containers (localhost:8501, 8502)
```

## Configuração Atual (Já Implementada)

O projeto já está configurado com:

✅ **Domínio**: `gmlimpeza.net` registrado na Hostinger
✅ **Nameservers**: Apontados para Cloudflare
✅ **Cloudflare Tunnel**: `gm-limpeza` configurado na VPS
✅ **Subdomínios ativos**: `sistemas` e `radar`

> Para entender a configuração do Cloudflare Tunnel em detalhes, veja [CLOUDFLARE_TUNNEL.md](./CLOUDFLARE_TUNNEL.md) e [CONFIGURACAO_DOMINIO.md](./CONFIGURACAO_DOMINIO.md).

## Adicionando Novos Subdomínios ao Projeto

### Passo a Passo para Adicionar um Novo Dashboard

Exemplo: Adicionar `gestao.gmlimpeza.net` para um novo dashboard na porta 8503.

#### 1. No Cloudflare (Adicionar DNS)

1. Acesse [Cloudflare Dashboard](https://dash.cloudflare.com/)
2. Selecione o domínio `gmlimpeza.net`
3. Vá em **DNS** → **Records**
4. Clique em **Add record**:
   - **Type**: CNAME
   - **Name**: `gestao` (cria gestao.gmlimpeza.net)
   - **Target**: `<UUID-do-tunnel>.cfargotunnel.com` (obtenha rodando `cloudflared tunnel list` na VPS)
   - **Proxy status**: Proxied (nuvem laranja)
   - **TTL**: Auto
5. Clique em **Save**

#### 2. Na VPS (Adicionar Rota no Tunnel)

Conecte na VPS e edite a configuração do tunnel:

```bash
# Conectar na VPS
ssh root@<IP_VPS>

# Editar config do tunnel
nano ~/.cloudflared/config.yml
```

Adicione a nova rota no arquivo `config.yml`:

```yaml
tunnel: gm-limpeza
credentials-file: /home/vicmo/.cloudflared/<UUID>.json

ingress:
  # Dashboard de Vendas (existente)
  - hostname: sistemas.gmlimpeza.net
    service: http://localhost:8501

  # Radar de Risco (existente)
  - hostname: radar.gmlimpeza.net
    service: http://localhost:8502

  # NOVO: Painel de Gestão
  - hostname: gestao.gmlimpeza.net
    service: http://localhost:8503

  # Catch-all
  - service: http_status:404
```

Salve o arquivo (`Ctrl+O`, `Enter`, `Ctrl+X`).

#### 3. Restart do Cloudflare Tunnel

```bash
# Parar tunnel atual
pkill -f cloudflared

# Reiniciar tunnel com nova configuração
nohup cloudflared tunnel run gm-limpeza > /tmp/cf_tunnel.log 2>&1 &

# Verificar logs
tail -f /tmp/cf_tunnel.log
```

#### 4. Adicionar Dashboard ao Docker

Edite o `docker-compose.yml` para adicionar o novo dashboard:

```bash
nano /opt/gm-analytics/docker-compose.yml
```

Adicione o novo serviço:

```yaml
services:
  dashboard-gestao:
    build: .
    container_name: gm-dashboard-gestao
    command: streamlit run dashboards/painel_gestao.py --server.port=8503
    ports:
      - "8503:8503"
    volumes:
      - .:/app
    env_file:
      - .env
    restart: unless-stopped
```

Restart do Docker:

```bash
cd /opt/gm-analytics
docker-compose up -d
```

#### 5. Testar o Novo Subdomínio

```bash
# Verificar DNS propagou
dig gestao.gmlimpeza.net

# Testar localmente primeiro
curl http://localhost:8503

# Testar pelo domínio
curl https://gestao.gmlimpeza.net
```

## Tipos de Registros DNS

### A Record (Address)
- Aponta domínio/subdomínio para um **IP IPv4**
- Exemplo: `analytics.dominio.com.br` → `203.0.113.45`

### AAAA Record
- Aponta domínio/subdomínio para um **IP IPv6**
- Exemplo: `app.dominio.com.br` → `2001:0db8:85a3::8a2e:0370:7334`

### CNAME (Canonical Name)
- Cria um **alias** para outro domínio
- Exemplo: `www.dominio.com.br` → `dominio.com.br`
- **Não pode** ser usado no domínio raiz (apex)

### MX Record
- Configura **servidores de email**
- Necessário se for usar email com o domínio

### TXT Record
- Adiciona informações de **texto** ao DNS
- Usado para verificação de propriedade, SPF, DKIM, etc.

## Configuração Atual do Projeto (Referência)

### Dashboard de Vendas (sistemas.gmlimpeza.net)

**Configuração DNS (Cloudflare):**
```
Type: CNAME
Name: sistemas
Target: <UUID>.cfargotunnel.com
Proxied: Yes
```

**Configuração Tunnel (`~/.cloudflared/config.yml`):**
```yaml
- hostname: sistemas.gmlimpeza.net
  service: http://localhost:8501
```

**Docker Compose:**
```yaml
dashboard-vendas:
  build: .
  container_name: gm-dashboard-vendas
  command: streamlit run dashboards/app.py --server.port=8501
  ports:
    - "8501:8501"
  volumes:
    - .:/app
  env_file:
    - .env
  restart: unless-stopped
```

### Radar de Risco (radar.gmlimpeza.net)

**Configuração DNS (Cloudflare):**
```
Type: CNAME
Name: radar
Target: <UUID>.cfargotunnel.com
Proxied: Yes
```

**Configuração Tunnel:**
```yaml
- hostname: radar.gmlimpeza.net
  service: http://localhost:8502
```

**Docker Compose:**
```yaml
dashboard-radar:
  build: .
  container_name: gm-dashboard-radar
  command: streamlit run dashboards/radar_vendedor.py --server.port=8502
  ports:
    - "8502:8502"
  volumes:
    - .:/app
  env_file:
    - .env
  restart: unless-stopped
```

## Verificando Propagação DNS

Após configurar DNS, pode levar até 48h para propagar (geralmente menos de 1h):

```bash
# Verificar registros CNAME dos dashboards
dig sistemas.gmlimpeza.net CNAME
dig radar.gmlimpeza.net CNAME

# Verificar resolução completa
dig sistemas.gmlimpeza.net
dig radar.gmlimpeza.net

# Verificar em múltiplos servidores DNS
nslookup sistemas.gmlimpeza.net 8.8.8.8
nslookup sistemas.gmlimpeza.net 1.1.1.1

# Testar acesso HTTPS
curl -I https://sistemas.gmlimpeza.net
curl -I https://radar.gmlimpeza.net
```

Ou use ferramentas online:
- [whatsmydns.net](https://www.whatsmydns.net/) - Digite `sistemas.gmlimpeza.net`
- [dnschecker.org](https://dnschecker.org/) - Verificação global de DNS

## Segurança e Melhores Práticas

### 1. HTTPS/SSL ✅

**Status atual do projeto:**
- ✅ SSL/TLS automático via Cloudflare
- ✅ Certificado válido para `*.gmlimpeza.net`
- ✅ Redirecionamento HTTP → HTTPS automático
- ✅ TLS 1.3 habilitado

**Verificar SSL:**
```bash
# Testar certificado SSL
openssl s_client -connect sistemas.gmlimpeza.net:443 -servername sistemas.gmlimpeza.net

# Ou use ferramentas online
# https://www.ssllabs.com/ssltest/analyze.html?d=sistemas.gmlimpeza.net
```

### 2. Proteção DDoS ✅

**Status atual:**
- ✅ Cloudflare proxy habilitado (nuvem laranja)
- ✅ Proteção DDoS automática do Cloudflare
- ✅ Rate limiting configurado
- ✅ Firewall rules ativas

**Verificar proteção:**
- Acesse Cloudflare Dashboard → Security → Overview
- Veja métricas de ataques bloqueados

### 3. Autenticação ✅

**Dashboards atuais:**
- ✅ **Radar de Risco**: Autenticação implementada (veja código em `dashboards/radar_vendedor.py`)
- ⚠️ **Dashboard de Vendas**: Sem autenticação (acesso interno/equipe)

**Para adicionar autenticação a novos dashboards:**
- Use o padrão implementado no Radar
- Ou configure Cloudflare Access (SSO gratuito até 50 usuários)

### 4. Backup de Configurações ✅

**Arquivos críticos já versionados:**
- ✅ `~/.cloudflared/config.yml` (tunnel)
- ✅ `docker-compose.yml` (containers)
- ✅ Documentação DNS neste guia

**Não versionado (manter backup manual):**
- ❌ `~/.cloudflared/<UUID>.json` (credenciais do tunnel)
- ❌ `.env` (credenciais banco de dados)

### 5. Monitoramento

**Ferramentas recomendadas:**
- **UptimeRobot**: Monitor gratuito de uptime (https://uptimerobot.com/)
- **Cloudflare Analytics**: Métricas de tráfego e performance
- **Logs do Tunnel**: `tail -f /tmp/cf_tunnel.log`

## Troubleshooting

### Dashboard não carrega (sistemas.gmlimpeza.net ou radar.gmlimpeza.net)

**1. Verificar DNS:**
```bash
dig sistemas.gmlimpeza.net
# Deve retornar IPs do Cloudflare (não do servidor diretamente)
```

**2. Verificar Cloudflare Tunnel:**
```bash
# Na VPS
pgrep -f cloudflared
# Deve retornar um PID

# Ver logs
tail -f /tmp/cf_tunnel.log
```

**3. Verificar Docker:**
```bash
# Na VPS
cd /opt/gm-analytics
docker ps
# Deve mostrar containers rodando

# Ver logs do dashboard específico
docker logs gm-dashboard-vendas
docker logs gm-dashboard-radar
```

**4. Testar localmente:**
```bash
# Na VPS
curl http://localhost:8501  # Dashboard de Vendas
curl http://localhost:8502  # Radar
```

### Erro 502 Bad Gateway

**Causa comum:** Container Docker parou ou porta não está respondendo

**Solução:**
```bash
# Na VPS
cd /opt/gm-analytics

# Verificar containers
docker ps -a

# Restart containers
make restart
# ou
docker-compose restart

# Verificar logs
make logs
```

### Erro 521 (Web server is down)

**Causa:** Cloudflare Tunnel não está conectado

**Solução:**
```bash
# Na VPS
pkill -f cloudflared
nohup cloudflared tunnel run gm-limpeza > /tmp/cf_tunnel.log 2>&1 &

# Aguardar 10 segundos e testar
sleep 10
curl https://sistemas.gmlimpeza.net
```

### Mudanças no config.yml não surtem efeito

**Solução:**
```bash
# Restart do tunnel para aplicar mudanças
pkill -f cloudflared
nohup cloudflared tunnel run gm-limpeza > /tmp/cf_tunnel.log 2>&1 &
```

### Dashboard lento ou travando

**Verificar recursos:**
```bash
# Na VPS
htop  # Ver CPU e memória
df -h # Ver espaço em disco

# Verificar cache ETL
ls -lh /opt/gm-analytics/cache/
```

**Solução:**
- Limpar cache antigo: `rm -f cache/*.parquet`
- Rodar ETL fresh: `make etl`
- Restart dashboards: `make restart`

## Recursos Adicionais

### Documentação do Projeto
- [CLOUDFLARE_TUNNEL.md](./CLOUDFLARE_TUNNEL.md) - Configuração detalhada do tunnel
- [CONFIGURACAO_DOMINIO.md](./CONFIGURACAO_DOMINIO.md) - Configuração avançada de DNS
- [ACESSO_VPS_HOSTINGER.md](./ACESSO_VPS_HOSTINGER.md) - Como acessar o servidor

### Documentação Externa
- [Cloudflare Tunnel Docs](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/)
- [Cloudflare DNS Docs](https://developers.cloudflare.com/dns/)
- [Documentação Hostinger](https://support.hostinger.com/)
- [Docker Compose Docs](https://docs.docker.com/compose/)

### Painéis e Ferramentas
- [Painel Cloudflare](https://dash.cloudflare.com/) - Gerenciar DNS e tunnel
- [Painel Hostinger](https://hpanel.hostinger.com/) - Gerenciar domínio
- [SSL Labs Test](https://www.ssllabs.com/ssltest/) - Testar SSL/TLS
- [DNS Checker](https://dnschecker.org/) - Verificar propagação DNS

## Checklist para Adicionar Novo Subdomínio

Use este checklist ao adicionar um novo dashboard ou aplicação:

- [ ] **Escolher nome do subdomínio** (ex: `gestao` para `gestao.gmlimpeza.net`)
- [ ] **Escolher porta local** (ex: 8503, não conflitar com portas existentes)
- [ ] **Criar/modificar dashboard** (se for novo dashboard Streamlit)
- [ ] **Adicionar ao docker-compose.yml** com porta e comando corretos
- [ ] **Adicionar rota ao ~/.cloudflared/config.yml** na VPS
- [ ] **Adicionar registro CNAME no Cloudflare DNS**
  - Nome: subdomínio escolhido
  - Target: UUID do tunnel + `.cfargotunnel.com`
  - Proxied: Yes (nuvem laranja)
- [ ] **Restart do Cloudflare Tunnel** (`pkill cloudflared && nohup cloudflared tunnel run gm-limpeza &`)
- [ ] **Restart do Docker** (`make restart` ou `docker-compose up -d`)
- [ ] **Testar localmente** (`curl http://localhost:PORTA`)
- [ ] **Aguardar DNS propagar** (1-5 minutos geralmente)
- [ ] **Testar via domínio** (`curl https://subdominio.gmlimpeza.net`)
- [ ] **Verificar SSL** (https deve funcionar automaticamente)
- [ ] **Configurar autenticação** (se aplicação for sensível)
- [ ] **Documentar neste guia** (adicionar à tabela de URLs Ativas)
- [ ] **Commitar mudanças** no Git (docker-compose.yml, docs, etc.)

## Status Atual dos Subdomínios

### Ativos ✅

| Subdomínio | Porta | Aplicação | Autenticação |
|------------|-------|-----------|--------------|
| sistemas.gmlimpeza.net | 8501 | Dashboard de Vendas | ❌ Não |
| radar.gmlimpeza.net | 8502 | Radar de Risco | ✅ Sim |

### Disponíveis para Uso

Portas e subdomínios sugeridos para expansão:
- `gestao.gmlimpeza.net` → 8503 (Painel de Gestão)
- `api.gmlimpeza.net` → 8000 (API REST se precisar)
- `etl.gmlimpeza.net` → 8504 (Dashboard de monitoramento do ETL)
- `dev.gmlimpeza.net` → 8505 (Ambiente de desenvolvimento/staging)

---

**Última atualização**: Setembro 2026
**Projeto**: GM Limpeza Analytics
**Domínio**: gmlimpeza.net
**Responsável**: Equipe de Desenvolvimento
