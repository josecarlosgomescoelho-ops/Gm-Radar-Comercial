# Bug: Ciclo de Compras Não Aparece no Mobile

**Status**: `desenvolvido`
**Criado em**: 2026-04-21
**Prioridade**: Must Have
**Esforço estimado**: Pequeno (1h)
**Tipo**: Bug

---

## Descrição do Problema

No celular, o ciclo de compras (🔄 Ciclo médio, dia habitual, atraso) não é exibido nos cards de detalhamento dos clientes. O conteúdo é cortado antes de chegar nessa informação.

## Causa Raiz

Os cards são renderizados via `components.html()` com altura calculada estaticamente no Python:

```python
altura = 155
if ciclo_text: altura += 22
if pivot_html: altura += 58
```

No desktop, o texto cabe na altura calculada. No mobile, a tela é mais estreita e o texto quebra em mais linhas — o nome do cliente, telefone, produtos habituais e ciclo todos ocupam mais altura do que o previsto. O iframe do `components.html()` tem altura fixa, então o conteúdo que ultrapassa fica cortado invisível.

## Critério de Aceite

- [ ] Todos os campos do card (incluindo ciclo de compras e pivot mensal) são visíveis no mobile sem scroll interno no card
- [ ] No desktop o layout não apresenta espaço em branco excessivo

## Solução

Adicionar JavaScript ao HTML do card que mede a altura real do conteúdo após renderizar e envia essa medida ao Streamlit para redimensionar o iframe dinamicamente:

```javascript
window.addEventListener('load', function() {
    const h = document.documentElement.scrollHeight;
    window.parent.postMessage({ type: 'streamlit:setFrameHeight', height: h + 4 }, '*');
});
window.addEventListener('resize', function() {
    const h = document.documentElement.scrollHeight;
    window.parent.postMessage({ type: 'streamlit:setFrameHeight', height: h + 4 }, '*');
});
```

O evento `resize` garante que quando o mobile rotaciona ou reflow acontece, o iframe se ajusta. O `height` estático no Python passa a ser um mínimo razoável, não o tamanho final.

## Arquivo Afetado

| Arquivo | Localização |
|---|---|
| `dashboards/radar_vendedor.py` | Constante `CARD_CSS` no topo do arquivo — adicionar `<script>` de auto-resize |
