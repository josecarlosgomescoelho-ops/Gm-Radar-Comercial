# ETL Incremental com Watermark

**Status**: `desenvolvido`
**Criado em**: 2026-04-24
**Prioridade**: Should Have
**Esforço estimado**: Médio (2–8h)

---

## Dor de Negócio

O ETL atual recarrega **todos os dados dos últimos 13 meses** a cada execução — 172k linhas de itens em ~54 segundos. Esse volume cresce proporcionalmente ao histórico acumulado. Além disso, 99% dos dados já estão nos Parquets do dia anterior; reprocessar tudo é desperdício de tempo e carga no banco. Com watermark, o ETL carrega apenas os dados novos desde a última execução — caindo de 54s para poucos segundos.

## História de Usuário

> Como responsável pelo sistema, quero que o ETL carregue apenas os dados novos desde a última execução, para que o tempo de processamento e a carga no banco sejam mínimos, mesmo com anos de histórico acumulado.

## Critérios de Aceite

- [ ] Na primeira execução (sem Parquets), o ETL roda em modo **full load** (comportamento atual)
- [ ] Nas execuções seguintes (Parquets existentes), o ETL roda em modo **incremental**: consulta apenas registros com `DataFaturamento > watermark`
- [ ] O watermark é a data do registro mais recente no Parquet existente, lida diretamente do arquivo antes de consultar o banco
- [ ] Após carregar os dados incrementais, o ETL faz **merge** (append + deduplicação por chave) com o Parquet existente, descartando registros com mais de 13 meses
- [ ] O log registra claramente o modo de execução: `[itens] INCREMENTAL: watermark=2026-04-23, 847 linhas novas` ou `[itens] FULL LOAD: 172008 linhas`
- [ ] Em caso de falha no incremental, o ETL re-executa em modo full load automaticamente como fallback
- [ ] O tempo de execução em modo incremental deve ser < 5s para uma janela de 1 dia de dados

## Lógica de Watermark

```
watermark = MAX(DataFaturamento) do Parquet existente

Query incremental:
  WHERE M.DataFaturamento > watermark
    AND M.DataFaturamento <= GETDATE()

Merge:
  df_novo = query_incremental()
  df_existente = pd.read_parquet(...)
  df_merged = pd.concat([df_existente, df_novo])
  df_merged = df_merged.drop_duplicates(subset=chave_primaria)
  df_merged = df_merged[df_merged['DataFaturamento'] >= corte_13_meses]
  df_merged.to_parquet(...)
```

## Chaves primárias para deduplicação por Parquet

| Parquet | Chave de deduplicação |
|---|---|
| `movimentos.parquet` | `IdMov` |
| `itens.parquet` | `IdMov` + `IdProduto` |
| `radar_clientes.parquet` | `CodCliFor` + `CodVendedor` + `DataFaturamento` + `IdMov` |
| `radar_produtos.parquet` | `CodCliFor` + `CodVendedor` + `Produto` (reagregar após merge) |
| `radar_rent_cli.parquet` | `CodCliFor` + `CodVendedor` (reagregar após merge) |
| `vendedores.parquet` | `CodVendedor` (sempre full — tabela pequena) |
| `supervisores.parquet` | `CodVendedor` (sempre full — tabela pequena) |

## Observação sobre reagregação

Para `radar_produtos` e `radar_rent_cli` (dados já agregados), o watermark não se aplica diretamente — são sempre recalculados a partir da janela de 6 meses completa. Apenas `movimentos`, `itens` e `radar_clientes` se beneficiam do incremental.

## Impacto na Arquitetura

- **Modificado**: `scripts/etl_cache.py` — adicionar lógica de watermark, merge e modo dual (full/incremental)
- Nenhum impacto no dashboard — os Parquets mantêm o mesmo schema
- Nenhum impacto no banco — as queries incrementais são mais leves, não mais pesadas

## Dependência

Implementar após `etl-nolock-protecao-banco.md` — o NOLOCK deve estar nas queries antes de rodar incremental, para garantir consistência da leitura do watermark.
