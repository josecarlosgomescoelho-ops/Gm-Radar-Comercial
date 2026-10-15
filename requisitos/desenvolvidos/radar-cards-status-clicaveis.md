# Cards de Status Clicáveis no Radar de Risco

**Status**: `a-desenvolver`
**Criado em**: 2026-04-21
**Prioridade**: Should Have
**Esforço estimado**: Médio (3-4h)

---

## Dor de Negócio

O usuário vê os cards de "Crítico", "Atenção", "Ativo" e "Perdido" com contagens e valores, mas precisa ir até a sidebar para aplicar um filtro. O fluxo natural seria clicar diretamente no card para ver apenas aquele grupo — o que hoje não é possível porque os cards são HTML estático sem interação.

## História de Usuário

> Como usuário do Radar de Risco, quero clicar nos cards de status (Crítico, Atenção, Ativo, Perdido) para filtrar a lista de clientes exibida, sem precisar usar o multiselect da sidebar.

## Critérios de Aceite

- [ ] Clicar em um card aplica o filtro de status correspondente na lista de clientes abaixo
- [ ] Clicar em um card já ativo (filtro já aplicado) remove o filtro (toggle)
- [ ] É possível ter múltiplos cards ativos ao mesmo tempo (ex: Crítico + Atenção)
- [ ] O card ativo tem visual destacado (borda mais espessa ou fundo mais intenso) para indicar que está selecionado
- [ ] O filtro do card e o `st.multiselect` da sidebar ficam sincronizados — alterar um reflete no outro
- [ ] Se nenhum card estiver selecionado, todos os clientes são exibidos
- [ ] A contagem "X clientes encontrados" abaixo dos cards reflete o filtro ativo

## Restrição Técnica

Streamlit não suporta eventos de clique em HTML arbitrário (`st.markdown` com `unsafe_allow_html`). Os cards precisam ser re-implementados usando componentes Streamlit nativos que suportem interação, mantendo o visual atual.

**Abordagem recomendada**: usar `st.button` com CSS customizado para sobrepor o estilo padrão do botão, tornando-o visualmente idêntico ao card atual. O estado de seleção é gerenciado via `st.session_state`.

```python
# Exemplo de estrutura para cada card
if st.button(f"🔴 {n_criticos}\nCRÍTICO\n{fmt_brl(r)} em risco", key="btn_critico"):
    # toggle no session_state
    if "CRITICO" in st.session_state.filtro_status:
        st.session_state.filtro_status.remove("CRITICO")
    else:
        st.session_state.filtro_status.add("CRITICO")
```

O CSS deve remover a aparência padrão de botão (`border`, `background`, `box-shadow`) e aplicar as classes `.card-critico`, `.card-atencao`, etc.

## Impacto na Arquitetura

- `radar_vendedor.py` — seção de Cards de Status (linhas 552-595): substituir `st.markdown` estáticos por `st.button` com CSS
- Inicializar `st.session_state.filtro_status` com `{"CRITICO", "ATENCAO"}` (padrão atual)
- Sincronizar `session_state.filtro_status` com o `st.multiselect` da sidebar (linha 510-516): usar o session_state como `default` do multiselect
- A lógica de filtro na linha 636 (`df_clientes[df_clientes["Status"].isin(filtro_status)]`) permanece igual

## Notas / Decisões Pendentes

- Confirmar se o comportamento "nenhum card selecionado = mostra todos" é o desejado, ou se deve manter a seleção anterior
- Card "Perdido / Novo" atual agrupa dois status em um só card — decidir se vira dois cards separados ou mantém o agrupamento com toggle nos dois status simultaneamente
  - **Recomendação**: separar em dois cards para consistência com o comportamento de toggle
