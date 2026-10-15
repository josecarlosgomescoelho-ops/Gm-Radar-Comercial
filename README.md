# GM Limpeza Analytics

Sistema de analytics para a **GM Limpeza**, distribuidora de produtos de limpeza (varejo + atacado) no Ceará. Substitui o processo manual de relatórios Excel/Manus com dashboards interativos em tempo real, alimentados diretamente pelo ERP Cronos.

---

## Visão Geral

| Item | Detalhe |
|---|---|
| **Fonte de dados** | SQL Server — ERP Cronos/Inovare (`dbCronos`) |
| **Linguagem** | Python 3.12 |
| **Dashboards** | Streamlit |
| **Formato de cache** | Apache Parquet (via PyArrow) |
| **Ambiente** | WSL2 (Ubuntu) + VSCode + Claude Code |
| **Acesso externo** | Cloudflare Tunnel |

---

## Arquitetura

```
SQL Server (ERP Cronos)
        │
        │  pymssql — 6x/dia (8h, 10h, 12h, 14h, 16h, 18h)
        ▼
  scripts/etl_cache.py
        │
        │  gera/atualiza Parquets (cache/)
        ▼
   cache/*.parquet
        │
        ├──▶ dashboards/app.py             → porta 8501
        │    Dashboard de Vendas
        │
        ├──▶ dashboards/radar_vendedor.py  → porta 8502
        │    Radar de Risco do Vendedor
        │
        └──▶ dashboards/gestao.py          → porta 8503
             Painel Estratégico de Gestão
                    │
                    │  Cloudflare Tunnel
                    ▼
      sistemas.gmlimpeza.net  /  radar.gmlimpeza.net
```

### Princípio de operação

O banco de produção é consultado **6 vezes ao dia** (8h, 10h, 12h, 14h, 16h, 18h) via cron no container Docker. Durante o dia, os dashboards leem exclusivamente os arquivos Parquet locais gerados pelo ETL. Isso minimiza lock contention com o ERP e garante resposta imediata nas consultas do usuário.

Se um Parquet não existir (primeira execução), o dashboard faz fallback direto ao banco com as mesmas queries do ETL.

---

## Estrutura do Projeto

```
gm-limpeza-analytics/
├── dashboards/
│   ├── app.py                  # Dashboard de Vendas (8 abas)
│   ├── radar_vendedor.py       # Radar de Risco multi-vendedor
│   └── assets/
│       └── logo.jpg
├── scripts/
│   ├── etl_cache.py            # ETL nightly — gera os Parquets
│   ├── reiniciar.sh            # Para e sobe todos os processos
│   └── discovery_banco_gm.py  # Script de exploração do schema (one-time)
├── cache/                      # Parquets gerados pelo ETL (gitignored)
├── logs/                       # Logs do ETL (gitignored)
├── docs/
│   └── schema/                 # 13 CSVs mapeando ~400 tabelas do dbCronos
├── requisitos/
│   ├── a-desenvolver/
│   ├── em-desenvolvimento/
│   └── desenvolvidos/
├── sql/                        # Queries T-SQL de referência
├── .env                        # Credenciais do banco (gitignored)
├── .gitignore
└── README.md
```

---

## Setup

### 1. Clonar e criar ambiente virtual

```bash
git clone <repo>
cd gm-limpeza-analytics
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configurar credenciais

Crie o arquivo `.env` na raiz do projeto (nunca versionar):

```env
DB_SERVER=<host>
DB_PORT=<porta>
DB_USER=<usuario>
DB_PASSWORD=<senha>
DB_NAME=dbCronos
```

### 3. Popular o cache pela primeira vez

```bash
venv/bin/python scripts/etl_cache.py
```

### 4. Subir os dashboards

```bash
bash scripts/reiniciar.sh
```

Acesse:
- Dashboard de Vendas → http://localhost:8501
- Radar de Risco → http://localhost:8502
- Painel de Gestão → http://localhost:8503

### 5. Cron — ETL periódico

No ambiente Docker, o ETL roda automaticamente 6 vezes ao dia (8h, 10h, 12h, 14h, 16h, 18h).

Para ambiente local sem Docker:

```cron
0 8,10,12,14,16,18 * * * cd /home/vmonteiro/gm-limpeza-analytics && venv/bin/python scripts/etl_cache.py >> logs/etl.log 2>&1
```

---

## 🐳 Deploy com Docker (Recomendado)

### Deploy Rápido

```bash
# 1. Build da imagem
make build

