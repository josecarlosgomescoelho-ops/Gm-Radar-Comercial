# Seleção Múltipla de Vendedores no Radar de Risco

**Status**: `a-desenvolver`
**Criado em**: 2026-04-21
**Prioridade**: Must Have
**Esforço estimado**: Médio (4-6h)

---

## Dor de Negócio

O supervisor precisa visualizar a carteira de risco de toda a sua equipe de uma vez, sem precisar trocar de vendedor manualmente a cada consulta. Hoje o `st.selectbox` força selecionar uma vendedora por vez, tornando a visão gerencial inviável.

## História de Usuário

> Como supervisor, quero selecionar uma, várias ou todas as vendedoras ao mesmo tempo no Radar de Risco, para ter uma visão consolidada da carteira de risco da minha equipe sem precisar navegar entre seleções.

## Critérios de Aceite

- [ ] O `st.selectbox` de vendedor é substituído por `st.multiselect` na sidebar
- [ ] Existe uma opção "Todas as vendedoras" que, quando marcada, seleciona todas automaticamente
- [ ] Quando uma vendedora está selecionada: header exibe "Radar de Risco — [Nome Vendedora]"
- [ ] Quando múltiplas vendedoras selecionadas: header exibe "Radar de Risco — [N] Vendedoras"
- [ ] Quando todas selecionadas: header exibe "Radar de Risco — Equipe Completa"
- [ ] Cada card de cliente exibe o nome da vendedora responsável quando há mais de uma selecionada
- [ ] O Resumo de Ações no rodapé agrega os totais de todas as vendedoras selecionadas e omite o nome individual
- [ ] Se nenhuma vendedora selecionada: exibe aviso "Selecione ao menos uma vendedora" e para execução
- [ ] A performance com múltiplas vendedoras é aceitável (queries paralelas ou query única com IN)

## Dados Necessários

| Campo | Tabela | Status |
|---|---|---|
| CodVendedor, NomeVendedor | Vendedores | ✅ Disponível |
| CodFunc (vínculo cliente-vendedor) | Cli_For | ✅ Disponível |

**Impacto nas queries**: `q_historico_cliente`, `q_produtos_habituais` e `q_rentabilidade_cliente` recebem hoje um único `cod_vendedor`. Precisam ser adaptadas para aceitar uma lista e usar `IN (...)` ou ser chamadas em loop com consolidação no pandas.

## Impacto na Arquitetura

- `radar_vendedor.py` — sidebar: substituir `selectbox` por `multiselect` (linha 501-506)
- Adaptar as 3 queries cached para aceitar tupla de códigos (ou criar versões `_multi`)
- Adicionar coluna `Vendedor` no `df_clientes` para exibir no card quando modo multi
- Adaptar textos dinâmicos: header (linha 543), resumo de ações (linhas 728-743), rodapé (linha 750)
- `classificar_clientes()` permanece igual — opera sobre o df consolidado

## Notas / Decisões Pendentes

- Definir se o cache muda de chave para tuple (hashable) ou se as queries individuais são chamadas em loop e concatenadas — loop é mais simples e reutiliza o cache existente por vendedora
- "Todas as vendedoras" deve considerar apenas vendedoras ativas (`Inativo = 'N'` e `Tipo = 'V'`)
