# Sidebar — Corrigir Seleção de Vendedores + Cache da Última Seleção

**Status**: `a-desenvolver`
**Criado em**: 2026-05-09
**Prioridade**: Must Have
**Esforço estimado**: Médio (2–8h)

---

## Dor de Negócio

O filtro de vendedores na sidebar mantém "Alineide" como padrão em algumas situações, causando confusão — supervisores e gestores abrem o dashboard e veem dados filtrados para uma vendedora específica sem perceber. Além disso, o filtro sempre reabre vazio, obrigando o usuário a refazer a seleção a cada sessão.

## História de Usuário

> Como gestor ou supervisor, quero que o dashboard abra sem nenhum vendedor pré-selecionado e que minha última seleção seja lembrada, para que eu não precise refazer o filtro toda vez que acessar o sistema.

## Critérios de Aceite

- [ ] Ao abrir o dashboard pela primeira vez (sem cache salvo), exibir modal/tela de boas-vindas solicitando seleção de vendedores antes de carregar os dados
- [ ] O modal deve ter: multiselect de vendedores, opção "Todos os vendedores" como atalho, e botão "Aplicar"
- [ ] Nenhum vendedor deve ser pré-selecionado por padrão — `default=[]`
- [ ] Após a seleção, salvar em `st.session_state` + `localStorage` via `streamlit-js-eval` ou arquivo de preferências local (`.cache/user_prefs.json`)
- [ ] Na próxima sessão, carregar a última seleção salva automaticamente, exibindo um aviso: "Filtro anterior carregado: [lista de vendedores] · Alterar"
- [ ] Botão de reset na sidebar: "Limpar filtro / Todos" que retorna ao estado sem seleção
- [ ] Remover qualquer `default=["Alineide"]` ou ordenação que coloque um vendedor específico primeiro

## Dados necessários

- Tabelas: `Vendedores` (já carregado no app)
- Status: ✅ Disponível
- Dependência técnica: mecanismo de persistência entre sessões (`localStorage` via componente JS ou arquivo JSON local)

## Impacto na arquitetura atual

- Modificado: `dashboards/app.py` — bloco sidebar (linha ~420–480)
- Novo: lógica de modal de seleção inicial (pode usar `st.dialog` do Streamlit ≥ 1.32 ou simulação com `st.empty`)
- Novo: arquivo `cache/user_prefs.json` para persistência de preferências do usuário
- Avaliar: `streamlit-js-eval` para localStorage, ou simplificar com arquivo JSON local dado que é ambiente single-user

## Notas

O ambiente é single-user (WSL + Cloudflare Tunnel), então persistir em arquivo local `.cache/user_prefs.json` é suficiente e mais simples que localStorage. Implementar com `json.dump/load` protegido por `try/except`.
