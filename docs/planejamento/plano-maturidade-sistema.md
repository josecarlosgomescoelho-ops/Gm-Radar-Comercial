# Plano de Maturidade — GM Limpeza Analytics

**Criado em**: 2026-04-24
**Autor**: Victor Monteiro

---

## Contexto

Sistema atual: dois dashboards Streamlit (`app.py` + `radar_vendedor.py`) rodando em WSL com túnel Cloudflare temporário. Cache ETL via Parquet implementado. Banco de produção protegido. Próximo passo: transformar em serviço permanente, autenticado e escalável.

---

## Onda 1 — Infraestrutura permanente

**Prazo estimado**: 1 semana
**Objetivo**: sair do "funciona enquanto o PC está ligado" para um serviço real.

### Hospedagem — Oracle Cloud Free Tier (R$ 0/mês)

Melhor relação custo-benefício disponível. Oracle oferece permanentemente grátis:

- 4 vCPUs + 24 GB RAM + 200 GB disco
- Uptime 24/7 sem depender da máquina local
- Suficiente para rodar os dois dashboards + ETL por anos

**Alternativa paga**: Contabo VPS (~R$ 30/mês, 4 GB RAM, Linux) — se preferir suporte e simplicidade de setup.

### Domínio fixo — Cloudflare Tunnel permanente (R$ 0)

O tunnel atual muda de URL a cada restart. Com uma conta Cloudflare gratuita:

- Cria-se um tunnel nomeado e permanente
- A URL nunca muda, mesmo reiniciando o servidor
- Domínio próprio registrado no Registro.br: `gmlimpeza.com.br` ou `analytics.gmlimpeza.com.br`

**Custo do domínio**: ~R$ 40/ano no Registro.br.

**Resultado final**: `https://analytics.gmlimpeza.com.br` fixo, sempre no ar, custo ~R$ 40/ano.

---

## Onda 2 — Autenticação e controle de acesso

**Prazo estimado**: 2–3 semanas
**Objetivo**: cada pessoa vê só o que é dela.

### Autenticação — Cloudflare Access (R$ 0 até 50 usuários)

Solução mais elegante para este caso: **zero mudança no código do dashboard**.

O Cloudflare fica na frente do tunnel e exige login antes de deixar entrar. Suporta:

- Login por e-mail com código OTP (sem senha para lembrar)
- Google/Microsoft SSO (se a empresa usar Gmail ou Office 365)

Quem não estiver na lista de e-mails autorizados vê uma tela de bloqueio — o dashboard nem carrega.

### Controle por perfil — dentro do Streamlit

Após o login, o Cloudflare passa o e-mail do usuário no header da requisição. O dashboard lê esse e-mail e aplica as regras de acesso:

| Perfil | E-mail de exemplo | O que vê |
|---|---|---|
| Gestor | gestor@gmlimpeza.com.br | Dashboard completo, todos os supervisores e vendedores |
| Supervisor | leandro@gmlimpeza.com.br | Apenas a equipe dele no Radar e nos gráficos |
| Vendedor | vendedor1@gmlimpeza.com.br | Apenas a própria carteira no Radar |

Uma tabela simples em YAML ou CSV mapeia `email → perfil → CodVendedor`. Sem banco de usuários, sem complexidade adicional.

---

## Onda 3 — Menu e expansão de funcionalidades

**Prazo estimado**: contínuo
**Objetivo**: estrutura que cresce sem virar bagunça.

### Arquitetura multipage do Streamlit

Em vez de tudo em um arquivo único, cada funcionalidade vira uma página separada:

```
dashboards/
├── app_home.py           # ponto de entrada e menu principal
└── pages/
    ├── 1_vendas.py       # dashboard de vendas (atual)
    ├── 2_radar.py        # radar de risco (atual)
    ├── 3_produtos.py     # análise de produtos (futuro)
    ├── 4_clientes.py     # curva ABC de clientes (futuro)
    └── 5_metas.py        # acompanhamento de metas (futuro)
```

O Streamlit renderiza automaticamente um menu lateral com essas páginas. Cada nova funcionalidade é um arquivo novo — sem tocar no que já funciona.

---

## Resumo de custos

| Item | Custo |
|---|---|
| Oracle Cloud Free Tier (servidor) | R$ 0/mês |
| Cloudflare Tunnel + Access (auth + domínio seguro) | R$ 0/mês |
| Domínio .com.br (Registro.br) | ~R$ 40/ano |
| **Total** | **~R$ 3,50/mês** |

---

## Sequência de implementação

```
Semana 1  →  Onda 1: Oracle Cloud + Tunnel permanente + domínio próprio
Semana 2  →  Onda 2: Cloudflare Access (autenticação por e-mail)
Semana 3  →  Onda 2: perfis por usuário dentro do dashboard
Contínuo  →  Onda 3: migrar para multipage conforme novas funções chegam
```
