# ETL com NOLOCK — Proteção Total do Banco de Produção

**Status**: `desenvolvido`
**Criado em**: 2026-04-24
**Prioridade**: Must Have
**Esforço estimado**: Pequeno (<2h)

---

## Dor de Negócio

O ETL roda às 01h com queries pesadas no banco de produção do ERP (Cronos). Embora o horário reduza o risco, qualquer query de analytics sem hint de lock pode competir com rotinas noturnas do próprio sistema (backup, fechamento, reindexação), causando lentidão ou travamento. O objetivo é garantir impacto zero no banco, independente do horário.

## História de Usuário

> Como gestor, quero que o ETL de analytics nunca interfira na operação do sistema Cronos, para que o banco de produção fique protegido mesmo que o ETL rode em horário incorreto ou em situação de falha.

## Critérios de Aceite

- [ ] Todas as queries do `scripts/etl_cache.py` usam `WITH (NOLOCK)` em cada tabela referenciada
- [ ] O ETL é testado e confirma que os totais de faturamento permanecem consistentes após a mudança
- [ ] Documentar no cabeçalho do `etl_cache.py` o motivo do uso de NOLOCK (analytics em banco operacional, horário noturno, risco de dirty read aceitável)
- [ ] Solicitar ao suporte Inovare/Cronos confirmação do horário das rotinas noturnas (backup, fechamento) para validar que 01h é seguro — ajustar cron se necessário
- [ ] Solicitar ao suporte verificação e criação de índice em `Movimento.DataFaturamento` — reduz o tempo da query `itens` de ~54s para < 5s

## Dados Necessários

Nenhum dado novo — alteração exclusiva nas queries do ETL existente.

## Impacto na Arquitetura

- **Modificado**: `scripts/etl_cache.py` — adicionar `WITH (NOLOCK)` em todas as cláusulas `FROM` e `JOIN`
- **Ação externa**: solicitar ao suporte Cronos/Inovare verificação de índice e horário de rotinas noturnas
- Nenhum impacto no dashboard ou nos Parquets gerados

## Exemplo da mudança

```sql
-- Antes
FROM ItensMov IM
INNER JOIN Movimento M ON IM.IdMov = M.IdMov

-- Depois
FROM ItensMov IM WITH (NOLOCK)
INNER JOIN Movimento M WITH (NOLOCK) ON IM.IdMov = M.IdMov
```

## Notas

- NOLOCK elimina lock contention mas permite dirty reads (linhas não commitadas)
- Risco prático é nulo: o ETL roda às 01h, sem operadores ativos
- Mesmo que ocorra um dirty read pontual, o dado é corrigido no ETL do dia seguinte
- **Não usar NOLOCK** em queries de relatórios fiscais, conciliação bancária ou fechamento contábil
