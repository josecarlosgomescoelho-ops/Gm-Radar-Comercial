# KPIs — Qtd. Pedidos do Mês Atual, Rentabilidade % e Total Faturado R$

**Status**: `a-desenvolver`
**Criado em**: 2026-05-09
**Prioridade**: Must Have
**Esforço estimado**: Pequeno (<2h)

---

## Dor de Negócio

No radar de vendedores e nas visões por cliente, não há um resumo rápido do mês atual: quantos pedidos foram feitos, qual a rentabilidade e quanto faturou. O gestor precisa alternar entre abas para construir essa visão manualmente.

## História de Usuário

> Como gestor comercial, quero ver no topo do radar e na ficha do cliente os três KPIs do mês atual (pedidos, rentabilidade % e faturamento R$), para que eu tenha um contexto imediato de performance sem precisar navegar por abas.

## Critérios de Aceite

- [ ] KPIs fixos para **mês atual** (independente do filtro de período do dashboard principal):
  - **Qtd. Pedidos do Mês**: count de pedidos faturados no mês corrente (`DataEmissao` entre 1º e hoje)
  - **Rentabilidade %**: `(Margem / Receita) * 100` do mês corrente
  - **Total Faturado R$**: soma de `ValorLiquido` do mês corrente
- [ ] Exibidos como cards KPI no topo do radar (`radar_vendedor.py`), acima dos cards de status dos clientes
- [ ] Os mesmos KPIs devem aparecer no card expandido do cliente (detalhe por cliente no radar)
- [ ] Quando filtrado por vendedor, os KPIs refletem apenas o vendedor selecionado
- [ ] Valores zerados exibem "—" em vez de "R$ 0,00" para evitar alarme falso

## Dados necessários

- Tabelas: `Movimento`, `ItensMov` (via Parquets `movimentos.parquet` e `itens.parquet`)
- Colunas: `DataEmissao`, `ValorLiquido`, `CustoTotal`, `CodVendedor`
- Status: ✅ Disponível — dados já carregados no cache

## Impacto na arquitetura atual

- Modificado: `dashboards/radar_vendedor.py` — novos cards KPI no topo + campo no card de cliente
- Sem nova query necessária — calcular a partir dos Parquets já carregados filtrando por mês atual
- Sem impacto em `app.py` ou ETL

## Notas

Mês atual = `ano == hoje.year AND mês == hoje.month`. Calcular antes do loop de cards para evitar recomputação por cliente. Atenção: rentabilidade pode ser negativa em meses com devoluções — exibir em vermelho se < 0%.
