# GM Limpeza Analytics

Projeto de analytics para a **GM Limpeza**, distribuidora de produtos de limpeza (varejo + atacado) que opera no Ceará. Canal principal de vendas é telefone, com entrega via rotas de caminhão para clínicas, hospitais, varejos e escritórios. Também possui loja física.

---

## Stack

- **Fonte de dados:** SQL Server (ERP Cronos / Inovare)
- **Banco:** `dbCronos` · schema: `dbo`
- **Linguagem SQL:** T-SQL
- **Front-end atual de dashboards:** Manus (MVP publicado)
- **Ambiente de dev:** VS Code + Claude Code

> Credenciais de conexão ficam em `DadosConexão.txt` (fora do Git — ver `.gitignore`).

---

## Regras de negócio CRÍTICAS (validadas com o cliente)

Toda query de vendas/faturamento **deve** seguir estas regras. Não improvise.

### Tabela de movimentações: `Movimento`

- **Data correta para faturamento:** `DataFaturamento` (nunca `DtMov`).
- **Tipos de movimento (`TipoMov`):**
  - `'2.1'`, `'2.4'` → **vendas** (valor positivo).
  - `'2.8'`, `'2.3'` → **devoluções** (valor deve ser multiplicado por -1).
- **Status a EXCLUIR sempre:** `'C'` (cancelado) e `'T'` (transferido).

### Regra canônica de valor líquido

```sql
CASE
    WHEN M.TipoMov IN ('2.8','2.3') THEN M.TotMov * -1
    ELSE M.TotMov
END AS ValorLiquido
```

### Filtro base padrão

```sql
WHERE M.DataFaturamento BETWEEN @DataInicio AND @DataFim
  AND M.TipoMov IN ('2.4','2.1','2.8','2.3')
  AND M.Status NOT IN ('C','T')
```

Scripts de referência (já validados): `ScriptPivotMensal.sql`, `dadosBrutosDasVendas.sql`.

---

## Modelo de dados — tabelas core

| Tabela       | Uso                                               | Chaves relevantes                           |
|--------------|---------------------------------------------------|---------------------------------------------|
| `Movimento`  | Cabeçalho de vendas/devoluções/OS/etc.            | `IdMov`, `CodCliFor`, `CodVendedor`, `DataFaturamento`, `TipoMov`, `Status`, `TotMov` |
| `ItensMov`   | Itens de cada movimentação                        | `IdMov`, `IdProduto`, `Qtd`, `ValorUnitario`, `CustoUnitarioItem`, `CustoMedioItem` |
| `Cli_For`    | Clientes e fornecedores (mesmo cadastro)          | `CodCliFor`, `NomeCliFor`, `TipoCliente`, `IdCidade`, `CodFunc` (vendedor), `Inativo` |
| `Produtos`   | Cadastro de produtos                              | `IdProduto`, `CODPRODUTO`, `NOMEPRODUTO`, `IdGrupo`, `CustoMedio`, `PrecoVenda1` |
| `Estoque`    | Saldo e custos por filial/local                   | `IdProduto`, `CodFilial`, `CodLocal`, `SdoAtual`, `ECustoMedio`, `ClasseABC` |
| `Vendedores` | Vendedores e estrutura de supervisão              | `CodVendedor`, `NomeVendedor`, `CodSupervisor`, `Inativo` |

> Documentação completa está nos CSVs em `docs/schema/` (01_tabelas_e_linhas.csv, 02_colunas_detalhadas.csv, 03_chaves_primarias.csv, 05_indices.csv, etc.).

### Relacionamento vendedor ↔ cliente

- `Cli_For.CodFunc` aponta para `Vendedores.CodVendedor` (é o vendedor responsável pelo cliente, não o vendedor do pedido).
- Vendedor do pedido: `Movimento.CodVendedor`.
- Supervisor: via `Vendedores.CodSupervisor`.

### Observação importante

- O banco **não possui foreign keys declaradas** (CSV `04_chaves_estrangeiras` está vazio). As relações são convencionais; preste atenção em joins.
- Muitas tabelas têm colunas com sufixos fiscais (CBS/IBS/IS) recém-adicionadas pela reforma tributária — ignorar para análises de negócio.

---

## Convenções de código

### SQL

- Sempre T-SQL compatível com SQL Server.
- Usar aliases curtos e consistentes: `M` (Movimento), `I` (ItensMov), `CF` (Cli_For), `P` (Produtos), `V` (Vendedores), `E` (Estoque).
- Parâmetros de data sempre no topo como `DECLARE @DataInicio DATE` / `@DataFim DATE`.
- Comentários em português, cabeçalho com autor, data e descrição (ver padrão em `ScriptPivotMensal.sql`).
- Queries de produção devem ter tratamento de `NULL` (ex.: `ISNULL(col, 0)` em agregações monetárias).
- Evitar `SELECT *` em produção — listar colunas.

