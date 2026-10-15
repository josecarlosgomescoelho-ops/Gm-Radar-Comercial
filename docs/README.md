# 📖 Documentação para Desenvolvedores

Bem-vindo à pasta de documentação do **GM Limpeza Analytics**!

Esta pasta contém guias completos para ajudar desenvolvedores a configurar, entender e dar manutenção no sistema.

---

## 📚 Guias Disponíveis

### 🎓 Onboarding

#### [GUIA_ONBOARDING_DEV.md](./onboarding/GUIA_ONBOARDING_DEV.md)
Guia completo para novos desenvolvedores (stack, setup, arquitetura, fluxo de trabalho)

#### [QUICKSTART.md](./onboarding/QUICKSTART.md)
Guia de inicialização rápida com comandos essenciais

#### [CLAUDE.MD](./onboarding/CLAUDE.MD)
Contexto e instruções para uso do Claude Code no projeto

---

### 🚀 Deploy e Infraestrutura

#### [guia-hostinger-deploy.md](./deployment/guia-hostinger-deploy.md)
Guia completo para hospedar aplicações usando domínio Hostinger (subdomínios, DNS, SSL, Cloudflare Tunnel)

#### [ACESSO_VPS_HOSTINGER.md](./deployment/ACESSO_VPS_HOSTINGER.md)
Acesso ao servidor de produção via SSH e VS Code Remote-SSH

#### [CONFIGURACAO_DOMINIO.md](./deployment/CONFIGURACAO_DOMINIO.md)
Configuração de domínio, DNS no Cloudflare, e rotas do Cloudflare Tunnel

#### [CLOUDFLARE_TUNNEL.md](./deployment/CLOUDFLARE_TUNNEL.md)
Setup detalhado do Cloudflare Tunnel para acesso seguro

#### [deploy-pc-local.md](./deployment/deploy-pc-local.md)
Deploy em PC dedicado local

---

### 📊 Análises e Relatórios

Pasta `analises/` contém:
- Análises de vendas e produtos (nov/25 - abr/26)
- Painéis estratégicos de rentabilidade
- Consultas e exports de dados

---

### 📋 Planejamento

Pasta `planejamento/` contém:
- Planos de maturidade do sistema
- Roadmaps e objetivos

---

### 🗄️ Schema do Banco

Pasta `schema/` contém CSVs com mapeamento completo das tabelas do banco de dados

---

## 🎯 Por Onde Começar?

### Novo no Projeto?

1. **Primeiro:** Leia o [GUIA_ONBOARDING_DEV.md](./onboarding/GUIA_ONBOARDING_DEV.md)
2. **Depois:** Use o [QUICKSTART.md](./onboarding/QUICKSTART.md) para configurar seu ambiente local
3. **Por fim:** Configure acesso à VPS com [ACESSO_VPS_HOSTINGER.md](./deployment/ACESSO_VPS_HOSTINGER.md)

### Já Conhece o Projeto?

- Precisa acessar a produção? → [ACESSO_VPS_HOSTINGER.md](./deployment/ACESSO_VPS_HOSTINGER.md)
- Precisa configurar domínio/subdomínio? → [guia-hostinger-deploy.md](./deployment/guia-hostinger-deploy.md)
- Precisa configurar DNS no Cloudflare? → [CONFIGURACAO_DOMINIO.md](./deployment/CONFIGURACAO_DOMINIO.md)
- Dúvida sobre arquitetura? → [GUIA_ONBOARDING_DEV.md](./onboarding/GUIA_ONBOARDING_DEV.md#como-funciona-o-sistema)
- Troubleshooting? → Todos os guias têm seções dedicadas

---

## 📂 Estrutura da Documentação

```
docs/
├── README.md                    (este arquivo)
├── onboarding/                  (guias para novos devs)
│   ├── GUIA_ONBOARDING_DEV.md
│   ├── QUICKSTART.md
│   └── CLAUDE.MD
├── deployment/                  (infraestrutura e deploy)
│   ├── guia-hostinger-deploy.md
│   ├── ACESSO_VPS_HOSTINGER.md
│   ├── CONFIGURACAO_DOMINIO.md
│   ├── CLOUDFLARE_TUNNEL.md
│   └── deploy-pc-local.md
├── analises/                    (relatórios e análises)
├── planejamento/                (roadmaps e planos)
└── schema/                      (mapeamento do banco)
```

### Outras Pastas do Projeto

- **[README.md](../README.md)** - Visão geral técnica completa na raiz
- **[scripts/](../scripts/)** - Scripts SQL e Python
- **[dashboards/](../dashboards/)** - Dashboards Streamlit

---

## 🔄 Fluxo de Leitura Recomendado

```
1. docs/onboarding/GUIA_ONBOARDING_DEV.md  (Setup inicial + fundamentos)
         │
         ├─▶ docs/onboarding/QUICKSTART.md      (Comandos rápidos)
         │
         ├─▶ ../README.md                        (Arquitetura detalhada)
         │
         ├─▶ deployment/ACESSO_VPS_HOSTINGER.md  (Acesso produção)
         │
         ├─▶ deployment/guia-hostinger-deploy.md (Hospedar apps)
         │
         └─▶ deployment/CONFIGURACAO_DOMINIO.md  (Config DNS avançado)
                   │
                   └─▶ Pronto para desenvolver! 🚀
```

---

## 🛠️ Comandos Rápidos

**Setup Local:**
```bash
# Clone e configure
git clone <repo>
cd gm-limpeza-analytics
make build
make up
```

**Acesso VPS:**
```bash
# SSH direto
ssh root@<IP_VPS>

# Ou via VS Code Remote-SSH
# Ver ACESSO_VPS_HOSTINGER.md
```

**Comandos Úteis:**
```bash
make help      # Lista todos os comandos
make status    # Status dos containers
make logs      # Ver logs
make etl       # Executar ETL
```

---

## 📞 Precisa de Ajuda?

1. **Consulte os guias acima** (90% das dúvidas estão lá!)
2. **Verifique a seção de Troubleshooting** em cada guia
3. **Pergunte ao time** se ainda tiver dúvidas

---

## 🔄 Contribuindo para a Documentação

Encontrou um erro? Tem uma sugestão de melhoria?

1. Edite o arquivo `.md` relevante na pasta apropriada
2. Commit com mensagem descritiva:
   ```bash
   git add docs/onboarding/GUIA_ONBOARDING_DEV.md
   git commit -m "docs: corrige passo 3 do setup local"
   git push origin main
   ```

**Mantenha a documentação atualizada! Futuros devs agradecem! 🙏**

---

**Boa leitura e bom desenvolvimento! 🚀**
