# ETL Intraday — Atualização do Radar Durante o Dia Comercial

**Status**: `a-desenvolver`
**Criado em**: 2026-04-30
**Prioridade**: Must Have
**Esforço estimado**: Pequeno (<2h)

---

## Dor de Negócio

Vendedoras reclamam que clientes continuam como **CRÍTICO** no radar mesmo após realizarem vendas. A investigação nos dados confirmou a causa raiz:

> O ETL roda **uma vez por dia às 01h**. Vendas faturadas após 01h só aparecem no radar **no dia seguinte às 01h**. Durante todo o horário comercial (08h–18h), o radar exibe dados de até 23 horas atrás.

**Evidência dos dados (Parquet — 2026-04-30):**
- 1.485 pares cliente/vendedor com status CRÍTICO no radar
- 0 desses têm compra recente em `movimentos.parquet` — o ETL está correto, o problema é a defasagem
- Vendas feitas após 01h de hoje ainda não estão no cache

**Cenário real:** vendedora liga para cliente CRÍTICO às 09h, fecha a venda, o ERP fatura. O cliente fica CRÍTICO no radar até às 01h do dia seguinte. A vendedora perde confiança no sistema.

## História de Usuário

> Como vendedora, quero que o radar reflita as vendas do dia durante o horário comercial, para que eu não perca tempo religando para clientes que já compraram hoje.

## Critérios de Aceite

- [ ] O ETL incremental é executado **automaticamente múltiplas vezes ao dia** em horário comercial (sugestão: 07h, 10h, 13h, 16h, 18h)
- [ ] O modo incremental garante que cada execução extra leve menos de 10s e zero impacto no banco (já garantido com NOLOCK + watermark)
- [ ] O radar exibe o **timestamp do cache** de forma destacada para o usuário entender a janela de atualização
- [ ] Logs de cada execução intraday ficam no mesmo `logs/etl.log` com identificação clara do horário

## Solução Técnica

### 1. Adicionar execuções ao cron

Substituir a entrada atual de cron por múltiplas entradas intraday:

```cron
# ETL GM Limpeza — atualização intraday
0 1  * * * cd /home/vmonteiro/gm-limpeza-analytics && venv/bin/python scripts/etl_cache.py >> logs/etl.log 2>&1
0 7  * * * cd /home/vmonteiro/gm-limpeza-analytics && venv/bin/python scripts/etl_cache.py >> logs/etl.log 2>&1
0 10 * * * cd /home/vmonteiro/gm-limpeza-analytics && venv/bin/python scripts/etl_cache.py >> logs/etl.log 2>&1
0 13 * * * cd /home/vmonteiro/gm-limpeza-analytics && venv/bin/python scripts/etl_cache.py >> logs/etl.log 2>&1
0 16 * * * cd /home/vmonteiro/gm-limpeza-analytics && venv/bin/python scripts/etl_cache.py >> logs/etl.log 2>&1
0 18 * * * cd /home/vmonteiro/gm-limpeza-analytics && venv/bin/python scripts/etl_cache.py >> logs/etl.log 2>&1
```

O modo incremental já existe — cada execução extra carrega apenas os registros novos desde o último watermark. Tempo esperado por execução intraday: **< 5s**.

### 2. Atualizar timestamp no radar_vendedor.py

Exibir a idade do cache com destaque no topo do radar:

```
⏱ Dados atualizados às 13h02 · próxima atualização às 16h00
```

Se o cache tiver mais de 4 horas, exibir aviso amarelo. Se mais de 12 horas, aviso vermelho.

## Impacto na Arquitetura

- **Modificado**: crontab do servidor
- **Modificado**: `dashboards/radar_vendedor.py` — melhorar exibição do timestamp
- **Nenhum impacto** no banco de produção — NOLOCK + incremental já protegem
- **Nenhuma mudança** no schema dos Parquets

## Notas

- O incremento de carga no banco é desprezível: cada execução intraday consulta apenas 1 dia de dados
- O modo full load (01h) continua como âncora de consistência — garante que qualquer eventual divergência no incremental seja corrigida toda madrugada
- A execução das 01h pode ser mantida como única execução nos finais de semana se desejado: `0 1 * * 1-5` (seg–sex) para intraday, `0 1 * * 6,0` para o full de fim de semana
