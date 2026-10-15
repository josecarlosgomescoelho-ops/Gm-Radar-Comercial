"""
GM Limpeza — Relatório de Vendas e Compras por Fornecedor
Baseado nos dados de movimentação de estoque (ENTRADA e SAÍDA).
Granularidade mensal — últimos 12 meses fechados.
"""

import os
import streamlit as st
import pandas as pd
import pymssql
import numpy as np
from datetime import date, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

# ============================================================================
# CONFIGURAÇÃO
# ============================================================================
DB_CONFIG = {
    "server":   os.environ["DB_SERVER"],
    "port":     int(os.environ["DB_PORT"]),
    "user":     os.environ["DB_USER"],
    "password": os.environ["DB_PASSWORD"],
    "database": os.environ["DB_NAME"],
}

CORES = {
    "azul_escuro": "#1B3A5C",
    "azul_medio":  "#2E6BA6",
    "azul_claro":  "#4DA8DA",
    "azul_gelo":   "#E8F4FD",
    "verde":       "#27AE60",
    "amarelo":     "#F39C12",
    "vermelho":    "#E74C3C",
    "cinza":       "#95A5A6",
    "cinza_claro": "#BDC3C7",
}

LOGO_PATH = Path(__file__).parent / "assets" / "logo.jpg"
HOJE = date.today()

