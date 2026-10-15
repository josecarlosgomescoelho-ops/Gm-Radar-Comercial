# Cache ETL + Proteção do Banco de Produção

**Status**: `desenvolvido`
**Criado em**: 2026-04-24
**Iniciado em**: 2026-04-24
**Concluído em**: 2026-04-24
**Prioridade**: Must Have
**Esforço estimado**: Médio (4–6h)

---

## Dor de Negócio

O dashboard consultava diretamente o banco de produção do ERP (Cronos/SQL Server), causando sobrecarga que derrubou o servidor e interrompeu toda a operação da empresa. O sistema precisa ser desacoplado do banco de produção para que consultas analytics nunca mais afetem o ERP operacional.

## História de Usuário

> Como gestor, quero que o dashboard esteja sempre disponível e nunca cause lentidão no sistema da empresa, para que a operação e a análise de dados funcionem de forma independente.

## Critérios de Aceite

- [ ] Nenhuma query de analytics dispara contra o banco de produção durante o horário comercial (07h–20h)
- [ ] Um script ETL (`scripts/etl_cache.py`) executa todas as queries pesadas uma vez ao dia, às 01h, e salva os resultados em arquivos Parquet em `cache/`
- [ ] O dashboard lê exclusivamente dos arquivos Parquet — sem conexão direta ao SQL Server durante o uso normal
- [ ] O rodapé do dashboard exibe a data/hora da última atualização dos dados (ex: "Dados de 24/04/2026 01:03")
- [ ] Se o Parquet não existir (primeira execução ou falha do ETL), o dashboard consulta o banco como fallback e exibe aviso visual
- [ ] Todas as conexões ao banco (ETL + fallback) têm `timeout=30s` — nenhuma query trava indefinidamente
- [ ] O ETL registra log em `logs/etl.log` com horário de início, duração de cada query e status de conclusão
- [ ] Se alguma query do ETL demorar mais de 60s, o log registra alerta

## Escopo técnico

### Camada 1 — Proteção imediata (query timeout + TTL)
- Adicionar `timeout=30` em `get_conn()` nos dois dashboards (`app.py` e `radar_vendedor.py`)
- Aumentar TTL do `@st.cache_data` de 300s para 1800s (30 min) — válido para o fallback
- Filtro de data padrão no dashboard limitado a 30 dias (evitar queries de período longo)

### Camada 2 — ETL local com Parquet
- Criar `scripts/etl_cache.py`: executa todas as queries de `app.py` e `radar_vendedor.py`, salva em `cache/*.parquet`
- Criar `cache/` no `.gitignore` (dados não vão para o repositório)
- Refatorar `app.py` e `radar_vendedor.py`: funções de dados lêem do Parquet quando disponível
- Agendar ETL via `cron`: `0 1 * * *`
- Exibir timestamp de atualização no rodapé dos dashboards

## Dados Necessários

| Arquivo Parquet | Query origem | Tabelas envolvidas |
|---|---|---|
| `cache/vendas.parquet` | `q_vendas()` | Movimento, Cli_For, Vendedores |
| `cache/rentabilidade_vendedor.parquet` | `q_rentabilidade_vendedor()` | Movimento, ItensMov, Cli_For, Vendedores |
| `cache/rentabilidade_produtos.parquet` | `q_rentabilidade_produtos()` | ItensMov, Movimento, Produtos, Grupos |
| `cache/rentabilidade_clientes.parquet` | `q_rentabilidade_clientes()` | Movimento, ItensMov, Cli_For, Vendedores |
| `cache/radar_clientes.parquet` | queries do radar | Movimento, Cli_For, Vendedores |

Período do ETL: últimos 13 meses (mês atual + 12 anteriores) — cobre todos os filtros possíveis do dashboard.

## Impacto na Arquitetura

- **Novo arquivo**: `scripts/etl_cache.py`
- **Nova pasta**: `cache/` (ignorada pelo Git)
- **Nova pasta**: `logs/` (ignorada pelo Git)
- **Modificado**: `dashboards/app.py` — `get_conn()` com timeout, funções de dados com fallback Parquet
- **Modificado**: `dashboards/radar_vendedor.py` — idem
- **Modificado**: `.gitignore` — adicionar `cache/` e `logs/`
- **Modificado**: `scripts/reiniciar.sh` — opcional: verificar se cache está atualizado ao subir
- **Cron**: `0 1 * * * python scripts/etl_cache.py >> logs/etl.log 2>&1`

## Riscos

- Se o ETL falhar às 01h e ninguém perceber, o dashboard continuará mostrando dados do dia anterior (comportamento aceitável, com aviso visual)
- O Parquet de 13 meses pode ter entre 20–100MB dependendo do volume — verificar espaço em disco antes
- A refatoração das funções de dados exige testes para garantir que o schema dos Parquets bate com o que o dashboard espera
