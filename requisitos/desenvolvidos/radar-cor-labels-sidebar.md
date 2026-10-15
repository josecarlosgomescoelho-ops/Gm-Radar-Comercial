# Cor dos Labels de Filtro na Sidebar

**Status**: `desenvolvido`
**Criado em**: 2026-04-21
**Prioridade**: Must Have
**Esforço estimado**: Pequeno (15min)
**Tipo**: Bug visual

---

## Dor de Negócio

Os textos dos filtros "👥 Supervisor:" e "👤 Vendedora(s):" na sidebar estão com cor padrão escura sobre o fundo azul escuro (`#1B3A5C` → `#2E6BA6`), tornando os rótulos ilegíveis ou de difícil leitura.

## Critérios de Aceite

- [ ] Labels dos widgets `st.selectbox` e `st.multiselect` na sidebar exibidos em branco ou cinza claro (`#E8F4FD`)
- [ ] Textos dos botões "✅ Todas" e "✖ Limpar" legíveis sobre o fundo azul
- [ ] Nenhum outro elemento fora da sidebar é afetado pelo ajuste

## Causa e Solução

O CSS existente já trata `.stMarkdown` e `.stCaption` na sidebar, mas não cobre os elementos `label` gerados pelos widgets Streamlit. Adicionar ao bloco CSS global:

```css
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stMultiSelect label {
    color: #E8F4FD !important;
}
```

## Arquivos Afetados

| Arquivo | Localização |
|---|---|
| `dashboards/radar_vendedor.py` | Bloco `st.markdown("""<style>...</style>""")` no topo do arquivo |
