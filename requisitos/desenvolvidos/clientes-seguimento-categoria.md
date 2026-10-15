# Clientes — Adicionar Segmento/Categoria (Condomínio, Hospital, Academia, etc.)

**Status**: `a-desenvolver`
**Criado em**: 2026-05-09
**Prioridade**: Should Have
**Esforço estimado**: Médio (2–8h)

---

## Dor de Negócio

Não é possível filtrar ou comparar clientes por tipo de negócio (condomínio, hospital, academia, restaurante, etc.), impedindo análises segmentadas de rentabilidade, ticket médio por segmento e identificação de oportunidades por verticais.

## História de Usuário

> Como gestor comercial, quero ver e filtrar clientes por segmento de negócio, para que eu possa entender quais verticais têm maior rentabilidade e direcionar esforços de prospecção.

## Critérios de Aceite

- [ ] O campo `CategoriaCliFor.Denominacao` (via `Cli_For.IdCategoriaCliFor`) deve ser trazido no ETL e salvo no Parquet de clientes/movimentos
- [ ] Filtro de "Segmento" disponível na sidebar do `app.py` (multiselect, abaixo do filtro de vendedor)
- [ ] O filtro de segmento deve impactar todas as abas que exibem dados de clientes: Visão Geral, Clientes, Pivot Mensal, Radar
- [ ] Na aba Clientes (tab6), adicionar coluna "Segmento" na tabela de busca
- [ ] Adicionar novo card de KPI ou gráfico de barras: "Faturamento por Segmento" na aba Clientes
- [ ] Clientes sem segmento cadastrado devem aparecer como "Não Classificado"
- [ ] Dado que há clientes sem `IdCategoriaCliFor`, quando o filtro de segmento for aplicado, então clientes sem categoria devem ser excluídos do resultado (não mostrar "Não Classificado" como resultado)

## Dados necessários

- Tabelas: `Cli_For` (coluna `IdCategoriaCliFor`), `CategoriaCliFor` (colunas `IdCategoriaCliFor`, `Denominacao`)
- Status: ✅ Disponível — tabela `CategoriaCliFor` existe e `Cli_For` já tem a FK

## Impacto na arquitetura atual

- Modificado: `scripts/etl_cache.py` — incluir JOIN com `CategoriaCliFor` no ETL de clientes
- Modificado: `dashboards/app.py` — filtro na sidebar, coluna na tabela de clientes, novo gráfico em tab6
- Modificado: `dashboards/radar_vendedor.py` — opcional: exibir segmento no card do cliente

## Notas

Verificar se as categorias cadastradas no Cronos da GM Limpeza já refletem os segmentos esperados (Condomínio, Hospital, Academia) ou se o cadastro precisa ser atualizado no ERP antes de implementar o filtro.
