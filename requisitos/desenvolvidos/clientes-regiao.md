# Clientes — Adicionar Região

**Status**: `a-desenvolver`
**Criado em**: 2026-05-09
**Prioridade**: Should Have
**Esforço estimado**: Pequeno (<2h)

---

## Dor de Negócio

Não há como analisar a distribuição geográfica dos clientes por região de atendimento, dificultando o planejamento de rotas, a avaliação de cobertura territorial e a identificação de regiões com baixo faturamento.

## História de Usuário

> Como supervisor comercial, quero filtrar e visualizar clientes por região, para que eu possa avaliar cobertura de atendimento e identificar áreas com potencial de crescimento.

## Critérios de Aceite

- [ ] O campo `Regiao.NomeRegiao` (via `Cli_For.IdRegiao`) deve ser trazido no ETL e salvo no Parquet
- [ ] Filtro de "Região" disponível na sidebar do `app.py` (multiselect)
- [ ] O filtro de região deve impactar todas as abas que exibem dados de clientes
- [ ] Na aba Clientes (tab6), adicionar coluna "Região" na tabela de busca
- [ ] Clientes sem região cadastrada exibem "Sem Região"
- [ ] Gráfico de faturamento por região (barras horizontais) na aba Clientes

## Dados necessários

- Tabelas: `Cli_For` (coluna `IdRegiao`), `Regiao` (colunas `IdRegiao`, `NomeRegiao`, `CodRegiao`)
- Status: ✅ Disponível — tabela `Regiao` existe com `NomeRegiao` e `Cli_For.IdRegiao` já é FK

## Impacto na arquitetura atual

- Modificado: `scripts/etl_cache.py` — JOIN com `Regiao` no ETL de clientes
- Modificado: `dashboards/app.py` — filtro sidebar, coluna em tab6, gráfico em tab6
- Sem impacto em outras abas além de clientes

## Notas

Verificar se as regiões cadastradas no Cronos estão atualizadas e refletem a realidade da operação atual da GM Limpeza. Regiões inativas (`Inativa = 'S'`) devem ser excluídas do filtro.
