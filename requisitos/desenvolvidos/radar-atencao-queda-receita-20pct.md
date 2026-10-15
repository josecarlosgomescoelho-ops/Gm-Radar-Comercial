# Ajuste de Limiar de Atenção: Queda de Receita de 50% para 20%

**Status**: `a-desenvolver`
**Criado em**: 2026-04-21
**Prioridade**: Must Have
**Esforço estimado**: Pequeno (30min)

---

## Dor de Negócio

O limiar atual de 50% de queda na receita para classificar um cliente como "Atenção" é muito permissivo — uma queda de 49% já é um sinal claro de risco e passa despercebida. O negócio quer ser alertado mais cedo, antes que a queda se aprofunde e o cliente migre para o concorrente.

## História de Usuário

> Como supervisor, quero que clientes com queda de 20% ou mais na receita do mês atual vs. a média mensal entrem automaticamente em "Atenção", para que eu possa agir antes que a situação se agrave.

## Critérios de Aceite

- [ ] A classificação ATENCAO passa a incluir clientes com `variacao < -20` (antes `-50`), independente de terem comprado no mês atual
- [ ] O tooltip explicativo (ℹ️ "Como funciona a classificação de risco?") é atualizado: "caiu mais de **20%**" substituindo "50%"
- [ ] A mensagem de alerta no card do cliente exibe corretamente a variação percentual real (ex: "⚠️ Faturamento caiu 23% vs média") — sem alteração necessária, pois já usa `cli["VariacaoVsMedia"]` dinamicamente

## Arquivos e Linhas Afetadas

| Arquivo | Linha | Alteração |
|---|---|---|
| `dashboards/radar_vendedor.py` | 428 | `variacao < -50` → `variacao < -20` |
| `dashboards/radar_vendedor.py` | 609 | `"caiu mais de 50%"` → `"caiu mais de 20%"` |

## Impacto Esperado

A mudança aumentará o número de clientes classificados como ATENÇÃO. Recomenda-se validar com o usuário após a primeira execução se o volume de alertas está adequado — um limiar muito baixo pode gerar ruído e fazer o supervisor ignorar os alertas.
