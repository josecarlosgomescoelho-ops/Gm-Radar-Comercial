# Pedidos Pendentes — Exibir Movimentos com TipoMov "P" no Filtro Ativo

**Status**: `a-desenvolver`
**Criado em**: 2026-05-09
**Prioridade**: Must Have
**Esforço estimado**: Médio (2–8h)

---

## Dor de Negócio

Pedidos digitados no ERP mas ainda não faturados (`TipoMov = 'P'` — Pedido pendente) não aparecem no dashboard, que exibe apenas vendas faturadas. Gestores e supervisores não conseguem acompanhar a carteira de pedidos em aberto, perdendo visibilidade sobre o que está prestes a ser faturado.

## História de Usuário

> Como supervisor comercial, quero ver os pedidos pendentes de faturamento filtrados pelo vendedor selecionado, para que eu acompanhe a carteira em aberto e antecipe projeções de faturamento.

## Critérios de Aceite

- [ ] Exibir pedidos com `TipoMov = 'P'` (ou o campo/valor correto — confirmar com operação) na nova seção "Pedidos Pendentes"
- [ ] A listagem deve respeitar o filtro de vendedor ativo na sidebar
- [ ] Colunas mínimas: Data do Pedido, Nº Pedido, Cliente, Vendedor, Valor Total, Qtd. Itens
- [ ] Exibir total consolidado: "X pedidos pendentes · R$ Y,YY em aberto"
- [ ] Pedidos pendentes devem ser buscados **diretamente do banco** (não do Parquet, pois mudam ao longo do dia) com cache curto de 15 minutos
- [ ] Localização: nova seção na aba Detalhamento (tab4) OU nova aba "📋 Pedidos" — a definir
- [ ] Dado que não há pedidos pendentes para o filtro selecionado, exibir mensagem "Nenhum pedido pendente no momento"

## Dados necessários

- Tabelas: `Movimento`, `Cli_For`, `Vendedores`
- Colunas: `TipoMov`, `Status`, `DataEmissao`, `NumMov`, `CodCliFor`, `NomeCliFor`, `CodVendedor`, `ValorTotal`
- Status: ⚠️ Parcialmente disponível — confirmar se `TipoMov = 'P'` é o identificador correto para pedido pendente no Cronos da GM Limpeza (alternativa: `Status = 'P'` ou `CodTipoDoc` específico)

## Impacto na arquitetura atual

- Novo: função `q_pedidos_pendentes(vendedores)` em `app.py` com cache TTL=900s (15min)
- Modificado: `app.py` — nova seção em tab4 ou nova tab9
- Risco: query direta ao banco de produção — usar `WITH (NOLOCK)` obrigatoriamente
- Novo campo no ETL: avaliar se faz sentido incluir pendentes no Parquet (volátil demais)

## Notas

Antes de implementar, validar com a operação: qual `TipoMov` representa pedido pendente de faturamento no Cronos (prováveis: `'P'`, `'PE'`, ou um `CodTipoDoc` específico). Também verificar se pedidos cancelados devem ser excluídos via `Status`.
