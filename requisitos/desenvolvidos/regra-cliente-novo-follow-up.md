# Regra "NOVO" — Identificar Cliente com Primeira Compra nos Últimos 30 Dias

**Status**: `a-desenvolver`
**Criado em**: 2026-05-09
**Prioridade**: Must Have
**Esforço estimado**: Médio (2–8h)

---

## Dor de Negócio

Clientes que compraram pela primeira vez nos últimos 30 dias são os mais propensos ao churn. Sem identificação automática, a vendedora não sabe quem são os novos clientes que precisam de follow-up para fidelização. A falta desse acompanhamento resulta em "compra única" — o cliente experimenta, não é retido, e some.

## História de Usuário

> Como vendedora, quero ver quais clientes da minha carteira compraram pela primeira vez nos últimos 30 dias, para que eu priorize o follow-up de fidelização antes que eles somam após a primeira compra.

## Critérios de Aceite

- [ ] Definição de "NOVO": cliente cuja **primeira compra em toda a base histórica** ocorreu há no máximo 30 dias (não apenas "comprou nos últimos 30 dias" — deve ser a primeira compra dele no sistema)
- [ ] O status "NOVO" deve aparecer como badge/tag no radar (`radar_vendedor.py`) ao lado do nome do cliente
- [ ] Na aba Clientes (`app.py` tab6), adicionar coluna "Status" com valor "NOVO" e destaque em verde para esses clientes
- [ ] Filtro rápido na aba Clientes: "Mostrar apenas NOVOS" (toggle/checkbox)
- [ ] Card de KPI no topo do radar: "X clientes NOVOS na carteira" com link para lista
- [ ] Script de sugestão de follow-up: ao clicar no badge "NOVO", exibir mensagem modelo: "Primeira compra em [data]. Sugerir 2ª compra até [data + 15 dias]"
- [ ] Clientes "NOVOS" devem ser excluídos do status CRÍTICO mesmo que estejam sem compra há mais de 45 dias (pois acabaram de entrar)

## Dados necessários

- Tabelas: `Movimento` (via Parquet `movimentos.parquet`)
- Colunas: `CodCliFor`, `DataEmissao` — calcular `MIN(DataEmissao)` por cliente em toda a base
- Status: ✅ Disponível — histórico completo disponível no Parquet

## Impacto na arquitetura atual

- Modificado: `scripts/etl_cache.py` — calcular e salvar `DataPrimeiraCompra` por cliente no Parquet
- Modificado: `dashboards/radar_vendedor.py` — badge "NOVO" nos cards de cliente + KPI no topo
- Modificado: `dashboards/app.py` — coluna e filtro em tab6
- Atenção: interação com a regra de status do radar — NOVO não pode ser CRÍTICO

## Notas

A `DataPrimeiraCompra` deve ser calculada sobre toda a base histórica disponível, não apenas o período filtrado. Isso significa que o cálculo deve ser feito no ETL usando o Parquet completo antes de qualquer filtro de período. Guardar como campo separado no Parquet de clientes.
