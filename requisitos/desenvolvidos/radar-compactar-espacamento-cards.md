# Radar — Compactar Espaçamento entre Cards de Cliente

**Status**: `a-desenvolver`
**Criado em**: 2026-05-09
**Prioridade**: Should Have
**Esforço estimado**: Pequeno (<2h)

---

## Dor de Negócio

O radar exibe os clientes com espaçamento excessivo entre os cards, forçando muito scroll para visualizar a carteira. Com 10+ clientes visíveis ao mesmo tempo, a navegação fica lenta e a leitura cansativa.

## História de Usuário

> Como vendedora, quero ver mais clientes na tela ao mesmo tempo, para navegar pela carteira com menos scroll durante o atendimento.

## Critérios de Aceite

- [ ] O espaçamento vertical entre cards é reduzido e padronizado (sem gaps irregulares)
- [ ] O conteúdo interno de cada card (nome, status, telefone, pivot) continua legível — sem corte de texto
- [ ] Cards com pivot mensal e cards sem pivot têm alturas proporcionais (sem espaço em branco no fundo do card)
- [ ] A redução é aplicada uniformemente para todos os status (CRÍTICO, ATENÇÃO, ATIVO)

## Causa Técnica

Dois pontos de espaçamento a ajustar:

### 1. Margem padrão do Streamlit entre `components.html`

O Streamlit injeta `margin-bottom` nos elementos `stCustomComponentV1`. Pode ser suprimido via CSS global:

```python
st.markdown("""
<style>
  iframe[title="streamlit_components_v1.component_v1"] {
      display: block;
      margin-bottom: -8px !important;
  }
</style>
""", unsafe_allow_html=True)
```

### 2. Altura do iframe calculada com folga (`altura` em `render_card`)

O cálculo atual começa em `altura = 120` e adiciona valores fixos conservadores. Reduzir a base e afinar os incrementos por linha elimina o espaço em branco no fundo de cada card.

```python
# Atual
altura  = 120
altura += linhas(ult_compra) * PX_POR_LINHA
if alerta:     altura += 40
if ciclo_text: altura += linhas(ciclo_text) * PX_POR_LINHA + 10
if pivot_html: altura += 70
if n_sel > 1:  altura += 25

# Ajuste sugerido
altura  = 100                         # base menor
altura += linhas(ult_compra) * PX_POR_LINHA
if alerta:     altura += 32           # era 40
if ciclo_text: altura += linhas(ciclo_text) * PX_POR_LINHA + 6  # era +10
if pivot_html: altura += 60           # era 70
if n_sel > 1:  altura += 20           # era 25
```

## Impacto na Arquitetura

- **Modificado**: `dashboards/radar_vendedor.py` — CSS global + função `render_card`
- Nenhum impacto em dados, ETL ou outros dashboards

## Notas

- Testar com clientes que têm pivot longo (6 meses) e sem histórico para garantir que nenhum card fica cortado
- O seletor CSS do iframe pode variar entre versões do Streamlit — validar no ambiente de deploy
