# 🖥️ Guia de Acesso à VPS Hostinger

Este guia ensina como acessar o servidor de produção da VPS Hostinger onde o sistema GM Limpeza Analytics está rodando.

---

## 📋 Índice

1. [Informações da VPS](#informações-da-vps)
2. [Acesso via SSH (Terminal)](#acesso-via-ssh-terminal)
3. [Acesso via VS Code com Remote-SSH](#acesso-via-vs-code-com-remote-ssh)
4. [Comandos Úteis na VPS](#comandos-úteis-na-vps)
5. [Estrutura de Pastas na VPS](#estrutura-de-pastas-na-vps)
6. [Como Fazer Deploy na VPS](#como-fazer-deploy-na-vps)
7. [Troubleshooting](#troubleshooting)

---

## 🌐 Informações da VPS

**Servidor:** VPS Hostinger
**Sistema Operacional:** Ubuntu/Debian
**Localização do Projeto:** `/opt/gm-analytics`
**Usuário:** `root` (ou usuário específico fornecido)
**IP/Hostname:** `<fornecido pelo administrador>`
**Porta SSH:** `22` (padrão) ou porta customizada

> ⚠️ **IMPORTANTE:** Solicite as credenciais de acesso (IP, usuário, senha/chave SSH) com o administrador do sistema antes de prosseguir.

---

## 🔐 Acesso via SSH (Terminal)

### Pré-requisitos

- Terminal (Linux/Mac/WSL) ou PuTTY (Windows)
- Credenciais de acesso (IP + usuário + senha ou chave privada)

### Passo 1: Conectar via SSH

**Linux/Mac/WSL:**

```bash
# Acesso com senha
ssh root@<IP_DA_VPS>

# Ou acesso com chave privada
ssh -i ~/.ssh/id_rsa root@<IP_DA_VPS>

# Se a porta SSH for customizada (ex: 2222)
ssh -p 2222 root@<IP_DA_VPS>
```

**Windows (PuTTY):**

1. Baixe o [PuTTY](https://www.putty.org/)
2. Abra o PuTTY
3. Em "Host Name", coloque: `root@<IP_DA_VPS>`
4. Em "Port", coloque: `22` (ou porta customizada)
5. Clique em "Open"
6. Digite a senha quando solicitado

### Passo 2: Verificar Acesso

Após conectar, você verá algo assim:

```bash
Welcome to Ubuntu 24.04 LTS
root@vps-hostname:~#
```

Verifique se o projeto está lá:

```bash
cd /opt/gm-analytics
ls -la
```

---

## 🎨 Acesso via VS Code com Remote-SSH

A extensão **Remote-SSH** permite editar arquivos da VPS diretamente no VS Code como se estivessem no seu PC local.

### Passo 1: Instalar a Extensão Remote-SSH

1. Abra o **VS Code**
2. Vá em **Extensions** (ícone de quadrados à esquerda ou `Ctrl+Shift+X`)
3. Pesquise por: **Remote - SSH**
4. Clique em **Install** na extensão oficial da Microsoft

![Remote-SSH Extension](https://code.visualstudio.com/assets/docs/remote/ssh/remote-ssh-extension.png)

### Passo 2: Configurar a Conexão SSH

#### Opção A: Configuração Manual (Recomendado)

1. No VS Code, pressione `F1` ou `Ctrl+Shift+P`
2. Digite: **Remote-SSH: Open SSH Configuration File**
3. Selecione: `~/.ssh/config` (Linux/Mac) ou `C:\Users\<SEU_USUARIO>\.ssh\config` (Windows)
4. Adicione a configuração da VPS:

```ssh-config
Host gm-vps
    HostName <IP_DA_VPS>
    User root
    Port 22
    IdentityFile ~/.ssh/id_rsa
```

**Explicação dos campos:**

- `Host gm-vps`: Nome amigável para identificar a conexão
- `HostName`: IP ou domínio da VPS
- `User`: Usuário SSH (root, ubuntu, etc.)
- `Port`: Porta SSH (geralmente 22)
- `IdentityFile`: Caminho para sua chave privada SSH (opcional, se usar senha, remova esta linha)

#### Opção B: Configuração Rápida (Com Senha)

Se você vai usar senha ao invés de chave SSH:

```ssh-config
Host gm-vps
    HostName <IP_DA_VPS>
    User root
    Port 22
```

5. **Salve o arquivo** (`Ctrl+S`)

### Passo 3: Conectar na VPS

1. Pressione `F1` ou `Ctrl+Shift+P`
2. Digite: **Remote-SSH: Connect to Host**
3. Selecione: **gm-vps** (o nome que você definiu)
4. Digite a senha (se aplicável) ou use a chave SSH
5. Aguarde a conexão (primeira vez pode demorar um pouco)

Você saberá que conectou quando ver no canto inferior esquerdo:

```
>< SSH: gm-vps
```

### Passo 4: Abrir o Projeto

1. No VS Code conectado, clique em **Open Folder**
2. Digite o caminho: `/opt/gm-analytics`
3. Clique em **OK**

Pronto! Agora você pode editar arquivos, rodar comandos no terminal integrado, tudo diretamente na VPS!

### Passo 5: Usar o Terminal Integrado

1. Pressione `` Ctrl+` `` (ou vá em **Terminal > New Terminal**)
2. O terminal já estará conectado na VPS!

```bash
root@vps-hostname:/opt/gm-analytics#
```

Agora você pode rodar comandos como:

```bash
make status        # Ver status dos containers
make logs          # Ver logs
make restart       # Restart da aplicação
```

---

## 🛠️ Comandos Úteis na VPS

### Verificar Status do Sistema

```bash
# Status dos containers Docker
cd /opt/gm-analytics
make status

# Ver processos rodando
docker ps

# Ver uso de recursos
htop           # Processador e memória (pressione 'q' para sair)
df -h          # Espaço em disco
```

### Gerenciar a Aplicação

```bash
cd /opt/gm-analytics

# Iniciar tudo
make up
# ou
./scripts/start-all.sh

# Parar tudo
make down
# ou
./scripts/stop-all.sh

# Restart completo
make restart

# Ver logs em tempo real
make logs

# Executar ETL manualmente
make etl
```

### Ver Logs

```bash
# Logs do Docker
make logs

# Logs do ETL
tail -f /opt/gm-analytics/logs/etl.log

# Logs do Cloudflare Tunnel
tail -f /tmp/cf_tunnel.log

# Ver logs de container específico
docker logs gm-analytics
```

### Atualizar Código

```bash
cd /opt/gm-analytics

# Atualizar da branch main
git pull origin main

# Rebuild e restart
make rebuild
```

---

## 📂 Estrutura de Pastas na VPS

```
/opt/gm-analytics/
├── dashboards/          # Código dos dashboards Streamlit
├── scripts/             # Scripts ETL e gerenciamento
├── cache/              # Arquivos .parquet gerados pelo ETL
├── logs/               # Logs da aplicação
├── .env                # Variáveis de ambiente (credenciais)
├── docker-compose.yml  # Configuração Docker
├── Dockerfile
└── ...
```

**Arquivos importantes:**

- `.env` - Credenciais do banco (NUNCA compartilhar!)
- `cache/*.parquet` - Dados em cache
- `logs/etl.log` - Log do ETL para debug

---

## 🚀 Como Fazer Deploy na VPS

### Deploy de Nova Feature

```bash
# 1. Conectar na VPS
ssh root@<IP_DA_VPS>
# ou via VS Code Remote-SSH

# 2. Ir para a pasta do projeto
cd /opt/gm-analytics

# 3. Fazer backup (opcional mas recomendado)
cp -r cache cache_backup_$(date +%Y%m%d)

# 4. Atualizar código
git pull origin main

# 5. Rebuild e restart
make rebuild

# 6. Verificar logs
make logs

# 7. Testar acessando os dashboards
# https://sistemas.gmlimpeza.net
# https://radar.gmlimpeza.net
```

### Deploy de Hotfix (Urgente)

```bash
# 1. Conectar na VPS
ssh root@<IP_DA_VPS>

# 2. Editar arquivo direto (emergência!)
nano /opt/gm-analytics/dashboards/app.py

# 3. Salvar e sair (Ctrl+O, Enter, Ctrl+X)

# 4. Restart rápido
make restart

# 5. IMPORTANTE: Commitar mudança depois!
git add dashboards/app.py
git commit -m "hotfix: descrição do fix"
git push origin main
```

### Rollback (Voltar Versão)

```bash
# 1. Ver commits recentes
git log --oneline -10

# 2. Voltar para commit anterior
git reset --hard <HASH_DO_COMMIT>

# 3. Rebuild
make rebuild

# 4. CUIDADO: Isso remove commits locais!
# Para manter histórico, use:
git revert <HASH_DO_COMMIT>
```

---

## 🐛 Troubleshooting

### Não Consigo Conectar via SSH

**Erro:** `Connection refused` ou `Connection timed out`

**Soluções:**

1. Verifique se o IP está correto
2. Verifique se a porta SSH está correta (pode não ser 22)
3. Verifique se seu IP está na whitelist do firewall
4. Tente de outra rede (pode ser bloqueio do seu provedor)

```bash
# Teste de conectividade
ping <IP_DA_VPS>

# Teste de porta SSH
telnet <IP_DA_VPS> 22
# ou
nc -zv <IP_DA_VPS> 22
```

### VS Code Remote-SSH Não Conecta

**Erro:** `Could not establish connection to "gm-vps"`

**Soluções:**

1. Verifique o arquivo `~/.ssh/config`
2. Teste conexão manual via terminal primeiro
3. Limpe cache do VS Code:
   - `F1` > **Remote-SSH: Kill VS Code Server on Host**
   - Tente conectar novamente
4. Verifique logs:
   - `F1` > **Remote-SSH: Show Log**

### Aplicação Não Sobe na VPS

**Erro:** `Container gm-analytics is unhealthy`

**Soluções:**

```bash
# Ver logs de erro
make logs

# Ver status detalhado
docker inspect gm-analytics

# Testar manualmente
docker-compose down
docker-compose up

# Ver se porta está ocupada
netstat -tulpn | grep 8501
```

### Erro de Permissão

**Erro:** `Permission denied`

**Soluções:**

```bash
# Ver dono dos arquivos
ls -la /opt/gm-analytics

# Ajustar permissões (cuidado!)
sudo chown -R root:root /opt/gm-analytics
sudo chmod -R 755 /opt/gm-analytics

# Tornar scripts executáveis
chmod +x scripts/*.sh
```

### Espaço em Disco Cheio

**Erro:** `No space left on device`

**Soluções:**

```bash
# Ver uso de disco
df -h

# Limpar Docker (imagens antigas, volumes órfãos)
docker system prune -a

# Limpar logs antigos
cd /opt/gm-analytics/logs
rm *.log.old

# Limpar cache de parquets antigos (se houver backup)
rm -rf cache_backup_*
```

---

## 🔒 Boas Práticas de Segurança

### ✅ SEMPRE Faça

- Use chave SSH ao invés de senha
- Mantenha o `.env` seguro (nunca commitar!)
- Faça backup antes de mudanças críticas
- Teste em local antes de deploy em produção
- Documente mudanças em commits descritivos

### ❌ NUNCA Faça

- Compartilhar credenciais por email/chat
- Commitar `.env` no Git
- Rodar `rm -rf /` ou comandos perigosos sem verificar
- Fazer deploy direto em produção sem testar
- Desligar a VPS sem avisar o time

---

## 📞 Contatos de Emergência

**Administrador da VPS:**
Nome: `<Administrador>`
Contato: `<Email/Telefone>`

**Suporte Hostinger:**
Site: https://www.hostinger.com.br/
Painel: https://hpanel.hostinger.com/

---

## 📚 Recursos Adicionais

- [Documentação VS Code Remote-SSH](https://code.visualstudio.com/docs/remote/ssh)
- [Guia SSH do GitHub](https://docs.github.com/en/authentication/connecting-to-github-with-ssh)
- [Comandos SSH Essenciais](https://www.ssh.com/academy/ssh/command)
- [Docker na VPS](https://docs.docker.com/engine/install/ubuntu/)

---

**Parabéns! Agora você tem acesso completo à VPS! 🎉**

**Próximos passos:**
1. ✅ Conecte via SSH no terminal
2. ✅ Configure o Remote-SSH no VS Code
3. ✅ Explore o código em `/opt/gm-analytics`
4. ✅ Rode `make status` para ver tudo funcionando
5. ✅ Veja os logs com `make logs`

**Dúvidas?** Consulte este guia ou peça ajuda ao time! 🚀

---

**Atualizado em:** Setembro 2026
**Versão:** 1.0