# 2. Subir aplicação
make up

# 3. Acessar dashboard
# http://localhost:8501
```

### Comandos Disponíveis

| Comando | Descrição |
|---------|-----------|
| `make build` | Build da imagem Docker |
| `make up` | Subir aplicação em background |
| `make down` | Parar aplicação |
| `make restart` | Restart completo (down + up) |
| `make logs` | Ver logs em tempo real |
| `make shell` | Acessar shell do container |
| `make etl` | Executar ETL manualmente |
| `make status` | Ver status dos containers |
| `make rebuild` | Rebuild completo (útil após mudanças) |
| `make clean` | Limpar tudo (cuidado!) |

### Sem Makefile (Docker Compose direto)

```bash
# Build
docker-compose build

# Subir
docker-compose up -d

# Logs
docker-compose logs -f

# Parar
docker-compose down
```

### Arquitetura do Container

```
┌─────────────────────────────────────┐
│   Container: gm-analytics           │
│                                     │
│  ┌──────────────────────────────┐  │
│  │   Streamlit (3 portas)       │  │
│  │   - 8501: Dashboard Vendas   │  │
│  │   - 8502: Radar de Risco     │  │
│  │   - 8503: Painel de Gestão   │  │
│  └──────────────────────────────┘  │
│                                     │
│  ┌──────────────────────────────┐  │
│  │   Cron (ETL 6x/dia)          │  │
│  │   - 8h, 10h, 12h, 14h,       │  │
│  │     16h, 18h → etl_cache.py  │  │
│  └──────────────────────────────┘  │
│                                     │
└─────────────────────────────────────┘
           │                │
           ▼                ▼
     [Volume: cache]   [SQL Server]
