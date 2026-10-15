# Faixa de Pré-Vendas Abertas no Radar de Risco

**Status**: desenvolvido
**Criado em**: 2026-06-09
**Iniciado em**: 2026-06-09
**Concluído em**: 2026-06-09
**Prioridade**: Must Have
**Esforço estimado**: Médio (2-8h)

---

## Dor de Negócio

Vendedoras não têm visibilidade das pré-vendas que estão travadas no ERP. Uma pré-venda em `Status = 'T'` não vira faturamento até ser liberada — mas hoje ela some do radar. O resultado é que pedidos ficam parados dias sem que a vendedora saiba, perdendo prazo de entrega ou deixando o cliente sem o produto.

---

## História de Usuário

> Como **vendedora**, quero ver no Radar de Risco quantas pré-vendas estão abertas e há quanto tempo estão travadas, para agir antes que o cliente seja prejudicado.

---

## Critérios de Aceite

- [ ] Dado que a vendedora tem pré-vendas com `Status = 'T'` no mês corrente, quando abrir o Radar, então uma faixa visível deve aparecer exibindo: total de pré-vendas abertas + valor total em aberto.
- [ ] Dado que existe ao menos uma pré-venda com `DtMov` há mais de **1 dia**, então essa pré-venda deve ser destacada como "travada" e a contagem deve aparecer na faixa (ex: _"3 pré-vendas abertas · 1 travada há 4 dias"_).
- [ ] Dado que não há pré-vendas abertas no período, então a faixa **não aparece** (não exibe "0 pré-vendas").
- [ ] Dado que a vendedora clica na faixa, então ela expande mostrando a listagem com as colunas: `Vendedor`, `IdMov`, `NumMov`, `DtMov`, `Dias em aberto`, `Observações`, `ValorLiquido`.
- [ ] Dado que há múltiplas vendedoras selecionadas, então as pré-vendas de todas são exibidas juntas, ordenadas por `DtMov ASC` (mais antigas primeiro).
- [ ] Dado que uma pré-venda está travada (> 2 dias), então ela aparece destacada em laranja na listagem expandida.
- [ ] O período consultado deve ser dinâmico: `DtMov >= início do mês corrente`.

---

## Dados Necessários

**Tabelas:** `Movimento`, `Cli_For`, `Vendedores`

**Colunas:**
| Campo | Tabela | Observação |
|---|---|---|
| `IdMov` | Movimento | PK do movimento |
| `NumMov` | Movimento | Número legível para o usuário |
| `DtMov` | Movimento | Data de criação da pré-venda |
| `CodVendedor` | Movimento | Código do vendedor que criou |
| `NomeVendedor` | Vendedores | Nome legível |
| `Observacoes` | Movimento | Campo livre do operador |
| `TotMov`, `PercDesconto`, `ValorFrete` | Movimento | Para calcular `ValorLiquido` |
| `Status = 'T'` | Movimento | Filtro pré-venda |
| `TipoMov IN ('2.4','2.1','2.8','2.3')` | Movimento | Apenas vendas/devoluções |
| `Inativo = 'N'` | Cli_For | Excluir clientes inativos |

**Status dos dados:** ✅ Todos disponíveis no banco atual

**Query de referência (validada pelo usuário):**
```sql
SELECT
    M.CodVendedor,
    V.NomeVendedor,
    M.IdMov,
    M.NumMov,
    M.DtMov,
    M.Observacoes,
    ROUND(
        CASE WHEN M.TipoMov IN ('2.8','2.3')
             THEN (M.TotMov * (1 - ISNULL(M.PercDesconto, 0)/100.0) * -1) + ISNULL(M.ValorFrete, 0)
             ELSE (M.TotMov * (1 - ISNULL(M.PercDesconto, 0)/100.0)) + ISNULL(M.ValorFrete, 0)
        END, 2
    ) AS ValorLiquido
FROM Movimento M WITH (NOLOCK)
INNER JOIN Cli_For CF WITH (NOLOCK) ON M.CodCliFor = CF.CodCliFor
INNER JOIN Vendedores V WITH (NOLOCK) ON V.CodVendedor = M.CodVendedor
WHERE CF.Inativo = 'N'
  AND M.TipoMov IN ('2.4','2.1','2.8','2.3')
  AND M.Status = 'T'
  AND M.DtMov >= DATEADD(DAY, 1, EOMONTH(GETDATE(), -1))  -- início do mês corrente (dinâmico)
```