# ============================================================================
# PÁGINA
# ============================================================================
st.set_page_config(
    page_title="GM Limpeza — Relatório Fornecedor",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Auth gate
from auth import check_session, render_logout_sidebar
_auth_user = check_session()

st.markdown("""
<style>
    /* Esconder menu */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* KPI Cards */
    .kpi-card {
        background: linear-gradient(135deg, #FFFFFF 0%, #F7FAFC 100%);
        border-left: 4px solid #2E6BA6;
        border-radius: 10px;
        padding: 18px 22px;
        box-shadow: 0 2px 12px rgba(0,0,0,0.05);
        margin-bottom: 8px;
    }
    .kpi-card.accent-green  { border-left-color: #27AE60; }
    .kpi-card.accent-yellow { border-left-color: #F39C12; }
    .kpi-card.accent-red    { border-left-color: #E74C3C; }
    .kpi-label {
        color: #95A5A6;
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        margin-bottom: 2px;
    }
    .kpi-value {
        color: #1B3A5C;
        font-size: 1.5rem;
        font-weight: 700;
        line-height: 1.3;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] > div {
        background: linear-gradient(180deg, #1B3A5C 0%, #2E6BA6 100%);
    }
    [data-testid="stSidebar"] .stMarkdown p,
    [data-testid="stSidebar"] .stMarkdown h3,
    [data-testid="stSidebar"] .stCaption,
    [data-testid="stSidebar"] label {
        color: #E8F4FD !important;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================================
# CONEXÃO E QUERIES
# ============================================================================
def get_conn():
    return pymssql.connect(**DB_CONFIG, login_timeout=15, timeout=120, charset="UTF-8")


@st.cache_data(ttl=1800, show_spinner="Carregando fornecedores...")
def q_fornecedores():
    """Lista de fabricantes/fornecedores."""
    sql = """
    SELECT DISTINCT
        F.CodFabr,
        F.NomeFabr
    FROM Fabricantes F WITH (NOLOCK)
    ORDER BY F.NomeFabr
    """
    conn = get_conn()
    df = pd.read_sql(sql, conn)
    conn.close()
    return df


@st.cache_data(ttl=1800, show_spinner="Processando vendas e compras...")
def q_vendas_compras_fornecedor(cod_fabr: str):
    """
    Retorna vendas e compras por produto do fornecedor,
    agregadas por mês, nos últimos 12 meses fechados.
    """
    # Calcular período: últimos 12 meses fechados (do primeiro dia de 12 meses atrás até o último dia do mês anterior)
    hoje = date.today()
    primeiro_dia_mes_atual = hoje.replace(day=1)
    ultimo_dia_mes_anterior = primeiro_dia_mes_atual - timedelta(days=1)
    primeiro_dia_12_meses = (primeiro_dia_mes_atual - timedelta(days=365)).replace(day=1)

    sql = """
    ;WITH DadosBase AS (
        SELECT
            P.IdProduto,
            P.NOMEPRODUTO AS Produto,
            M.DataFaturamento,
            YEAR(M.DataFaturamento) AS Ano,
            MONTH(M.DataFaturamento) AS Mes,
            -- Classificar como Venda ou Compra
            CASE
                WHEN M.TipoMov IN ('2.4','2.1','2.5') THEN 'VENDA'
                WHEN M.TipoMov IN ('1.1') THEN 'COMPRA'
                ELSE NULL
            END AS TipoOperacao,
            SUM(IM.Qtd) AS Quantidade
        FROM ItensMov IM WITH (NOLOCK)
        INNER JOIN Movimento M WITH (NOLOCK) ON IM.IdMov = M.IdMov
        INNER JOIN Produtos P WITH (NOLOCK) ON IM.IdProduto = P.IdProduto
        WHERE P.CodFabr = %s
          AND M.DataFaturamento >= %s
          AND M.DataFaturamento <= %s
          AND M.Status NOT IN ('C','T')
          AND IM.StatusItemMov NOT IN ('C')
          AND M.TipoMov IN ('2.4','2.1','2.5','1.1')  -- Vendas + Compras
        GROUP BY P.IdProduto, P.NOMEPRODUTO, M.DataFaturamento,
                 YEAR(M.DataFaturamento), MONTH(M.DataFaturamento),
                 CASE WHEN M.TipoMov IN ('2.4','2.1','2.5') THEN 'VENDA'
                      WHEN M.TipoMov IN ('1.1') THEN 'COMPRA' ELSE NULL END
    )
    SELECT
        Produto, Ano, Mes, TipoOperacao, SUM(Quantidade) AS Qtd
    FROM DadosBase
    GROUP BY Produto, Ano, Mes, TipoOperacao
    ORDER BY Produto, Ano, Mes
    """
    conn = get_conn()
    df = pd.read_sql(sql, conn, params=(cod_fabr, str(primeiro_dia_12_meses), str(ultimo_dia_mes_anterior)))
    conn.close()
    return df


# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================
def fmt_num(v):
    if pd.isna(v) or v == 0:
        return "—"
    return f"{int(v):,}".replace(",", ".")


def kpi_html(label, value, sub="", accent=""):
    cls = f"accent-{accent}" if accent else ""
    sub_html = f'<div class="kpi-sub" style="font-size:0.78rem; color:#95A5A6; margin-top:2px;">{sub}</div>' if sub else ""
    return f"""
    <div class="kpi-card {cls}">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        {sub_html}
    </div>"""


def pivotar_dados(df_raw):
    """
    Transforma os dados agregados em uma tabela pivoteada com colunas:
    Produto | jul/25 Vend | jul/25 Comp | ... | jun/26 Vend | jun/26 Comp | Total Vend | Total Comp
    """
    if df_raw.empty:
        return pd.DataFrame()

    # Criar MesAno formatado
    df_raw["MesAno"] = pd.to_datetime(df_raw[["Ano", "Mes"]].assign(day=1))
    df_raw["MesAnoStr"] = df_raw["MesAno"].dt.strftime("%m/%Y")

    # Separar vendas e compras
    df_venda  = df_raw[df_raw["TipoOperacao"] == "VENDA"].copy()
    df_compra = df_raw[df_raw["TipoOperacao"] == "COMPRA"].copy()

    # Pivotar vendas
    pivot_venda = df_venda.pivot_table(
        index="Produto",
        columns="MesAnoStr",
        values="Qtd",
        aggfunc="sum",
        fill_value=0,
    )

    # Pivotar compras
    pivot_compra = df_compra.pivot_table(
        index="Produto",
        columns="MesAnoStr",
        values="Qtd",
        aggfunc="sum",
        fill_value=0,
    )

    # Obter todos os meses presentes
    meses_venda  = set(pivot_venda.columns)
    meses_compra = set(pivot_compra.columns)
    todos_meses  = sorted(meses_venda | meses_compra, key=lambda x: (int(x.split("/")[1]), int(x.split("/")[0])))

    # Garantir que ambos têm todas as colunas
    for mes in todos_meses:
        if mes not in pivot_venda.columns:
            pivot_venda[mes] = 0
        if mes not in pivot_compra.columns:
            pivot_compra[mes] = 0

    pivot_venda  = pivot_venda[todos_meses]
    pivot_compra = pivot_compra[todos_meses]

    # Criar DataFrame final intercalando vendas e compras
    df_final = pd.DataFrame(index=pivot_venda.index)

    for mes in todos_meses:
        df_final[f"{mes} Vend"] = pivot_venda[mes]
        df_final[f"{mes} Comp"] = pivot_compra[mes]

    # Totais
    df_final["Total Vendido"]  = pivot_venda.sum(axis=1)
    df_final["Total Comprado"] = pivot_compra.sum(axis=1)

    # Ordenar por total vendido DESC
    df_final = df_final.sort_values("Total Vendido", ascending=False).reset_index()

    return df_final


# ============================================================================
# SIDEBAR
# ============================================================================
with st.sidebar:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=120)
    st.markdown("### 📦 Relatório Fornecedor")
    st.markdown("---")

    # Carregar fornecedores
    df_fornecedores = q_fornecedores()

    if df_fornecedores.empty:
        st.error("Nenhum fornecedor encontrado")
        st.stop()

    # Seleção de fornecedor
    fornecedor_sel = st.selectbox(
        "Selecione o Fornecedor:",
        options=df_fornecedores["CodFabr"].tolist(),
        format_func=lambda x: df_fornecedores[df_fornecedores["CodFabr"] == x]["NomeFabr"].iloc[0],
        key="sel_fornecedor",
    )

    st.markdown("---")

    # Toggle para mostrar/esconder colunas de compra
    mostrar_compras = st.checkbox("Mostrar colunas de Compra", value=True, key="toggle_compras")
    mostrar_vendas = st.checkbox("Mostrar colunas de Venda", value=True, key="toggle_vendas")

    st.markdown("---")
    st.caption(f"📅 Hoje: {HOJE.strftime('%d/%m/%Y')}")
    st.caption("📊 Últimos 12 meses fechados")

    render_logout_sidebar(_auth_user)


# ============================================================================
# CARREGAR DADOS
# ============================================================================
nome_fornecedor = df_fornecedores[df_fornecedores["CodFabr"] == fornecedor_sel]["NomeFabr"].iloc[0]

with st.spinner(f"🔄 Carregando dados de {nome_fornecedor}..."):
    df_raw = q_vendas_compras_fornecedor(fornecedor_sel)

if df_raw.empty:
    st.warning(f"Nenhum dado de vendas ou compras encontrado para **{nome_fornecedor}** nos últimos 12 meses.")
    st.stop()

# Pivotar dados
df_pivot = pivotar_dados(df_raw)

if df_pivot.empty:
    st.warning(f"Erro ao processar dados de **{nome_fornecedor}**.")
    st.stop()


# ============================================================================
# HEADER
# ============================================================================
hcol1, hcol2 = st.columns([1, 5])
with hcol1:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=70)
with hcol2:
    st.markdown(f"## 📦 RELATÓRIO DE VENDAS E COMPRAS")
    st.caption(f"{nome_fornecedor} · Últimos 12 meses fechados")

st.markdown("---")


# ============================================================================
# KPIs
# ============================================================================
total_vendido  = df_pivot["Total Vendido"].sum()
total_comprado = df_pivot["Total Comprado"].sum()
n_produtos     = len(df_pivot)
media_vendida  = total_vendido / 12 if total_vendido > 0 else 0

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(kpi_html("Total Vendido (12m)", fmt_num(total_vendido), "Quantidade total", "green"), unsafe_allow_html=True)
with c2:
    st.markdown(kpi_html("Total Comprado (12m)", fmt_num(total_comprado), "Quantidade total"), unsafe_allow_html=True)
with c3:
    st.markdown(kpi_html("Média Mensal Vendida", fmt_num(media_vendida), "Por mês", "yellow"), unsafe_allow_html=True)
with c4:
    st.markdown(kpi_html("Produtos Ativos", str(n_produtos), "No período"), unsafe_allow_html=True)

st.markdown("")


# ============================================================================
# FILTRAR COLUNAS CONFORME TOGGLE
# ============================================================================
colunas_exibir = ["Produto"]

# Coletar colunas de mês (Vend e Comp)
colunas_meses = [c for c in df_pivot.columns if c not in ["Produto", "Total Vendido", "Total Comprado"]]

for col in colunas_meses:
    if col.endswith(" Vend") and mostrar_vendas:
        colunas_exibir.append(col)
    elif col.endswith(" Comp") and mostrar_compras:
        colunas_exibir.append(col)

# Adicionar totais se os respectivos tipos estão visíveis
if mostrar_vendas:
    colunas_exibir.append("Total Vendido")
if mostrar_compras:
    colunas_exibir.append("Total Comprado")

df_display = df_pivot[colunas_exibir].copy()


# ============================================================================
# TABELA
# ============================================================================
st.markdown(f'<div style="color:#1B3A5C; font-size:1.05rem; font-weight:600; border-bottom:2px solid #E8F4FD; padding-bottom:8px; margin:20px 0 14px 0;">📊 Vendas e Compras por Produto — {nome_fornecedor}</div>', unsafe_allow_html=True)

# Formatar colunas numéricas
format_dict = {}
for col in df_display.columns:
    if col != "Produto":
        format_dict[col] = "{:,.0f}"

st.dataframe(
    df_display.style.format(format_dict).applymap(
        lambda v: "background-color: #FFF3CD;" if isinstance(v, (int, float)) and v == 0 else "",
        subset=[c for c in df_display.columns if c != "Produto"]
    ),
    use_container_width=True,
    height=600,
)


# ============================================================================
# DOWNLOAD CSV
# ============================================================================
st.markdown("")

# Gerar CSV completo (com todas as colunas)
csv = df_pivot.to_csv(index=False, sep=";", decimal=",")

st.download_button(
    label="📥 Baixar Relatório Completo (CSV)",
    data=csv,
    file_name=f"vendas_compras_{fornecedor_sel}_{HOJE.strftime('%Y%m%d')}.csv",
    mime="text/csv",
    use_container_width=False,
)

st.caption("💡 **Dica:** O arquivo CSV contém todas as colunas (vendas e compras), independente do filtro aplicado acima.")


# ============================================================================
# GUIA DE USO
# ============================================================================
with st.expander("📖 Como usar este relatório"):
    st.markdown("""
    ### 📊 Finalidade

    Este relatório mostra a **quantidade vendida** e a **quantidade comprada** de cada produto
    do fornecedor selecionado, mês a mês, nos **últimos 12 meses fechados** (não inclui o mês atual).

    ---

    ### 🔍 Interpretação

    - **jul/25 Vend** = Quantidade vendida em julho de 2025
    - **jul/25 Comp** = Quantidade comprada (entrada de estoque) em julho de 2025
    - **Total Vendido** = Soma de todas as vendas nos 12 meses
    - **Total Comprado** = Soma de todas as compras nos 12 meses

    ---

    ### ✅ Aplicações Práticas

    1. **Ressuprimento:** Compare a quantidade comprada vs vendida para identificar produtos com estoque desbalanceado.
    2. **Planejamento de Compras:** Use a média mensal vendida para calcular a quantidade ideal de reposição.
    3. **Análise de Sazonalidade:** Identifique meses com picos de venda para ajustar compras antecipadamente.
    4. **Copy & Paste para Excel:** Use o botão de download ou copie diretamente da tabela para sua planilha de ressuprimento.

    ---

    ### 🛠️ Filtros

    - **Mostrar colunas de Venda:** Exibe/oculta as colunas "Vend" de cada mês
    - **Mostrar colunas de Compra:** Exibe/oculta as colunas "Comp" de cada mês

    O arquivo CSV baixado sempre contém todas as colunas.
    """)


# ============================================================================
# RODAPÉ
# ============================================================================
st.markdown("---")
st.caption(
    f"GM Limpeza — Relatório de Vendas e Compras por Fornecedor · "
    f"{nome_fornecedor} · {HOJE.strftime('%d/%m/%Y')} · "
    f"Desenvolvido por Victor Monteiro"
)
