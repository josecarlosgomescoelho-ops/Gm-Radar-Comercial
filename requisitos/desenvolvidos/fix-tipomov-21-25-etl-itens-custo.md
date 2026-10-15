# Fix — ETL de itens ignora TipoMov '2.1' e '2.5', subdimensionando custo e inflando rentabilidade

**Status**: `desenvolvido`
**Criado em**: 2026-05-21
**Implementado em**: 2026-05-21
**Prioridade**: Must Have
**Esforço estimado**: Pequeno (<1h)

---

## Dor de Negócio

O Radar de Vendedor exibe rentabilidade do mês atual muito acima da realidade. Comparação com o relatório do ERP para maio/2026:

| Fonte | Faturamento | Custo % | Rentabilidade |
|---|---|---|---|
| ERP (referência) | R$ 130.937 | ~76% | **~24%** |
| Radar atual | R$ 141.068 | ~50% | **~50%** |

Uma rentabilidade de 50% para distribuidora de produtos de limpeza é irreal e gera decisões equivocadas de gestão.

## Causa Raiz

O `etl_itens` filtra apenas `TipoMov = '2.4'` para buscar itens e custos:

```python
WHERE M.TipoMov = '2.4'
  AND M.Status NOT IN ('C','T')
  AND IM.StatusItemMov NOT IN ('C')
```

Porém, `TipoMov '2.1'` e `'2.5'` também geram registros em `ItensMov` com `CustoUnitarioItem` preenchido. Esses pedidos **entram no faturamento** (após o fix de `etl_movimentos`) mas **não têm custo capturado**, inflando artificialmente a margem.

### Evidência direta no banco (mai/2026, todos os vendedores)

```
TipoMov | Itens |  CustoTotal
--------+-------+------------
2.1     |   643 |  R$ 24.121,13   ← não capturado
2.4     | 8.389 | R$ 767.745,31   ← já capturado
2.5     |   227 |  R$ 22.249,34   ← não capturado
```

**Custo perdido no período: R$ 46.370,47** — equivalente a ~6% do custo total registrado.

## História de Usuário

> Como supervisor, quero que a rentabilidade exibida no Radar reflita o custo real de todos os pedidos faturados, para tomar decisões baseadas em margens corretas.

## Critérios de Aceite

- [ ] `etl_itens` captura itens de `TipoMov IN ('2.4','2.1','2.5')`
- [ ] Após reprocessamento, o custo total no parquet inclui os itens de `'2.1'` e `'2.5'`
- [ ] A rentabilidade no Radar se aproxima dos ~24% reportados pelo ERP para os vendedores de referência
- [ ] Devoluções (`'2.8'`, `'2.3'`) continuam fora do `etl_itens` — não têm itens detalhados relevantes para custo
- [ ] Sem regressão nos demais KPIs do radar (clientes, receita em risco)

## Solução Técnica

### `etl_itens` — `scripts/etl_cache.py`

Localizar o `_base` dentro de `etl_itens()`:

```python
# ANTES
WHERE M.TipoMov = '2.4'
  AND M.Status NOT IN ('C','T')
  AND IM.StatusItemMov NOT IN ('C')

# DEPOIS
WHERE M.TipoMov IN ('2.4','2.1','2.5')
  AND M.Status NOT IN ('C','T')
  AND IM.StatusItemMov NOT IN ('C')
```

### Reprocessamento obrigatório

`itens.parquet` existe e está em modo incremental. Deletar e rodar full load:

```bash
rm cache/itens.parquet
python scripts/etl_cache.py
```

## Impacto na Arquitetura

- **Modificado**: `scripts/etl_cache.py` — 1 linha alterada em `etl_itens()`
- **Reprocessamento**: `itens.parquet` (full load)
- **Sem impacto** em `movimentos.parquet`, `radar_clientes.parquet`, `app.py` ou banco

## Notas

- `etl_itens` é usado pela rentabilidade do radar (`radar_vendedor.py`) e pela aba Detalhamento do `app.py` — ambos se beneficiam da correção
- O gap residual de rentabilidade (após este fix) deve ser reavaliado: se o ERP inclui custos operacionais/overhead no `CustoUnitarioItem`, pode haver diferença estrutural irredutível entre as fontes
- `'2.7'` foi investigado e descartado — é registro financeiro/estoque do mesmo pedido `'2.4'` (dupla contagem); ver [[fix-tipomov-25-etl-movimentos]]
