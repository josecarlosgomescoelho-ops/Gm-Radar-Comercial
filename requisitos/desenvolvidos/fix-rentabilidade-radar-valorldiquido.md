# Fix — Rentabilidade no Radar usa ReceitaItem em vez de ValorLiquido

**Status**: `desenvolvido`
**Criado em**: 2026-05-17
**Implementado em**: 2026-05-17
**Prioridade**: Must Have
**Esforço estimado**: Pequeno (<1h)

---

## Dor de Negócio

O KPI **"Rentabilidade — mês atual"** no Radar de Vendedor exibe valores errados — inclusive **negativos** — para vendedores com rentabilidade real positiva.

**Exemplo confirmado em dados (2026-05-17):**

| | Valor |
|---|---|
| Vendedora | Alineide (CodVendedor 01180) |
| Rentabilidade exibida no radar | **-9,9%** |
| Rentabilidade real (cálculo correto) | **23,78%** |
| Faturamento real (ValorLiquido/TotMov) | R$ 38.825,37 |
| Faturamento usado pelo radar (ReceitaItem) | R$ 27.455,59 |
| Custo (CustoItem) | R$ 30.179,18 |

O número errado gera desconfiança no sistema e pode levar a decisões equivocadas de gestão.

## Causa Raiz

O `radar_vendedor.py` calcula o faturamento mensal como:

```python
_rec_bruto = float(_itens_mes["ReceitaItem"].sum())   # ERRADO
_kpi_rent_pct = (_rec_bruto - _cst_mes) / _rec_bruto * 100
```

`ReceitaItem` é calculado no ETL como `Qtd × PrecoUnit × (1 - PercDescontoItem / 100)`.
O campo `ItensMov.PrecoUnit` **não é o preço real de venda** — é o preço de tabela/base do ERP.
O preço real negociado está em `Movimento.TotMov` (→ `ValorLiquido` no parquet).

A diferença para Alineide em maio: **R$ 11.369,78 (29% a menos que o real)**, o que inverte a margem de positiva para negativa.

O `app.py` já resolve isso corretamente em `q_rentabilidade_vendedor`:
```python
Faturamento = ValorLiquido.sum()   # de movimentos.parquet
CustoTotal  = CustoItem.sum()      # de itens.parquet
Margem      = Faturamento - CustoTotal
RentPerc    = Margem / Faturamento * 100
```

## História de Usuário

> Como supervisor, quero que o radar exiba a rentabilidade real do vendedor no mês, para tomar decisões baseadas em números corretos e não perder confiança no sistema.

## Critérios de Aceite

- [ ] O KPI "Rentabilidade — mês atual" usa `ValorLiquido` de `movimentos.parquet` como faturamento, não `ReceitaItem` de `itens.parquet`
- [ ] Devoluções (TipoMov `'2.8'` e `'2.3'`) são automaticamente contempladas pelo `ValorLiquido` negativo — sem lógica de ajuste separada
- [ ] TipoMov `'2.1'` (vendas diretas sem item detalhado) também é contabilizado no faturamento
- [ ] O resultado para Alineide (CodVendedor 01180) em maio/2026 passa de **-9,9% para ~23,8%**
- [ ] O cálculo é idêntico ao que `app.py` produz na aba Detalhamento
- [ ] O KPI "Faturado — mês atual" também passa a usar `ValorLiquido` (consistência)

## Solução Técnica

### 1. Adicionar loader de `movimentos.parquet` no radar

```python
@st.cache_data(ttl=1800)
def _load_mov_cache():
    p = CACHE_DIR / "movimentos.parquet"
    if not p.exists():
        return None
    return pd.read_parquet(p)
```

### 2. Substituir o bloco de KPI (linhas ~714–753)

**Remover** o bloco atual que usa `ReceitaItem` e o ajuste manual de devoluções.

**Substituir por:**

```python
_mov_all = _load_mov_cache()
if _mov_all is not None:
    _mask_mov = (
        (_mov_all["DataFaturamento"].dt.year  == _hoje_ts.year) &
        (_mov_all["DataFaturamento"].dt.month == _hoje_ts.month) &
        (_mov_all["CodVendedor"].isin(vendedores_sel))
    )
    _mov_mes = _mov_all[_mask_mov]
    if not _mov_mes.empty:
        _fat_mes  = float(_mov_mes["ValorLiquido"].sum())
        _ped_mes  = int(_mov_mes["IdMov"].nunique())
        _kpi_pedidos = _ped_mes or None
        if _fat_mes > 0:
            _kpi_fat_mes = _fat_mes
            # custo continua de itens.parquet (correto)
            _itens_mes = _load_radar_itens()
            if _itens_mes is not None:
                _mask_ite = (
                    (_itens_mes["DataFaturamento"].dt.year  == _hoje_ts.year) &
                    (_itens_mes["DataFaturamento"].dt.month == _hoje_ts.month) &
                    (_itens_mes["CodVendedor"].isin(vendedores_sel))
                )
                _cst_mes = float(_itens_mes[_mask_ite]["CustoItem"].sum())
                _kpi_rent_pct = (_fat_mes - _cst_mes) / _fat_mes * 100
```

## Impacto na Arquitetura

- **Modificado**: `dashboards/radar_vendedor.py` — bloco de KPI de ~40 linhas
- **Nenhuma mudança** no ETL, parquets, banco ou `app.py`
- **Nenhum impacto** em outras métricas do radar (cards de clientes, receita em risco, etc.)

## Notas

- O `movimentos.parquet` já existe no cache e é carregado pelo `app.py` — não há overhead de ETL
- O ajuste manual de devoluções (bloco `_mask_dev`) deve ser **removido**: devoluções já estão como `ValorLiquido` negativo em `movimentos.parquet`, o ajuste separado era um workaround incompleto (só capturava TipoMov `'2.8'`, ignorava `'2.3'`)
- `ReceitaItem` continua sendo útil em outros contextos (análise de produto, margem por item), mas **não deve ser usada como proxy de faturamento total**