### Python / ETL (quando existir)

- Preferir `pyodbc` ou `sqlalchemy` para conectar ao SQL Server.
- `.env` para credenciais, **nunca** hardcode.
- Estrutura: `sql/` (queries versionadas) · `notebooks/` (exploração) · `scripts/` (ETL produtivo) · `dashboards/`.

---

## Estado atual do projeto

**Concluído:**
- Script validado de faturamento por vendedor/cliente com pivot mensal (`ScriptPivotMensal.sql`).
- Script de extração bruta das vendas (`dadosBrutosDasVendas.sql`).
- Dashboard MVP publicado no Manus (visão geral, por supervisor, gráficos, detalhamento).
- Meta mensal atual: **R$ 1.600.000** · rentabilidade média observada: **~25,88%**.
- Estrutura de supervisão: **Leandro** (6 vendedoras), **Cesar** (5 vendedores), **Outros**.

**Em aberto / próximos passos possíveis:**
- Migrar dashboard do Manus para uma stack mais sustentável (Streamlit / Power BI / Metabase).
- Modelagem dimensional (fato vendas, dimensão cliente, produto, tempo, vendedor).
- Análises: curva ABC de clientes, churn, ticket médio por rota, sazonalidade, rentabilidade por grupo de produto.
- Automatizar cálculo de meta diária e projeção.

---

## Gestão de Requisitos

Os requisitos do projeto ficam em `requisitos/`, organizados em três pastas que representam o ciclo de vida:

| Pasta | Significado |
|---|---|
| `requisitos/a-desenvolver/` | Backlog — especificado, aguardando desenvolvimento |
| `requisitos/em-desenvolvimento/` | Em progresso — implementação iniciada |
| `requisitos/desenvolvidos/` | Concluído — em produção |

### Convenção de nomes de arquivo

`<slug-da-funcionalidade>.md` — ex: `alerta-clientes-inativos.md`

### Campos obrigatórios em cada card

```
# Nome da Funcionalidade
**Status**: a-desenvolver | em-desenvolvimento | desenvolvido
**Criado em**: AAAA-MM-DD
**Prioridade**: Must Have | Should Have | Could Have | Won't Have
**Esforço estimado**: Pequeno (<2h) | Médio (2-8h) | Grande (>8h)

## Dor de Negócio
## História de Usuário
## Critérios de Aceite (checklist)
## Dados Necessários
## Impacto na Arquitetura
```

### Regra de movimentação — IMPORTANTE

O Claude **deve** mover o arquivo `.md` entre as pastas conforme o progresso:
- Ao **iniciar** o desenvolvimento de um requisito → mover de `a-desenvolver/` para `em-desenvolvimento/` e adicionar campo `**Iniciado em**:`
- Ao **concluir** → mover de `em-desenvolvimento/` para `desenvolvidos/`, atualizar `**Status**` e adicionar `**Concluído em**:`
- Nunca deixar o status do arquivo desatualizado em relação ao que foi feito

---

## Regras de comunicação com o Claude

- **Sempre responder em português brasileiro.**
- **Ser direto.** Não enrolar. Aprofundar só quando pedido.
- **Todo insight tem que ser acionável.** Se não leva a uma decisão, não entregue.
- **Custo-benefício antes de sofisticação.** Ferramentas gratuitas e simples antes de stacks complexas.
- **Não inventar colunas nem tabelas.** Se tiver dúvida do schema, consultar os CSVs em `docs/schema/` ou pedir validação.
- **Preservar as regras de negócio do SQL acima** em qualquer query nova. Se precisar fugir delas, avisar explicitamente e justificar.

---

## Estrutura do repositório

```
.
├── CLAUDE.MD                        # este arquivo
├── .gitignore
├── dashboards/                      # código dos dashboards Streamlit
│   ├── app.py                       # dashboard principal (8 abas)
│   ├── radar_vendedor.py            # radar de risco por vendedor
│   ├── app_legacy.py                # versão anterior (referência)
│   ├── requirements.txt
│   ├── assets/logo.jpg
│   └── .streamlit/config.toml
├── docs/
│   ├── schema/                      # CSVs de documentação do banco (gerados por scripts/discovery_banco_gm.py)
│   └── dashboards/                  # PDFs e prints dos dashboards
├── notebooks/                       # exploração ad-hoc
├── scripts/                         # utilitários e ETL
│   ├── discovery_banco_gm.py        # gera os CSVs em docs/schema/
│   └── reiniciar.sh                 # reinicia dashboard + túnel
├── sql/                             # queries SQL versionadas
└── requisitos/                      # gestão de requisitos (ver seção acima)
    ├── a-desenvolver/
    ├── em-desenvolvimento/
    └── desenvolvidos/
```