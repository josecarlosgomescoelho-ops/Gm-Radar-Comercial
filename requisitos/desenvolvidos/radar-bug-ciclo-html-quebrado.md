# Bug: HTML do Ciclo de Compra Quebrando nos Cards de Cliente

**Status**: `a-desenvolver`
**Criado em**: 2026-04-21
**Prioridade**: Must Have
**Esforço estimado**: Pequeno (1-2h)
**Tipo**: Bug

---

## Descrição do Problema

Em alguns cards de cliente na lista do Radar de Risco, o código HTML bruto está sendo exibido em tela em vez de ser renderizado. O usuário vê literalmente o conteúdo de `</div><table style="width:100%...` como texto, conforme exemplo reportado:

```
</div>
<table style="width:100%; margin-top:8px;"><tr><th style="text-align:right; padding:4px 8px; font-size:0.72rem; color:#95A5A6;">11/2025</th>...
```

## Causa Raiz

O card de cada cliente é renderizado via um único `st.markdown(f"...", unsafe_allow_html=True)` com uma string HTML muito longa e aninhada (linhas 696-716 de `radar_vendedor.py`). 

O Streamlit tem um limite não documentado de complexidade para renderização de HTML via `st.markdown`. Quando a string HTML ultrapassa esse limite (especialmente com múltiplos blocos de CSS inline, emojis e tabelas aninhadas dentro de `<div>`s com classes), o parser do Streamlit falha silenciosamente e escapa o restante do conteúdo como texto literal.

Os clientes afetados são especificamente aqueles que possuem **ciclo de compra detectado** (`CicloMedioDias` não-nulo), pois a variável `ciclo_text` adiciona uma `<span>` extra dentro do `<div class="cliente-meta">`, aumentando a complexidade da string até o ponto de quebra.

## Critérios de Aceite

- [ ] Nenhum cliente exibe código HTML bruto em tela
- [ ] O ciclo de compra (🔄 Ciclo médio, dia habitual e atraso) continua sendo exibido nos cards
- [ ] O mini pivot mensal continua sendo exibido corretamente abaixo das informações do cliente
- [ ] O comportamento é consistente para todos os clientes, independente de ter ciclo detectado ou não

## Solução Recomendada

Substituir o `st.markdown` único e complexo por uma composição de elementos Streamlit nativos + `st.components.v1.html()` apenas para as partes verdadeiramente HTML (a tabela pivot e o card colorido):

**Opção A (mais simples)**: Separar o card em dois chamadas `st.markdown`:
1. Primeira: o card principal (nome, badge, alerta, meta, ciclo)
2. Segunda: apenas a tabela pivot

**Opção B (mais robusta)**: Usar `st.components.v1.html(html_str, height=N)` para renderizar o card completo — este método não tem as mesmas limitações do markdown parser do Streamlit.

**Recomendação**: Opção B, pois resolve o problema na raiz sem fragmentar a lógica de renderização. O único cuidado é definir a altura dinamicamente (cards com mais informação precisam de height maior).

## Impacto na Arquitetura

- `radar_vendedor.py` — loop de renderização de clientes (linhas 646-716)
- Se usar `st.components.v1.html()`: adicionar `import streamlit.components.v1 as components` no topo
- Nenhuma mudança nas queries, classificação ou lógica de negócio

## Como Reproduzir

1. Abrir o Radar de Risco (`streamlit run radar_vendedor.py`)
2. Selecionar uma vendedora que tenha clientes com ciclo de compra detectado (ao menos 3 compras históricas)
3. Observar que o card desses clientes exibe HTML bruto após o conteúdo de "📦 Produtos habituais"
