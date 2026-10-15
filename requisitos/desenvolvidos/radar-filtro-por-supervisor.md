# Filtro por Supervisor no Radar de Risco

**Status**: `a-desenvolver`
**Criado em**: 2026-04-21
**Prioridade**: Must Have
**Esforço estimado**: Pequeno (2-3h)
**Dependência**: Depende de `radar-multi-select-vendedores.md` (implementar antes)

---

## Dor de Negócio

O supervisor precisa de um atalho para ver a carteira de risco de toda a sua equipe de uma vez, sem precisar marcar cada vendedora individualmente no multiselect. Hoje não existe nenhum agrupamento por hierarquia comercial no Radar.

## História de Usuário

> Como supervisor, quero selecionar meu nome em um filtro de supervisor para que todas as vendedoras da minha equipe sejam automaticamente selecionadas no multiselect, podendo depois remover ou adicionar vendedoras individualmente.

## Critérios de Aceite

- [ ] A sidebar exibe um `st.selectbox` de supervisor **acima** do multiselect de vendedoras, com opção "Todos" como padrão
- [ ] Ao selecionar um supervisor, o multiselect de vendedoras é automaticamente preenchido com todas as vendedoras daquele supervisor
- [ ] O usuário pode, após selecionar o supervisor, remover ou adicionar vendedoras individualmente no multiselect (os dois filtros trabalham juntos)
- [ ] Ao mudar o supervisor para "Todos", o multiselect volta ao estado anterior (sem forçar seleção)
- [ ] Supervisores listados são apenas os que têm ao menos uma vendedora ativa vinculada
- [ ] O header e o resumo de ações adaptam o texto para incluir o nome do supervisor quando toda a equipe dele está selecionada (ex: "Equipe Leandro")

## Dados Necessários

| Campo | Tabela | Status |
|---|---|---|
| CodVendedor, NomeVendedor | Vendedores | ✅ Disponível |
| CodSupervisor | Vendedores | ✅ Disponível |

**Query nova necessária**: buscar supervisores distintos (vendedores que são referenciados como `CodSupervisor` por ao menos uma vendedora ativa):

```sql
SELECT DISTINCT
    SUP.CodVendedor,
    SUP.NomeVendedor AS Supervisor
FROM Vendedores V
INNER JOIN Vendedores SUP ON V.CodSupervisor = SUP.CodVendedor
WHERE V.Inativo = 'N'
  AND V.Tipo = 'V'
ORDER BY SUP.NomeVendedor
```

## Impacto na Arquitetura

- `radar_vendedor.py` — nova função `q_supervisores()` com cache TTL=300
- Sidebar: adicionar `selectbox` de supervisor antes do `multiselect` de vendedoras (linhas 500-517)
- Usar `st.session_state` para controlar o estado do multiselect quando o supervisor muda
- Lógica de detecção "equipe completa do supervisor selecionado" para adaptar textos do header e rodapé

## Notas / Decisões Pendentes

- Estrutura de supervisão atual: **Leandro** (6 vendedoras) e **Cesar** (5 vendedores) — confirmar se há outros supervisores ativos no banco
- Decidir comportamento quando o supervisor muda: sobrescreve o multiselect ou faz union com o que estava selecionado?
  - **Recomendação**: sobrescrever (mais intuitivo para o usuário)
