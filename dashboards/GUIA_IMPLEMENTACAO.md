# 🚀 Guia de Implementação — GM Limpeza Dashboard

## Pré-requisitos
- VM Linux com Python 3.10+ (você já tem)
- Acesso ao SQL Server do cliente (já validado)
- pymssql instalado (já feito)

---

## Passo 1 — Copiar o projeto para a VM

Copie a pasta `gm-dashboard/` para sua VM. A estrutura é:

```
gm-dashboard/
├── app.py                  # Dashboard completo
├── requirements.txt        # Dependências
├── .streamlit/
│   └── config.toml         # Tema e configuração
└── assets/
    └── logo.jpg            # Logo GM Limpeza
```

---

## Passo 2 — Instalar dependências

```bash
cd ~/gm-limpeza-analytics
source venv/bin/activate
cd ~/gm-dashboard
pip install -r requirements.txt
```

---

## Passo 3 — Testar localmente

```bash
streamlit run app.py
```

O dashboard abre em `http://localhost:8501`. Teste todas as abas.

Se der erro de conexão com o banco, verifique se o SQL Server
está acessível da VM (o teste com pymssql que já rodou antes).

---

## Passo 4 — Expor para o cliente (URL pública)

### Opção A — Cloudflare Tunnel (recomendado, gratuito, estável)

```bash
# Instalar cloudflared
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared
chmod +x cloudflared
sudo mv cloudflared /usr/local/bin/

# Criar tunnel (gera URL pública automaticamente)
cloudflared tunnel --url http://localhost:8501
```

Isso gera uma URL tipo `https://abc123.trycloudflare.com` que você manda pro cliente.

### Opção B — ngrok (alternativa)

```bash
# Instalar
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok-v3-stable-linux-amd64.tgz | tar xz
sudo mv ngrok /usr/local/bin/

# Criar conta grátis em https://ngrok.com e pegar o token
ngrok config add-authtoken SEU_TOKEN

# Expor
ngrok http 8501
```

---

## Passo 5 — Rodar em background (manter ligado)

Para o dashboard continuar rodando mesmo se você fechar o terminal:

```bash
# Opção simples com nohup
nohup streamlit run app.py &

# Opção melhor com screen
screen -S dashboard
streamlit run app.py
# Ctrl+A, D para desconectar
# screen -r dashboard para reconectar
```

Para o tunnel em background:

```bash
nohup cloudflared tunnel --url http://localhost:8501 &
```

---

## Passo 6 — Manter atualizado

O dashboard já tem cache de 5 minutos (`ttl=300` nas queries).
Cada vez que alguém acessa ou recarrega a página, se passaram
mais de 5 minutos desde a última consulta, os dados são buscados
novamente do banco.

Para forçar atualização: botão "⟳" no canto superior direito do Streamlit.

---

## Resumo dos Comandos (copiar e colar)

```bash
# Setup completo (rodar uma vez)
cd ~/gm-limpeza-analytics
source venv/bin/activate
pip install streamlit pymssql pandas plotly

# Copiar projeto (ajuste o caminho se necessário)
cp -r ~/gm-dashboard ~/gm-limpeza-analytics/dashboard
cd ~/gm-limpeza-analytics/dashboard

# Rodar dashboard + tunnel
streamlit run app.py &
cloudflared tunnel --url http://localhost:8501
```

---

## Troubleshooting

| Problema | Solução |
|----------|---------|
| Erro de conexão SQL | Verifique se o firewall libera sua VM na porta 52456 |
| Página em branco | Verifique se o Streamlit está rodando: `ps aux \| grep streamlit` |
| Dados desatualizados | Clique em "⟳" no Streamlit ou espere 5 min |
| Tunnel caiu | Reinicie: `cloudflared tunnel --url http://localhost:8501` |
| Erro de memória | O cache pode acumular. Reinicie o Streamlit |
