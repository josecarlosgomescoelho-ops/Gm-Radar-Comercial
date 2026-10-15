# 🚀 Guia de Onboarding - GM Limpeza Analytics

Bem-vindo ao time! Este guia vai te ajudar a configurar o ambiente de desenvolvimento e entender como o sistema funciona.

---

## 📋 Índice

1. [Visão Geral do Projeto](#visão-geral-do-projeto)
2. [Setup Inicial - Desenvolvimento Local](#setup-inicial---desenvolvimento-local)
3. [Como Funciona o Sistema](#como-funciona-o-sistema)
4. [Estrutura do Código](#estrutura-do-código)
5. [Fluxo de Desenvolvimento](#fluxo-de-desenvolvimento)
6. [Deploy e Produção](#deploy-e-produção)
7. [Troubleshooting Comum](#troubleshooting-comum)
8. [Recursos Úteis](#recursos-úteis)

---

## 🎯 Visão Geral do Projeto

O **GM Limpeza Analytics** é um sistema de dashboards interativos que substituiu os relatórios manuais em Excel da GM Limpeza (distribuidora de produtos de limpeza no Ceará).

### Stack Tecnológica

- **Backend/Frontend**: Python 3.12 + Streamlit
- **Banco de Dados**: SQL Server (ERP Cronos da Inovare)
- **Cache**: Apache Parquet (via PyArrow)
- **Deploy**: Docker + Docker Compose
- **Acesso Externo**: Cloudflare Tunnel (HTTPS sem abrir portas)
- **Agendamento**: Cron (ETL periódico)

### Dashboards Disponíveis

1. **Dashboard de Vendas** (porta 8501)
   - 8 abas com KPIs, gráficos, análises
   - Gestão de vendedores e supervisores
   - Análise de produtos e clientes

2. **Radar de Risco** (porta 8502)
   - Classificação de clientes por risco de churn
   - Métricas de ciclo de compra
   - Follow-up automatizado

3. **Painel de Gestão** (porta 8503)
   - Visão estratégica de rentabilidade
   - Análise por supervisor e vendedor
   - Métricas consolidadas

---

## 🛠️ Setup Inicial - Desenvolvimento Local

### Pré-requisitos

Antes de começar, certifique-se de ter instalado:

- **Git** (controle de versão)
- **Python 3.12+**
- **VSCode** (recomendado)
- **Docker & Docker Compose** (opcional, mas recomendado)

### Passo 1: Clonar o Repositório

```bash
# Clone o repositório
git clone <URL_DO_REPO>
cd gm-limpeza-analytics

# Verifique a branch atual (geralmente main)
git branch
```

### Passo 2: Configurar Variáveis de Ambiente

Crie o arquivo `.env` na raiz do projeto (NUNCA commitar este arquivo!):

```bash
cp .env.example .env
nano .env
```

Preencha com as credenciais do banco de dados:

```env
DB_SERVER=<host_do_sql_server>
DB_PORT=<porta>
DB_USER=<usuario>
DB_PASSWORD=<senha>
DB_NAME=dbCronos
```

### Passo 3: Setup com Docker (Recomendado)

```bash
# Build da imagem
make build

# Subir a aplicação
make up

# Verificar status
make status

# Ver logs
make logs
```

Acesse os dashboards:
- http://localhost:8501 (Vendas)
- http://localhost:8502 (Radar)
- http://localhost:8503 (Gestão)

### Passo 3 (Alternativa): Setup Manual (Sem Docker)

```bash
# Criar ambiente virtual
python3.12 -m venv venv
source venv/bin/activate

# Instalar dependências
pip install -r requirements.txt

# Popular cache (primeira execução - pode demorar!)
python scripts/etl_cache.py

# Subir dashboards (3 terminais diferentes ou usar scripts/reiniciar.sh)
streamlit run dashboards/app.py --server.port=8501
streamlit run dashboards/radar_vendedor.py --server.port=8502
streamlit run dashboards/gestao.py --server.port=8503
```

### Passo 4: Verificar Funcionamento

```bash
# Testar se os dashboards estão respondendo
curl http://localhost:8501/_stcore/health
curl http://localhost:8502/_stcore/health
curl http://localhost:8503/_stcore/health

# Verificar se cache foi gerado
ls -lh cache/
```

---

## 🧠 Como Funciona o Sistema

### Arquitetura

```
SQL Server (ERP Cronos)
        │
        │  ETL: 6x/dia (8h, 10h, 12h, 14h, 16h, 18h)
        ▼
  scripts/etl_cache.py
        │
        │  Gera/Atualiza arquivos .parquet
        ▼
   cache/*.parquet
        │
        ├──▶ dashboards/app.py (Vendas)
        ├──▶ dashboards/radar_vendedor.py (Radar)
        └──▶ dashboards/gestao.py (Gestão)
                    │
                    │  Cloudflare Tunnel (Produção)
                    ▼
      https://sistemas.gmlimpeza.net
      https://radar.gmlimpeza.net
```

### ETL - Extract, Transform, Load

O script `scripts/etl_cache.py` é o coração do sistema:

**Quando roda:**
- No Docker: Automaticamente 6x/dia (8h, 10h, 12h, 14h, 16h, 18h)
- Manual: `make etl` ou `python scripts/etl_cache.py`

**O que faz:**
1. Conecta no SQL Server do ERP Cronos
2. Extrai dados de vendas, clientes, produtos
3. Aplica transformações e regras de negócio
4. Salva em arquivos `.parquet` na pasta `cache/`

**Modos de operação:**
- **Full Load**: Quando o parquet não existe (primeira vez)
- **Incremental**: Carrega só registros novos (baseado em watermark)
- **Fallback**: Se incremental falhar, faz full load

**Arquivos gerados:**
```
cache/
├── movimentos.parquet       # ~27k linhas - Vendas
├── itens.parquet           # ~180k linhas - Itens vendidos
├── radar_clientes.parquet  # ~33k linhas - Dados p/ Radar
├── radar_produtos.parquet  # ~42k linhas - Produtos p/ Radar
├── radar_rent_cli.parquet  # ~2k linhas - Rentabilidade
├── vendedores.parquet      # 28 linhas - Cadastro vendedores
├── supervisores.parquet    # 3 linhas - Supervisores
├── clientes_info.parquet   # ~11k linhas - Info clientes
└── pedidos_pendentes.parquet # Variável - Pedidos não faturados
```

### Dashboards - Como Leem os Dados

Os dashboards **sempre leem os arquivos Parquet**, nunca o banco diretamente (exceto se o parquet não existir).

**Vantagens:**
- ✅ Respostas instantâneas (sem latência de rede)
- ✅ Sem impacto no banco de produção
- ✅ Funciona mesmo se o SQL Server cair
- ✅ Cache versionado com Git (para testes)

**Exemplo de código (app.py):**
```python
import pandas as pd

# Lê parquet (super rápido)
df_movimentos = pd.read_parquet('cache/movimentos.parquet')

# Aplica filtros
df_filtrado = df_movimentos[
    (df_movimentos['DataFaturamento'] >= data_inicio) &
    (df_movimentos['DataFaturamento'] <= data_fim)
]
```

---

## 📂 Estrutura do Código

```
gm-limpeza-analytics/
│
├── dashboards/              # 🎨 Frontend - Streamlit Apps
│   ├── app.py              # Dashboard principal de vendas
│   ├── radar_vendedor.py   # Radar de risco de clientes
│   ├── gestao.py           # Painel estratégico de gestão
│   ├── auth.py             # Autenticação (se houver)
│   └── assets/             # Imagens, logos
│
├── scripts/                 # ⚙️ Backend - ETL e Utilitários
│   ├── etl_cache.py        # 🔥 ETL principal (CORE!)
│   ├── reiniciar.sh        # Script para reiniciar dashboards
│   ├── start-all.sh        # Inicia Docker + Cloudflare
│   ├── start-docker.sh     # Só Docker
│   ├── start-cloudflare.sh # Só Cloudflare
│   └── stop-all.sh         # Para tudo
│
├── cache/                   # 📦 Arquivos .parquet (gitignored)
├── logs/                    # 📋 Logs do ETL (gitignored)
│
├── docs/                    # 📚 Documentação técnica
│   ├── schema/             # CSVs mapeando tabelas do ERP
│   ├── analise-*.md        # Análises de dados históricas
│   └── deploy-*.md         # Guias de deploy
│
├── Doc/                     # 📖 Documentação para devs
│   ├── GUIA_ONBOARDING_DEV.md     # 👈 Você está aqui!
│   └── ACESSO_VPS_HOSTINGER.md    # Acesso à produção
│
├── requisitos/              # 📝 Gestão de requisitos
│   ├── a-desenvolver/
│   ├── em-desenvolvimento/
│   └── desenvolvidos/
│
├── sql/                     # 🗃️ Queries SQL de referência
│
├── .env                     # 🔐 Credenciais (NUNCA commitar!)
├── .env.example            # Template do .env
├── requirements.txt         # 📦 Dependências Python
├── Dockerfile              # 🐳 Imagem Docker
├── docker-compose.yml      # 🐳 Orquestração
├── Makefile                # 🛠️ Comandos úteis
├── entrypoint.sh           # Script de inicialização Docker
│
├── README.md               # Documentação geral
├── QUICKSTART.md           # Início rápido
└── CLOUDFLARE_TUNNEL.md    # Setup do túnel
```

---

## 🔄 Fluxo de Desenvolvimento

### 1. Pegar uma Task/Requisito

```bash
# Verifique requisitos a desenvolver
ls requisitos/a-desenvolver/

# Ou crie uma branch para sua feature
git checkout -b feature/nome-da-feature
```

### 2. Fazer Alterações

**Editando Dashboards:**
- Arquivos em `dashboards/*.py`
- Streamlit tem hot-reload: salva e atualiza no navegador

**Editando ETL:**
- Arquivo `scripts/etl_cache.py`
- Testar localmente: `python scripts/etl_cache.py`
- Validar parquets gerados: `ls -lh cache/`

### 3. Testar Localmente

```bash
# Com Docker (recomendado)
make down
make rebuild
make logs

# Manual
pkill -f streamlit  # Parar processos antigos
streamlit run dashboards/app.py --server.port=8501
```

### 4. Commitar Mudanças

```bash
# Ver o que mudou
git status
git diff

# Adicionar arquivos
git add dashboards/app.py
git add scripts/etl_cache.py

# Commitar (mensagem descritiva!)
git commit -m "feat: adiciona filtro por região no dashboard"

# Push
git push origin feature/nome-da-feature
```

### 5. Abrir Pull Request

- Descreva o que foi feito
- Inclua prints se for visual
- Referencie o requisito (issue)

---

## 🚀 Deploy e Produção

### Ambiente de Produção

O sistema roda em uma **VPS Hostinger** no caminho:

```
/opt/gm-analytics
```

**Como acessar:** Veja o guia [ACESSO_VPS_HOSTINGER.md](./ACESSO_VPS_HOSTINGER.md)

### Deploy Manual (VPS)

```bash
# 1. Conectar na VPS (veja guia de acesso)
ssh root@<IP_VPS>

# 2. Ir para a pasta do projeto
cd /opt/gm-analytics

# 3. Atualizar código
git pull origin main

# 4. Rebuild e restart
make rebuild

# 5. Verificar logs
make logs
```

### Deploy Automático (Futuro)

Podemos configurar CI/CD com GitHub Actions para deploy automático ao fazer push na branch `main`.

---

## 🐛 Troubleshooting Comum

### Problema: "Conexão com banco de dados falhou"

**Causa:** Credenciais erradas ou firewall bloqueando

**Solução:**
```bash
# Verificar .env
cat .env

# Testar conexão SQL Server
pip install pymssql
python -c "import pymssql; conn = pymssql.connect(server='<host>', user='<user>', password='<pass>', database='dbCronos'); print('OK')"
```

### Problema: "Porta 8501 já em uso"

**Causa:** Streamlit já rodando ou outra aplicação

**Solução:**
```bash
# Ver o que está usando a porta
lsof -i :8501

# Matar processos Streamlit
pkill -f streamlit

# Ou parar Docker
make down
```

### Problema: "Cache vazio / Parquet não encontrado"

**Causa:** ETL nunca rodou ou falhou

**Solução:**
```bash
# Rodar ETL manualmente
python scripts/etl_cache.py

# Ou com Docker
make etl

# Ver logs do ETL
cat logs/etl.log
```

### Problema: "Dashboard lento ou travando"

**Causa:** Dados muito grandes, sem paginação

**Solução:**
- Use `st.cache_data` para cachear operações pesadas
- Limite número de linhas exibidas
- Use `st.dataframe` com virtualização

### Problema: "Docker build falha"

**Causa:** Dependências ou permissões

**Solução:**
```bash
# Limpar tudo e rebuild
make clean
make build

# Ver logs detalhados
docker-compose build --no-cache
```

---

## 📚 Recursos Úteis

### Documentação Oficial

- [Streamlit Docs](https://docs.streamlit.io/)
- [Pandas Docs](https://pandas.pydata.org/docs/)
- [Plotly Python](https://plotly.com/python/)
- [Docker Docs](https://docs.docker.com/)

### Documentação Interna

- **README.md** - Visão geral do projeto e arquitetura
- **QUICKSTART.md** - Inicialização rápida
- **CLOUDFLARE_TUNNEL.md** - Setup do túnel Cloudflare
- **scripts/README.md** - Documentação dos scripts
- **dashboards/GUIA_IMPLEMENTACAO.md** - Guia de implementação

### Comandos Úteis (Makefile)

```bash
make help      # Lista todos os comandos
make build     # Build da imagem Docker
make up        # Subir aplicação
make down      # Parar aplicação
make restart   # Restart completo
make logs      # Ver logs em tempo real
make shell     # Acessar shell do container
make etl       # Executar ETL manualmente
make status    # Status dos containers
make rebuild   # Rebuild completo
make clean     # Limpar tudo (cuidado!)
```

### Regras de Negócio Críticas (SQL)

**Sempre use estas regras ao fazer queries:**

```sql
-- Campo de data: SEMPRE DataFaturamento (NUNCA DtMov)
-- TipoMov de vendas: '2.1', '2.4'
-- TipoMov de devoluções: '2.8', '2.3' (multiplicar TotMov por -1)
-- Excluir: Status 'C' (cancelado) e 'T' (transferido)
-- NOLOCK: SEMPRE usar em todas as tabelas

SELECT
    CASE WHEN M.TipoMov IN ('2.8','2.3')
         THEN M.TotMov * -1
         ELSE M.TotMov
    END AS ValorLiquido
FROM Movimento M WITH (NOLOCK)
WHERE M.DataFaturamento BETWEEN @inicio AND @fim
  AND M.TipoMov IN ('2.4','2.1','2.8','2.3')
  AND M.Status NOT IN ('C','T')
```

### Contexto de Negócio

- **Meta mensal:** R$ 1.600.000
- **Rentabilidade média:** ~25,88%
- **Região:** Ceará
- **Segmentos:** Clínicas, hospitais, varejo, escritórios
- **Time comercial:** 2 supervisores (Leandro: 6 vendedores | Cesar: 5 vendedores)

---

## 🎓 Próximos Passos

Agora que você configurou o ambiente:

1. ✅ Explore os 3 dashboards localmente
2. ✅ Leia o código dos dashboards (`dashboards/*.py`)
3. ✅ Entenda o ETL (`scripts/etl_cache.py`)
4. ✅ Veja um requisito em `requisitos/desenvolvidos/` para entender o fluxo
5. ✅ Acesse a VPS e veja o ambiente de produção
6. ✅ Pegue sua primeira task!

**Dúvidas?** Pergunte ao time! 🚀

---

**Atualizado em:** Setembro 2026
**Versão:** 1.0
