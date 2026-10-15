# Radar — Remover Listagem de Produtos Habituais do Card do Cliente

**Status**: `a-desenvolver`
**Criado em**: 2026-05-09
**Prioridade**: Should Have
**Esforço estimado**: Pequeno (<2h)

---

## Dor de Negócio

O card de detalhe do cliente no radar exibe uma seção com listagem de produtos habituais. Essa informação polui a tela e não é usada na tomada de decisão pelo vendedor ou supervisor no contexto do radar de risco.

## História de Usuário

> Como vendedora usando o radar, quero que o card do cliente não liste os produtos habituais, para que a tela fique mais limpa e foque nas informações de risco e contato.

## Critérios de Aceite

- [ ] Remover completamente a seção/listagem de "Produtos Habituais" do card de detalhe do cliente em `radar_vendedor.py`
- [ ] Nenhuma outra informação do card deve ser afetada (status, histórico de compras, contato, etc.)
- [ ] A remoção não deve causar erros caso o código ainda tente carregar os dados de produtos — garantir que a query/lógica associada também seja removida ou desativada
- [ ] Verificar se a query de produtos habituais contribuía para carga no banco; se sim, removê-la também do ETL/cache

## Dados necessários

- Nenhum dado novo necessário — é uma remoção de funcionalidade existente
- Status: ✅ Não requer dados

## Impacto na arquitetura atual

- Modificado: `dashboards/radar_vendedor.py` — remover bloco HTML/Python que renderiza a lista de produtos no card do cliente
- Possível modificado: `scripts/etl_cache.py` ou query interna do radar — remover a busca de produtos habituais se existir
- Sem impacto em `app.py`

## Notas

Antes de remover, verificar se existe query associada carregando dados de produtos para o radar. Se sim, removê-la também para não poluir o cache com dados que não serão exibidos.
