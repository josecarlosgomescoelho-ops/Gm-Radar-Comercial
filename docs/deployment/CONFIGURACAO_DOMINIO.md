# 🌐 Configuração de Domínio - GM Limpeza Analytics

Este guia explica como configurar e gerenciar o domínio `gmlimpeza.net` para acessar os dashboards via URLs amigáveis e seguras (HTTPS).

---

## 📋 Índice

1. [Visão Geral](#visão-geral)
2. [Como Funciona](#como-funciona)
3. [Configuração Inicial do Domínio](#configuração-inicial-do-domínio)
4. [Adicionar Novos Subdomínios](#adicionar-novos-subdomínios)
5. [Gerenciar DNS no Cloudflare](#gerenciar-dns-no-cloudflare)
6. [Configurar Cloudflare Tunnel](#configurar-cloudflare-tunnel)
7. [Verificar e Testar](#verificar-e-testar)
8. [Troubleshooting](#troubleshooting)
9. [Renovação de Domínio](#renovação-de-domínio)
10. [Boas Práticas](#boas-práticas)

---

## 🎯 Visão Geral

### URLs Atuais do Sistema

| Dashboard | URL Local | URL Pública (Domínio) |
|-----------|-----------|------------------------|
| Dashboard de Vendas | http://localhost:8501 | https://sistemas.gmlimpeza.net |
| Radar de Risco | http://localhost:8502 | https://radar.gmlimpeza.net |
| Painel de Gestão | http://localhost:8503 | *(Adicionar conforme necessário)* |

### Informações do Domínio

- **Domínio:** `gmlimpeza.net`
- **Registrador:** *(Ex: Registro.br, GoDaddy, Namecheap, etc.)*
- **DNS:** Cloudflare (gerenciamento de DNS + CDN + SSL)
- **SSL/TLS:** Automático via Cloudflare (certificado gratuito)
- **Túnel:** Cloudflare Tunnel `gm-limpeza`

---

## 🔍 Como Funciona

### Arquitetura Completa

```
Usuário digita: https://sistemas.gmlimpeza.net
        │
        ▼
   DNS Cloudflare
        │ (resolve para IP do Cloudflare)
        ▼
   Cloudflare Network (CDN + Proxy)
        │ (SSL/TLS + proteção DDoS)
        ▼
   Cloudflare Tunnel (gm-limpeza)
        │ (conexão criptografada de saída)
        ▼
   VPS Hostinger (/opt/gm-analytics)
        │ (localhost:8501)
        ▼
   Dashboard Streamlit
```

### Vantagens desta Arquitetura

✅ **HTTPS automático** - SSL/TLS gerenciado pelo Cloudflare
✅ **Sem abrir portas** - Tunnel faz conexão de saída (mais seguro)
✅ **Proteção DDoS** - Cloudflare filtra tráfego malicioso
✅ **CDN global** - Baixa latência de qualquer lugar do mundo
✅ **URLs amigáveis** - `sistemas.gmlimpeza.net` ao invés de `IP:8501`

---

## ⚙️ Configuração Inicial do Domínio

### Pré-requisitos

- Domínio registrado (`gmlimpeza.net`)
- Conta Cloudflare (gratuita)
- Cloudflare Tunnel configurado (veja [CLOUDFLARE_TUNNEL.md](../CLOUDFLARE_TUNNEL.md))

### Passo 1: Adicionar Domínio ao Cloudflare

1. **Acesse o painel Cloudflare:**
   - URL: https://dash.cloudflare.com/
   - Faça login com sua conta

2. **Adicione o site (se ainda não foi adicionado):**
   - Clique em **"Add a Site"**
   - Digite: `gmlimpeza.net`
   - Clique em **"Add Site"**
   - Escolha plano **Free** (suficiente para nosso uso)
   - Clique em **"Continue"**

3. **Cloudflare vai escanear os DNS existentes:**
   - Aguarde a verificação
   - Revise os registros encontrados
   - Clique em **"Continue"**

4. **Cloudflare fornecerá Nameservers:**
   ```
   Exemplo:
   adam.ns.cloudflare.com
   vera.ns.cloudflare.com
   ```
   - **Copie esses nameservers** (vamos usar no próximo passo)

### Passo 2: Atualizar Nameservers no Registrador

Agora você precisa apontar seu domínio para os nameservers do Cloudflare.

**Exemplo com Registro.br:**

1. Acesse https://registro.br/
2. Faça login
3. Vá em **"Meus Domínios"** → `gmlimpeza.net`
4. Clique em **"Alterar Servidores DNS"**
5. Substitua os nameservers atuais pelos do Cloudflare:
   ```
   adam.ns.cloudflare.com
   vera.ns.cloudflare.com
   ```
6. Salve as alterações

**Exemplo com GoDaddy:**

1. Acesse https://www.godaddy.com/
2. Faça login
3. Vá em **"My Products"** → **"Domains"**
4. Clique em **"DNS"** ao lado de `gmlimpeza.net`
5. Role até **"Nameservers"**
6. Clique em **"Change"**
7. Selecione **"Custom"**
8. Insira os nameservers do Cloudflare
9. Clique em **"Save"**

**⏱️ Tempo de Propagação:**
- Pode levar de 5 minutos até 48 horas
- Geralmente está funcionando em 1-2 horas

### Passo 3: Verificar no Cloudflare

Volte ao painel Cloudflare:

1. Clique em **"Done, check nameservers"**
2. Cloudflare vai verificar se os nameservers foram atualizados
3. Quando estiver pronto, você verá: ✅ **"Great news! Cloudflare is now protecting your site"**

---

## ➕ Adicionar Novos Subdomínios

### Método 1: Via Cloudflare Tunnel (Recomendado)

Para adicionar um novo subdomínio que aponta para um dos dashboards:

**Exemplo: Adicionar `gestao.gmlimpeza.net` para o dashboard de gestão (porta 8503)**

#### No Servidor (VPS)

1. **Edite o arquivo de configuração do Tunnel:**

```bash
# Conecte na VPS
ssh root@<IP_VPS>

# Edite o config do Cloudflare
nano ~/.cloudflared/config.yml
```

2. **Adicione o novo ingress:**

```yaml
tunnel: gm-limpeza
credentials-file: /home/usuario/.cloudflared/<UUID>.json

ingress:
  # Dashboard de Vendas (existente)
  - hostname: sistemas.gmlimpeza.net
    service: http://localhost:8501

  # Radar de Risco (existente)
  - hostname: radar.gmlimpeza.net
    service: http://localhost:8502

  # Painel de Gestão (NOVO!)
  - hostname: gestao.gmlimpeza.net
    service: http://localhost:8503

  # Catch-all (sempre por último)
  - service: http_status:404
```

3. **Salve o arquivo** (`Ctrl+O`, `Enter`, `Ctrl+X`)

4. **Reinicie o Cloudflare Tunnel:**

```bash
# Parar o tunnel
pkill -f cloudflared

# Iniciar novamente
nohup cloudflared tunnel run gm-limpeza > /tmp/cf_tunnel.log 2>&1 &

# Verificar logs
tail -f /tmp/cf_tunnel.log
```

#### No Painel Cloudflare

1. Acesse https://dash.cloudflare.com/
2. Selecione o domínio `gmlimpeza.net`
3. Vá em **"DNS"** → **"Records"**
4. O Cloudflare Tunnel vai criar automaticamente o registro CNAME
5. Verifique se apareceu: `gestao` → CNAME → `<UUID>.cfargotunnel.com`

**Pronto!** Agora você pode acessar https://gestao.gmlimpeza.net

### Método 2: Via DNS Manual (Para outros serviços)

Se você quiser apontar um subdomínio para outro servidor ou IP:

1. Acesse https://dash.cloudflare.com/
2. Selecione `gmlimpeza.net`
3. Vá em **"DNS"** → **"Records"**
4. Clique em **"Add record"**
5. Preencha:
   - **Type:** `A` (para IP) ou `CNAME` (para outro domínio)
   - **Name:** nome do subdomínio (ex: `api`)
   - **IPv4 address:** IP do servidor (ex: `192.168.1.100`)
   - **Proxy status:** ☁️ Proxied (laranja) - proteção Cloudflare
   - **TTL:** Auto
6. Clique em **"Save"**

Agora `api.gmlimpeza.net` aponta para o IP configurado.

---

## 🗂️ Gerenciar DNS no Cloudflare

### Acessar o Painel DNS

1. https://dash.cloudflare.com/
2. Selecione `gmlimpeza.net`
3. Menu lateral: **"DNS"** → **"Records"**

### Tipos de Registros Comuns

| Tipo | Uso | Exemplo |
|------|-----|---------|
| `A` | Apontar para IPv4 | `@` → `192.168.1.100` |
| `AAAA` | Apontar para IPv6 | `@` → `2001:db8::1` |
| `CNAME` | Alias para outro domínio | `www` → `gmlimpeza.net` |
| `MX` | Servidor de email | `@` → `mail.gmlimpeza.net` |
| `TXT` | Verificações/SPF/DKIM | `@` → `v=spf1 include:...` |

### Proxy Status (Nuvem Laranja)

- ☁️ **Proxied (Laranja):** Tráfego passa pelo Cloudflare (proteção + CDN + SSL)
- ⚪ **DNS Only (Cinza):** Só resolve DNS, sem proteção

**Recomendação:** Use **Proxied** sempre que possível!

### Exemplo de Configuração Completa

```
Tipo   | Nome     | Conteúdo                        | Proxy  | TTL
-------|----------|---------------------------------|--------|-----
A      | @        | 192.168.1.100                  | Proxied| Auto
CNAME  | www      | gmlimpeza.net                  | Proxied| Auto
CNAME  | sistemas | <UUID>.cfargotunnel.com        | Proxied| Auto
CNAME  | radar    | <UUID>.cfargotunnel.com        | Proxied| Auto
CNAME  | gestao   | <UUID>.cfargotunnel.com        | Proxied| Auto
MX     | @        | mail.gmlimpeza.net (Priority 10)| -      | Auto
TXT    | @        | "v=spf1 include:_spf.example.com ~all" | - | Auto
```

---

## 🔧 Configurar Cloudflare Tunnel

### Ver Configuração Atual do Tunnel

```bash
# Na VPS
ssh root@<IP_VPS>

# Ver config
cat ~/.cloudflared/config.yml

# Ver info do tunnel
cloudflared tunnel info gm-limpeza
```

### Adicionar/Remover Rotas

Edite `~/.cloudflared/config.yml`:

```yaml
ingress:
  - hostname: novo.gmlimpeza.net
    service: http://localhost:8504

  # Exemplo com HTTPS
  - hostname: api.gmlimpeza.net
    service: https://localhost:8000
    originRequest:
      noTLSVerify: true  # Se o certificado local for autoassinado

  # Exemplo com websockets
  - hostname: ws.gmlimpeza.net
    service: ws://localhost:8765

  # Catch-all
  - service: http_status:404
```

Sempre reinicie o tunnel após mudanças:

```bash
pkill -f cloudflared
cloudflared tunnel run gm-limpeza
```

---

## ✅ Verificar e Testar

### 1. Verificar Propagação DNS

```bash
# Verificar se o DNS foi propagado
dig sistemas.gmlimpeza.net

# Ou use online
# https://dnschecker.org/
```

**Resultado esperado:**
```
sistemas.gmlimpeza.net. 300 IN CNAME <UUID>.cfargotunnel.com.
```

### 2. Testar Acesso HTTPS

```bash
# Testar se o site carrega
curl -I https://sistemas.gmlimpeza.net

# Resultado esperado: HTTP/2 200 OK
```

### 3. Verificar SSL/TLS

Acesse no navegador:
- https://sistemas.gmlimpeza.net
- Clique no **cadeado** ao lado da URL
- Deve mostrar: **"Conexão segura"** com certificado Cloudflare

### 4. Verificar Logs do Tunnel

```bash
# Na VPS
tail -f /tmp/cf_tunnel.log

# Deve mostrar conexões ativas:
# 2026-09-10T12:00:00Z INF Connection established
```

---

## 🐛 Troubleshooting

### Problema: "Site não pode ser alcançado"

**Causa:** DNS não propagado ou configuração incorreta

**Soluções:**

1. **Aguarde propagação DNS** (até 48h, geralmente 1-2h)

2. **Verifique nameservers:**
   ```bash
   dig NS gmlimpeza.net
   # Deve mostrar nameservers do Cloudflare
   ```

3. **Limpe cache DNS local:**
   ```bash
   # Windows
   ipconfig /flushdns

   # Mac
   sudo dscacheutil -flushcache

   # Linux
   sudo systemd-resolve --flush-caches
   ```

### Problema: "ERR_SSL_VERSION_OR_CIPHER_MISMATCH"

**Causa:** SSL não configurado corretamente

**Soluções:**

1. **No painel Cloudflare:**
   - Vá em **"SSL/TLS"** → **"Overview"**
   - Escolha modo: **"Full"** ou **"Full (strict)"**
   - **"Flexible"** também funciona (menos seguro)

2. **Verifique certificado:**
   - Cloudflare emite certificados automaticamente
   - Pode levar até 15 minutos após adicionar o domínio

### Problema: "Error 1033: Argo Tunnel error"

**Causa:** Cloudflare Tunnel não está rodando ou configurado errado

**Soluções:**

1. **Verifique se o tunnel está rodando:**
   ```bash
   # Na VPS
   pgrep -f cloudflared
   # Se não retornar nada, o tunnel não está rodando
   ```

2. **Reinicie o tunnel:**
   ```bash
   pkill -f cloudflared
   cloudflared tunnel run gm-limpeza
   ```

3. **Verifique config:**
   ```bash
   cat ~/.cloudflared/config.yml
   # Verifique se o hostname está correto
   ```

### Problema: Subdomínio não aparece no Cloudflare

**Causa:** Config do Tunnel não tem o hostname

**Solução:**

Adicione manualmente no painel:

1. https://dash.cloudflare.com/
2. Selecione `gmlimpeza.net`
3. Vá em **"DNS"** → **"Records"**
4. Adicione um registro CNAME:
   - **Name:** `sistemas`
   - **Target:** `<UUID>.cfargotunnel.com` (pegue de outro registro do tunnel)
   - **Proxy:** ☁️ Proxied
5. Salve

### Problema: "Too many redirects"

**Causa:** Loop de redirecionamento SSL

**Solução:**

1. No painel Cloudflare: **"SSL/TLS"** → **"Overview"**
2. Mude para **"Full"** (não "Flexible")
3. Aguarde 5 minutos
4. Teste novamente

---

## 🔄 Renovação de Domínio

### Verificar Data de Expiração

1. **No registrador** (Registro.br, GoDaddy, etc.)
   - Login → "Meus Domínios"
   - Veja a data de expiração

2. **Via WHOIS:**
   ```bash
   whois gmlimpeza.net | grep -i expir
   ```

### Renovar Domínio

**Geralmente 30-60 dias antes do vencimento:**

1. Acesse o painel do registrador
2. Vá em "Renovar Domínio"
3. Escolha o período (1, 2, 5 anos)
4. Pague a renovação

**⚠️ Importante:**
- Configure **renovação automática** se disponível
- Se o domínio expirar, os dashboards ficarão inacessíveis!

### Após Renovação

- O Cloudflare continua funcionando normalmente
- Não precisa reconfigurar DNS
- Tudo deve continuar funcionando sem interrupção

---

## ✅ Boas Práticas

### Segurança

1. ✅ **Use Cloudflare Proxy (nuvem laranja)** - Esconde IP real do servidor
2. ✅ **Habilite SSL/TLS Full** - Criptografia end-to-end
3. ✅ **Ative WAF (Web Application Firewall)** - Proteção contra ataques
4. ✅ **Configure Rate Limiting** - Previne abuse
5. ❌ **Nunca exponha IP direto** - Sempre use domínio

### DNS

1. ✅ **Use TTL baixo durante mudanças** - Facilita testes (300s)
2. ✅ **Aumente TTL após estabilizar** - Melhor performance (3600s)
3. ✅ **Documente mudanças DNS** - Anote o que cada registro faz
4. ❌ **Evite muitos subdomínios desnecessários** - Organização

### Cloudflare Tunnel

1. ✅ **Sempre use HTTPS** - Mesmo que o serviço local seja HTTP
2. ✅ **Configure health checks** - Monitore disponibilidade
3. ✅ **Separe ambientes** - `dev.gmlimpeza.net`, `prod.gmlimpeza.net`
4. ✅ **Teste antes de alterar** - Use outro subdomínio para validar

### Monitoramento

1. ✅ **Configure alertas de expiração de domínio** - Email/SMS antes do vencimento
2. ✅ **Monitore uptime** - Use UptimeRobot, Pingdom, etc.
3. ✅ **Revise logs do Cloudflare** - Identifique problemas cedo
4. ✅ **Verifique certificado SSL** - Deve renovar automaticamente

---

## 📚 Recursos Úteis

### Painéis e Ferramentas

- **Cloudflare Dashboard:** https://dash.cloudflare.com/
- **Verificar DNS:** https://dnschecker.org/
- **Testar SSL:** https://www.ssllabs.com/ssltest/
- **WHOIS Lookup:** https://www.whois.com/whois/

### Documentação Oficial

- [Cloudflare Tunnel Docs](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/)
- [Cloudflare DNS Docs](https://developers.cloudflare.com/dns/)
- [Cloudflare SSL/TLS Docs](https://developers.cloudflare.com/ssl/)

### Comandos Úteis

```bash
# Verificar DNS
dig gmlimpeza.net
dig sistemas.gmlimpeza.net

# Verificar nameservers
dig NS gmlimpeza.net

# Testar HTTPS
curl -I https://sistemas.gmlimpeza.net

# Verificar certificado SSL
openssl s_client -connect sistemas.gmlimpeza.net:443 -servername sistemas.gmlimpeza.net

# Ver info do Cloudflare Tunnel
cloudflared tunnel info gm-limpeza

# Ver rotas do Tunnel
cloudflared tunnel route dns gm-limpeza sistemas.gmlimpeza.net
```

---

## 📝 Checklist de Configuração Completa

Use este checklist ao configurar um novo domínio ou subdomínio:

### Configuração Inicial (Primeira Vez)

- [ ] Domínio registrado e pago
- [ ] Conta Cloudflare criada
- [ ] Domínio adicionado ao Cloudflare
- [ ] Nameservers atualizados no registrador
- [ ] DNS propagado (verificar com `dig`)
- [ ] SSL/TLS configurado (modo Full)
- [ ] Cloudflare Tunnel instalado na VPS
- [ ] Tunnel criado e configurado
- [ ] Primeiro subdomínio funcionando

### Adicionar Novo Subdomínio

- [ ] Decidir nome do subdomínio (ex: `api.gmlimpeza.net`)
- [ ] Identificar porta/serviço (ex: `localhost:8504`)
- [ ] Editar `~/.cloudflared/config.yml`
- [ ] Adicionar ingress com hostname e service
- [ ] Reiniciar Cloudflare Tunnel
- [ ] Verificar logs do tunnel
- [ ] Testar acesso via navegador
- [ ] Verificar SSL (cadeado verde)
- [ ] Documentar no README ou aqui

### Manutenção Regular

- [ ] Verificar data de expiração do domínio (mensal)
- [ ] Revisar logs do Cloudflare (semanal)
- [ ] Testar todos os subdomínios (semanal)
- [ ] Verificar uptime dos dashboards (diário via monitoramento)
- [ ] Backup da config do Cloudflare (mensal)

---

## 🎓 Exemplo Completo: Adicionar `api.gmlimpeza.net`

Vamos criar um passo a passo completo para adicionar um novo subdomínio de API:

### 1. Criar o Serviço (Exemplo: API Flask na porta 5000)

```bash
# Na VPS
cd /opt/gm-analytics
nano api.py
```

```python
from flask import Flask
app = Flask(__name__)

@app.route('/')
def home():
    return {"status": "ok", "message": "GM Limpeza API"}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```

```bash
# Rodar a API
python api.py &
```

### 2. Adicionar ao Cloudflare Tunnel

```bash
nano ~/.cloudflared/config.yml
```

```yaml
ingress:
  - hostname: sistemas.gmlimpeza.net
    service: http://localhost:8501

  - hostname: radar.gmlimpeza.net
    service: http://localhost:8502

  - hostname: api.gmlimpeza.net  # NOVO
    service: http://localhost:5000  # NOVO

  - service: http_status:404
```

### 3. Reiniciar Tunnel

```bash
pkill -f cloudflared
cloudflared tunnel run gm-limpeza &
```

### 4. Testar

```bash
# Testar localmente
curl http://localhost:5000
# {"status":"ok","message":"GM Limpeza API"}

# Aguardar 1-2 minutos e testar via domínio
curl https://api.gmlimpeza.net
# {"status":"ok","message":"GM Limpeza API"}
```

**Pronto! API acessível via https://api.gmlimpeza.net** 🎉

---

**Documentação atualizada em:** Setembro 2026
**Versão:** 1.0
**Autor:** Time GM Limpeza Analytics

**Dúvidas?** Consulte os recursos úteis acima ou peça ajuda ao time! 🚀
