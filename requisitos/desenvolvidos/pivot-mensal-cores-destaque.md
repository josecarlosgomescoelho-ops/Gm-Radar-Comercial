# Pivot Mensal — Destaque Visual com Cores na Tabela Mês a Mês

**Status**: `a-desenvolver`
**Criado em**: 2026-05-09
**Prioridade**: Should Have
**Esforço estimado**: Pequeno (<2h)

---

## Dor de Negócio

A tabela de faturamento mês a mês (aba Pivot Mensal) exibe apenas números sem nenhum destaque visual, dificultando identificar rapidamente queda de clientes, meses zerados ou crescimento expressivo.

## História de Usuário

> Como supervisor comercial, quero que a tabela mensal destaque visualmente os valores por cor, para que eu identifique de imediato clientes em queda, inativos ou em crescimento sem precisar ler número por número.

## Critérios de Aceite

- [ ] Células com valor `R$ 0,00` devem ser exibidas em cinza claro (cliente inativo no mês)
- [ ] Célula com valor abaixo da média do cliente (calculada ao longo dos meses exibidos) → fundo amarelo
- [ ] Célula com valor acima de 150% da média do cliente → fundo verde claro
- [ ] Meses com queda consecutiva de 2 ou mais meses → linha com destaque de borda esquerda vermelha
- [ ] As cores devem ser aplicadas via `pandas Styler` — manter compatibilidade com `st.dataframe`
- [ ] Legenda de cores exibida abaixo da tabela (verde = acima da média, amarelo = abaixo, cinza = inativo)

## Dados necessários

- Tabelas: `Movimento` (já carregado via Parquet `movimentos.parquet`)
- Colunas: `ValorLiquido`, `MesAnoStr`, `CodCliFor`, `Cliente`, `Vendedor`
- Status: ✅ Disponível — pivot já calculado no `tab7`

## Impacto na arquitetura atual

- Modificado: `dashboards/app.py` — bloco `with tab7:` (linha ~903)
- Substituir `st.dataframe(pivot...)` por versão estilizada com `pandas Styler`
- Sem impacto em queries ou cache

## Notas

Atenção ao desempenho do Styler com pivots grandes (muitos clientes × muitos meses). Se necessário, aplicar as cores apenas nas linhas visíveis ou limitar a 200 clientes no Styler e manter paginação.