```

### Volumes Persistentes

O Docker monta volumes locais para:
- **`./cache`** → Cache de Parquets (persistente entre restarts)
- **`./logs`** → Logs do ETL e aplicação

### Health Check

O container possui health check automático que verifica se o Streamlit está respondendo:
- Intervalo: 30s
- Timeout: 10s
- Retries: 3

Status: `docker-compose ps` ou `make status`

### Troubleshooting

**Container não sobe:**
```bash
make logs  # Ver logs de erro
```

**Cache corrompido:**
```bash
make shell
rm -rf /app/cache/*.parquet
python /app/scripts/etl_cache.py
exit
make restart
```

**Executar ETL manualmente:**
```bash
make etl
```

**Rebuild completo após mudanças no código:**
```bash
make rebuild
```

---

## Dependências Principais

| Pacote | Versão | Uso |
|---|---|---|
| `streamlit` | 1.56.0 | Framework de dashboards |
| `pandas` | 3.0.2 | Manipulação de dados |
| `plotly` | 6.7.0 | Gráficos interativos |
| `pyarrow` | 23.0.1 | Leitura/escrita de Parquet |
| `pymssql` | 2.3.13 | Conexão com SQL Server |
| `numpy` | 2.4.4 | Cálculos vetorizados |
| `python-dotenv` | 1.0.1 | Carregamento do `.env` |

---

## ETL — Cache de Parquets

O `etl_cache.py` opera em **três modos por arquivo**:

| Modo | Quando | Como |
|---|---|---|
| **Full Load** | Parquet ausente (primeira execução) | Carrega todo o período histórico |
| **Incremental** | Parquet existente | Carrega só registros com `DataFaturamento` > watermark (MAX do Parquet), faz merge + deduplicação |
| **Fallback** | Incremental com erro | Executa full load automaticamente |

Tabelas pequenas (`vendedores`, `supervisores`) e agregações (`radar_produtos`, `radar_rent_cli`) são sempre full load.

### Parquets gerados

| Arquivo | Linhas (ref.) | Janela | Modo | Chave de dedup |
|---|---|---|---|---|
| `movimentos.parquet` | ~27 mil | 13 meses | Incremental | `IdMov` |
| `itens.parquet` | ~180 mil | 13 meses | Incremental | `IdMov + IdProduto` |
| `radar_clientes.parquet` | ~33 mil | 12 meses | Incremental | `CodCliFor + CodVendedor + TipoMov + DataFaturamento + IdMov` |
| `radar_produtos.parquet` | ~42 mil | 6 meses | Full load | — |
| `radar_rent_cli.parquet` | ~2 mil | 6 meses | Full load | — |
| `vendedores.parquet` | 28 | — | Full load | — |
| `supervisores.parquet` | 3 | — | Full load | — |
| `clientes_info.parquet` | ~11 mil | — | Full load | — |
| `pedidos_pendentes.parquet` | variável | estado atual | Full load | — |

---

## Dashboards

### Dashboard de Vendas (`app.py` — porta 8501)

8 abas cobrindo o ciclo completo de gestão comercial:

| Aba | Conteúdo |
|---|---|
| Visão Geral | KPIs do período, gauge de meta, projeção de faturamento com curva real + projetada |
| Por Supervisor | Cards por supervisor com faturamento/rentabilidade, ranking de vendedores por equipe, pizza de participação |
| Gráficos | Ranking de faturamento e rentabilidade por vendedor (barras horizontais com média de referência) |
| Detalhamento | Tabela completa por vendedor com filtro de supervisor; seção de pedidos pendentes (não faturados) |
| Produtos | Top 20 por margem R$ e por pior rentabilidade %; busca de produto por nome |
| Clientes | Top 20 por margem; tabela com WhatsApp clicável, segmento, região, badge NOVO (primeira compra ≤ 30 dias) |
| Pivot Mensal | Tabela cliente × mês com colorização (queda > 20% = amarelo, alta > 50% = verde); download CSV |
| Guia de Uso | Manual operacional: rotina diária, semanal, mensal; interpretação de rentabilidade; 3 alavancas de crescimento |

**Filtros globais (sidebar):** período (início/fim), meta do período, filtro multi-vendedor com persistência em JSON.

### Radar de Risco do Vendedor (`radar_vendedor.py` — porta 8502)

Ferramenta de gestão de carteira — classifica todos os clientes de um ou mais vendedores por risco de churn.

**Classificação de risco:**

| Status | Critério | Ação sugerida |
|---|---|---|
| 🔴 CRÍTICO | Sem compra ≥ 60 dias | Ligar hoje |
| 🟡 ATENÇÃO | Sem compra ≥ 30 dias **ou** ciclo habitual atrasado > 7 dias **ou** comprou ≥ 20% abaixo da média | Ligar esta semana |
| 🟢 ATIVO | Comprando dentro do padrão | Manter acompanhamento |
| 🔵 NOVO | Primeira compra nos últimos 30 dias | Follow-up de fidelização |
| 💀 PERDIDO | Sem compra ≥ 120 dias | Tentativa de resgate |

**Métricas por cliente:**
- Média mensal de compras (R$)
- Ciclo médio de compra (dias entre pedidos)
- Dia habitual de compra (mediana do dia do mês)
- Atraso em relação ao ciclo esperado
- Receita em risco = média mensal × meses parado
- Rentabilidade % e margem R$
- Pivot dos últimos 6 meses de compras

**Filtros:** supervisor → auto-popula multiselect de vendedores; filtro de status por cards clicáveis (toggle).

---

## Regras de Negócio Críticas (SQL)

Toda query de faturamento deve obedecer estas regras validadas com o cliente:

```sql
-- Campo de data: sempre DataFaturamento (nunca DtMov)
-- TipoMov de vendas: '2.1', '2.4'
-- TipoMov de devoluções: '2.8', '2.3' (multiplicar TotMov por -1)
-- Excluir sempre: Status 'C' (cancelado) e 'T' (transferido)
-- NOLOCK em todas as tabelas (banco sem FKs declaradas)

SELECT
    CASE WHEN M.TipoMov IN ('2.8','2.3') THEN M.TotMov * -1
         ELSE M.TotMov END AS ValorLiquido
FROM Movimento M WITH (NOLOCK)
WHERE M.DataFaturamento BETWEEN @inicio AND @fim
  AND M.TipoMov IN ('2.4','2.1','2.8','2.3')
  AND M.Status NOT IN ('C','T')
```

### Tabelas Core do dbCronos

| Tabela | Descrição | Chaves relevantes |
|---|---|---|
| `Movimento` | Cabeçalho de vendas, devoluções, pedidos | `IdMov`, `CodCliFor`, `CodVendedor`, `DataFaturamento`, `TipoMov`, `Status`, `TotMov` |
| `ItensMov` | Itens de cada movimentação | `IdMov`, `IdProduto`, `Qtd`, `ValorUnitario`, `CustoUnitarioItem` |
| `Cli_For` | Clientes e fornecedores | `CodCliFor`, `NomeCliFor`, `CodFunc` (vendedor responsável), `Inativo` |
| `Vendedores` | Vendedores e supervisores | `CodVendedor`, `NomeVendedor`, `CodSupervisor`, `Tipo`, `Inativo` |
| `Produtos` | Cadastro de produtos | `IdProduto`, `NOMEPRODUTO`, `IdGrupo` |
| `Grupos` | Grupos de produtos | `IdGrupo`, `NomeGrupo` |
| `Regiao` | Regiões de clientes | `IdRegiao`, `NomeRegiao` |
| `CategoriaCliFor` | Segmentos de clientes | `IdCategoriaCliFor`, `Denominacao` |

---

## 📖 Documentação para Desenvolvedores

Guias completos para onboarding e manutenção do sistema:

### 🚀 Para Novos Desenvolvedores

- **[Doc/GUIA_ONBOARDING_DEV.md](./Doc/GUIA_ONBOARDING_DEV.md)** - Guia completo de onboarding
  - Setup local e Docker
  - Como funciona o sistema (ETL, dashboards, cache)
  - Estrutura do código
  - Fluxo de desenvolvimento
  - Troubleshooting comum

### 🖥️ Para Acesso à Produção

- **[Doc/ACESSO_VPS_HOSTINGER.md](./Doc/ACESSO_VPS_HOSTINGER.md)** - Acesso à VPS Hostinger
  - Como conectar via SSH
  - Como usar VS Code Remote-SSH (passo a passo completo)
  - Comandos úteis na VPS
  - Como fazer deploy
  - Troubleshooting de conexão

### 🌐 Para Gerenciar Domínios

- **[Doc/CONFIGURACAO_DOMINIO.md](./Doc/CONFIGURACAO_DOMINIO.md)** - Configuração de Domínio
  - Como funciona o domínio com Cloudflare
  - Adicionar novos subdomínios
  - Gerenciar DNS
  - Configurar SSL/TLS
  - Troubleshooting DNS e certificados

### 📚 Índice Completo

- **[Doc/README.md](./Doc/README.md)** - Índice de toda a documentação

---

## Contexto do Negócio

- **Meta mensal:** R$ 1.600.000
- **Rentabilidade média histórica:** ~25,88%
- **Canal de vendas:** telefone (principal) + loja física
- **Logística:** entrega por rotas de caminhão
- **Mercado:** Ceará — clínicas, hospitais, varejo, escritórios
- **Time comercial:** 2 supervisores (Leandro: 6 vendedores · Cesar: 5 vendedores) + grupo Outros