---

## Comportamento Visual

### Faixa fechada (estado padrão)

```
┌─────────────────────────────────────────────────────────────┐
│  📋  3 pré-vendas abertas · R$ 4.820,00 em aberto           │
│      ⚠️ 1 travada há 4 dias                        ▼ Ver    │
└─────────────────────────────────────────────────────────────┘
```

- Cor de fundo: **amarelo âmbar** (`#FEF3C7`) se houver alguma travada; **azul claro** (`#EBF5FB`) se todas forem recentes.
- Borda esquerda colorida conforme o estado (laranja se travada, azul se ok).

### Faixa expandida (após clique)

```
┌─────────────────────────────────────────────────────────────┐
│  📋  3 pré-vendas abertas · R$ 4.820,00 em aberto    ▲ Fechar│
├──────────┬──────────┬────────────┬───────┬──────────────────┤
│ Vendedor │  NumMov  │   DtMov    │ Dias  │   ValorLiquido   │
├──────────┼──────────┼────────────┼───────┼──────────────────┤
│ Ana      │ 001234   │ 05/06/2026 │  4d ⚠️│    R$ 1.200,00   │  ← laranja
│ Ana      │ 001456   │ 07/06/2026 │  2d   │    R$ 2.100,00   │
│ Ana      │ 001478   │ 09/06/2026 │  0d   │    R$ 1.520,00   │
└──────────┴──────────┴────────────┴───────┴──────────────────┘
│ Observações: [campo expandível por linha]                    │
└─────────────────────────────────────────────────────────────┘
```

- Ordenação: mais antigas primeiro (maior risco de travar).
- Pré-vendas com > 1 dia: linha destacada em laranja claro.
- Coluna `Observações` exibida como texto colapsável por linha (não quebrar o layout).

---

## Posição no Radar

A faixa deve aparecer **entre os KPIs do mês e os cards de status** (Crítico / Atenção / Ativo / Perdido / Novo). Só é renderizada se houver ao menos 1 pré-venda para os vendedores selecionados.

```
[KPIs: Pedidos | Faturado | Rentabilidade]
─────────────────────────────────────────
[Faixa Pré-Vendas]   ← NOVO
─────────────────────────────────────────
[Cards: Crítico | Atenção | Ativo | Perdido | Novo]
[Listagem de clientes...]
```

---

## Impacto na Arquitetura

### ETL (`scripts/etl_cache.py`)
- Nova função `etl_prevendas(conn)` — **full load sempre** (estado corrente, muda o tempo todo).
- Salva em `cache/prevendas.parquet`.
- TTL do cache Streamlit: **30 minutos** (mesmo padrão do radar).
- Adicionar chamada em `__main__` junto com `etl_pedidos_pendentes`.

> **Atenção:** `pedidos_pendentes.parquet` existente usa `TipoMov = 'P'` (pedidos aguardando faturamento) — contexto diferente. Não reutilizar.

### Dashboard (`dashboards/radar_vendedor.py`)
- Nova função `_load_prevendas_cache()` — carrega o parquet e filtra por `CodVendedor`.
- Nova função `render_faixa_prevendas(df_prev, vendedores_sel)` — encapsula toda a lógica visual.
- Inserir chamada à função entre os KPIs e os cards de status.
- Implementar com `st.expander` (interação de abrir/fechar nativa do Streamlit).

### Sem impacto em:
- `app.py` (dashboard principal)
- Queries de faturamento existentes (pré-vendas continuam excluídas do faturamento)
- Lógica de classificação de risco dos clientes

---

## Definições e Regras

| Conceito | Regra |
|---|---|
| Pré-venda | `Movimento.Status = 'T'` + `TipoMov IN ('2.4','2.1','2.8','2.3')` |
| Travada | `DtMov` há mais de **1 dia corrido** (DATEDIFF dia) — 2+ dias é problema |
| Período | Mês corrente: `DtMov >= primeiro dia do mês atual` |
| ValorLiquido | Mesma fórmula canônica do sistema (TotMov com desconto e frete) |

> **Regra validada:** Pré-venda criada no mesmo dia é normal. Com **1 dia parado já é travada** (alerta). Com **2+ dias é problema** (destaque mais forte).
