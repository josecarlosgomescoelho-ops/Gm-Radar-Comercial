# Fix — ETL ignora TipoMov '2.5', subnotificando pedidos e faturamento no Radar

**Status**: `desenvolvido`
**Criado em**: 2026-05-21
**Implementado em**: 2026-05-21
**Prioridade**: Must Have
**Esforço estimado**: Pequeno (<1h)

---

## Dor de Negócio

O Radar de Vendedor exibe pedidos e faturamento do mês atual **abaixo do real** para todos os vendedores. Validação com a vendedora Karla (CodVendedor `00012`) em maio/2026:

| Fonte | Pedidos | Faturamento |
|---|---|---|
| SQL direto no banco (correto) | **121** | **R$ 137.381,15** |
| Radar de Vendedor (atual) | 89 | ~R$ 93.000 |
| Diferença | −32 pedidos | −R$ 44.381 |

O número exibido no radar gera desconfiança e impede o supervisor de acompanhar a performance real do vendedor no mês.

## Causa Raiz

### 1. TipoMov `'2.5'` ausente no ETL

A investigação das `NaturezaOperacao` revelou que vendas regulares com NF-e são geradas com dois TipoMov distintos:

| TipoMov | CFOP | ClasseMov | ICMS | Pedidos (Karla/maio) | Valor |
|---|---|---|---|---|---|
| `2.4` | 5.102 / 6.102 | N | Sim | 110 | R$ 125.991 |
| `2.5` | 5.102 | N | Sim | 4 | R$ 5.585 |
| `2.1` | 5.102 | N | Não | 9 | R$ 5.754 |

`2.5` tem `ClasseMovimento = N`, `TipoMovimento = S` (saída), ICMS calculado — é uma venda de NF-e indistinguível de `2.4` do ponto de vista fiscal. O ETL atual filtra apenas `IN ('2.4','2.1','2.8','2.3')`, excluindo `2.5` integralmente.

### 2. TipoMov `'2.7'` — descartado corretamente

Também investigado, `2.7` tem exatamente os mesmos 108 pedidos que `2.4` (mesmo `PercDescontoMedio`, mesmo `IdNaturezaOperacao`). São registros financeiros/de estoque gerados para a mesma venda — incluí-los causaria dupla contagem. O ETL já os exclui corretamente.

### 3. Gap residual (após adicionar `2.5`)

Adicionando `2.5` ao ETL, a estimativa pelo banco fica:
- `2.4` + `2.1` + `2.5` + `2.8` = ~121 pedidos, ~R$ 137.381

O radar atual mostra 89 pedidos (~R$93k), gap de 32 pedidos/R$44k ainda a ser confirmado. Parte pode ser atraso no parquet (watermark desatualizado) ou filtro de data no dashboard. Isso deve ser reavaliado após o deploy desta correção com parquet reprocessado.

## História de Usuário

> Como supervisor, quero que o Radar exiba o número de pedidos e o faturamento do mês idênticos ao relatório do ERP, para acompanhar a performance real sem precisar cruzar fontes manualmente.

## Critérios de Aceite

- [ ] `etl_movimentos`: `TipoMov IN ('2.4','2.1','2.8','2.3','2.5')`
- [ ] `etl_radar_clientes`: `TipoMov IN ('2.4','2.1','2.8','2.3','2.5')` (ambos os SQLs: full e incremental)
- [ ] Após reprocessamento do parquet, Karla (00012) passa a exibir ≥ 121 pedidos e ≥ R$ 137.381 no Radar para maio/2026
- [ ] Devoluções `2.8` e `2.3` continuam com `ValorLiquido` negativo — sem regressão
- [ ] `2.7` continua fora dos filtros (evitar dupla contagem)

## Solução Técnica

### `etl_movimentos` — `scripts/etl_cache.py`

Localizar a linha:
```python
WHERE M.TipoMov IN ('2.4','2.1','2.8','2.3')
```
Substituir por:
```python
WHERE M.TipoMov IN ('2.4','2.1','2.8','2.3','2.5')
```

Essa string aparece em `_base` dentro de `etl_movimentos()` — alterar uma vez cobre os dois SQLs (full e incremental).

### `etl_radar_clientes` — `scripts/etl_cache.py`

Mesma substituição em `sql_full` e `sql_inc` dentro de `etl_radar_clientes()`:
```python
-- antes
AND M.TipoMov IN ('2.4','2.1','2.8','2.3')
-- depois
AND M.TipoMov IN ('2.4','2.1','2.8','2.3','2.5')
```

### Reprocessamento obrigatório

Após a alteração, deletar os parquets afetados e rodar o ETL em full load para reprocessar o histórico com o filtro correto:

```bash
rm cache/movimentos.parquet cache/radar_clientes.parquet
python scripts/etl_cache.py
```

## Impacto na Arquitetura

- **Modificado**: `scripts/etl_cache.py` — 3 linhas alteradas
- **Reprocessamento**: `movimentos.parquet` e `radar_clientes.parquet` (full load)
- **Sem impacto** em `app.py`, `radar_vendedor.py`, outros parquets ou banco de produção

## Notas

- `2.5` confirmado com `ClasseMovimento = N` e `TipoMovimento = S` na tabela `NaturezaOperacao` — é venda fiscal legítima
- `2.7` investigado e descartado: duplo registro do mesmo pedido (confirmado por `PercDescontoMedio` idêntico ao `2.4` para os mesmos 108 pedidos de Karla)
- O gap residual (89 → 121 pedidos) pode ter componente adicional não identificado ainda; reavaliar após deploy
