"""
GM Limpeza — Dashboard de Vendas v1.0
Lê exclusivamente dos Parquets gerados pelo ETL (scripts/etl_cache.py).
"""

import calendar
import json
import re
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime, timedelta
from pathlib import Path
import numpy as np

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

LOGO_PATH  = Path(__file__).parent / "assets" / "logo.jpg"
CACHE_DIR  = Path(__file__).parent.parent / "cache"
PREFS_FILE = CACHE_DIR / "user_prefs.json"

# ============================================================================
# PÁGINA E CSS
# ============================================================================
st.set_page_config(
    page_title="GM Limpeza — Dashboard de Vendas",
    page_icon="🧹",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
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
    .kpi-sub {
        font-size: 0.78rem;
        color: #95A5A6;
        margin-top: 2px;
    }

    /* Supervisor Card */
    .sup-card {
        background: #FFFFFF;
        border: 2px solid #2E6BA6;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 2px 12px rgba(0,0,0,0.06);
    }
    .sup-card h3 {
        color: #2E6BA6;
        margin: 0 0 12px 0;
        font-size: 1.15rem;
    }
    .sup-stat {
        display: inline-block;
        text-align: center;
        padding: 0 16px;
    }
    .sup-stat .num { font-size: 1.2rem; font-weight: 700; color: #1B3A5C; }
    .sup-stat .lbl { font-size: 0.7rem; color: #95A5A6; text-transform: uppercase; }

    /* Section */
    .section-title {
        color: #1B3A5C;
        font-size: 1.05rem;
        font-weight: 600;
        border-bottom: 2px solid #E8F4FD;
        padding-bottom: 8px;
        margin: 20px 0 14px 0;
    }

    /* Ranking */
    .rank-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 12px;
        border-radius: 6px;
        margin-bottom: 4px;
    }
    .rank-row:nth-child(odd) { background: #F7FAFC; }
    .rank-name { font-weight: 600; color: #1B3A5C; }
    .rank-value { color: #2E6BA6; font-weight: 700; }
    .rank-sub { font-size: 0.78rem; color: #95A5A6; }

    /* Esconder menu e footer */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Abas */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 8px 20px;
        font-weight: 600;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] > div {
        background: linear-gradient(180deg, #1B3A5C 0%, #2E6BA6 100%);
    }
    [data-testid="stSidebar"] .stMarkdown p,
    [data-testid="stSidebar"] .stMarkdown h3,
    [data-testid="stSidebar"] .stCaption {
        color: #E8F4FD !important;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================
def fmt_brl(v):
    """Formata valor em Reais."""
    if pd.isna(v): return "R$ 0"
    if abs(v) >= 1_000_000: return f"R$ {v/1_000_000:,.2f}M"
    if abs(v) >= 1_000: return f"R$ {v/1_000:,.1f}K"
    return f"R$ {v:,.2f}"

def fmt_num(v):
    """Formata número com separador de milhar."""
    return f"{int(v):,}".replace(",", ".")

def fmt_pct(v):
    """Formata percentual."""
    return f"{v:.1f}%"

def kpi_html(label, value, sub="", accent=""):
    """Retorna HTML de um KPI card."""
    cls = f"accent-{accent}" if accent else ""
    sub_html = f'<div class="kpi-sub">{sub}</div>' if sub else ""
    return f"""
    <div class="kpi-card {cls}">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        {sub_html}
    </div>"""

def dias_uteis_entre(d1, d2):
    """Conta dias úteis entre duas datas."""
    dias = pd.bdate_range(d1, d2)
    return len(dias)

def cor_rentabilidade(val, media):
    """Retorna cor baseada na rentabilidade vs média."""
    if val >= media * 1.1: return CORES["verde"]
    if val >= media * 0.9: return CORES["amarelo"]
    return CORES["vermelho"]


# ---- Cache local (Parquet) -------------------------------------------------

@st.cache_data(ttl=1800)
def _load_mov():
    """Lê movimentos.parquet. Retorna (df, timestamp) ou (None, None)."""
    p = CACHE_DIR / "movimentos.parquet"
    if not p.exists():
        return None, None
    df = pd.read_parquet(p)
    df["DataFaturamento"] = pd.to_datetime(df["DataFaturamento"])
    df["MesAno"]    = df["DataFaturamento"].dt.to_period("M").dt.to_timestamp()
    df["MesAnoStr"] = df["DataFaturamento"].dt.strftime("%m/%Y")
    df["Supervisor"] = df["Supervisor"].fillna("Outros")
    df["Vendedor"]   = df["Vendedor"].fillna("Sem vendedor")
    ts = datetime.fromtimestamp(p.stat().st_mtime).strftime("%d/%m/%Y %H:%M")
    return df, ts

@st.cache_data(ttl=1800)
def _load_itens():
    """Lê itens.parquet. Retorna df ou None."""
    p = CACHE_DIR / "itens.parquet"
    if not p.exists():
        return None
    df = pd.read_parquet(p)
    df["DataFaturamento"] = pd.to_datetime(df["DataFaturamento"])
    return df

@st.cache_data(ttl=1800)
def _load_cli_contact():
    """CodCliFor → Celular (WhatsApp) do radar_clientes.parquet."""
    p = CACHE_DIR / "radar_clientes.parquet"
    if not p.exists():
        return None
    df = pd.read_parquet(p, columns=["CodCliFor", "Celular"])
    return df.drop_duplicates("CodCliFor")[["CodCliFor", "Celular"]].copy()


@st.cache_data(ttl=1800)
def _load_clientes_info():
    """CodCliFor → Regiao, Segmento do clientes_info.parquet."""
    p = CACHE_DIR / "clientes_info.parquet"
    if not p.exists():
        return None
    return pd.read_parquet(p)


@st.cache_data(ttl=1800)
def _load_pedidos_pendentes():
    """Lê pedidos_pendentes.parquet gerado pelo ETL."""
    p = CACHE_DIR / "pedidos_pendentes.parquet"
    if not p.exists():
        return None
    df = pd.read_parquet(p)
    df["Data"] = pd.to_datetime(df["Data"])
    return df


def _load_prefs() -> dict:
    if PREFS_FILE.exists():
        try:
            with open(PREFS_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_prefs(prefs: dict):
    try:
        with open(PREFS_FILE, "w", encoding="utf-8") as f:
            json.dump(prefs, f)
    except Exception:
        pass


def _fmt_whatsapp(celular) -> str:
    if not celular or str(celular).strip() in ("", "nan", "None"):
        return ""
    num = re.sub(r"\D", "", str(celular))
    if len(num) < 10:
        return ""
    return f"55{num}" if not num.startswith("55") else num


def _phone_display(celular) -> str:
    if not celular or str(celular).strip() in ("", "nan", "None"):
        return ""
    num = re.sub(r"\D", "", str(celular))
    if num.startswith("55") and len(num) > 11:
        num = num[2:]
    if len(num) == 11:
        return f"({num[:2]}) {num[2:7]}-{num[7:]}"
    if len(num) == 10:
        return f"({num[:2]}) {num[2:6]}-{num[6:]}"
    return num


def _filtrar_mov(dt_ini, dt_fim):
    mov, _ = _load_mov()
    if mov is None:
        return None
    d0, d1 = pd.to_datetime(dt_ini), pd.to_datetime(dt_fim)
    return mov[(mov["DataFaturamento"] >= d0) & (mov["DataFaturamento"] <= d1)]

def _filtrar_itens(dt_ini, dt_fim):
    itens = _load_itens()
    if itens is None:
        return None
    d0, d1 = pd.to_datetime(dt_ini), pd.to_datetime(dt_fim)
    return itens[(itens["DataFaturamento"] >= d0) & (itens["DataFaturamento"] <= d1)]


# ---- Funções de query (somente Parquet) ------------------------------------

@st.cache_data(ttl=1800)
def q_vendas(dt_ini: str, dt_fim: str):
    mov = _filtrar_mov(dt_ini, dt_fim)
    if mov is not None:
        return mov.copy()
    return pd.DataFrame()


@st.cache_data(ttl=1800)
def q_rentabilidade_vendedor(dt_ini: str, dt_fim: str):
    mov   = _filtrar_mov(dt_ini, dt_fim)
    itens = _filtrar_itens(dt_ini, dt_fim)
    if mov is None or itens is None:
        return pd.DataFrame()
    fat = mov.groupby(["CodVendedor", "Vendedor", "Supervisor"]).agg(
        Pedidos    =("IdMov",        "nunique"),
        Faturamento=("ValorLiquido", "sum"),
        DescMedio  =("PercDesconto", "mean"),
    ).reset_index()
    custo = itens.groupby("CodVendedor").agg(CustoTotal=("CustoItem", "sum")).reset_index()
    df = fat.merge(custo, on="CodVendedor", how="left")
    df["CustoTotal"] = df["CustoTotal"].fillna(0)
    df["DescMedio"]  = df["DescMedio"].fillna(0)
    df["Margem"]     = df["Faturamento"] - df["CustoTotal"]
    df["RentPerc"]   = np.where(df["Faturamento"] > 0, df["Margem"] / df["Faturamento"] * 100, 0)
    return df


@st.cache_data(ttl=1800)
def q_rentabilidade_produtos(dt_ini: str, dt_fim: str):
    itens = _filtrar_itens(dt_ini, dt_fim)
    if itens is None:
        return pd.DataFrame()
    df = itens.groupby(["IdProduto", "Produto", "Grupo"]).agg(
        QtdVendida =("Qtd",        "sum"),
        Receita    =("ReceitaItem","sum"),
        CustoTotal =("CustoItem",  "sum"),
    ).reset_index()
    df = df[df["Receita"] > 0].copy()
    df["Margem"]   = df["Receita"] - df["CustoTotal"]
    df["RentPerc"] = np.where(df["Receita"] > 0, df["Margem"] / df["Receita"] * 100, 0)
    return df


@st.cache_data(ttl=1800)
def q_primeira_compra():
    mov, _ = _load_mov()
    if mov is None:
        return pd.DataFrame(columns=["CodCliFor", "DataPrimeiraCompra"])
    return (
        mov.groupby("CodCliFor")["DataFaturamento"]
        .min()
        .reset_index()
        .rename(columns={"DataFaturamento": "DataPrimeiraCompra"})
    )


@st.cache_data(ttl=1800)
def q_rentabilidade_clientes(dt_ini: str, dt_fim: str):
    mov   = _filtrar_mov(dt_ini, dt_fim)
    itens = _filtrar_itens(dt_ini, dt_fim)
    if mov is None or itens is None:
        return pd.DataFrame()
    fat = mov.groupby(["CodCliFor", "Cliente", "Vendedor"]).agg(
        Pedidos    =("IdMov",        "nunique"),
        Faturamento=("ValorLiquido", "sum"),
    ).reset_index()
    custo = itens.groupby("CodCliFor").agg(CustoTotal=("CustoItem", "sum")).reset_index()
    df = fat.merge(custo, on="CodCliFor", how="left")
    df = df[df["Faturamento"] > 0].copy()
    df["CustoTotal"]  = df["CustoTotal"].fillna(0)
    df["Vendedor"]    = df["Vendedor"].fillna("Sem vendedor")
    df["Margem"]      = df["Faturamento"] - df["CustoTotal"]
    df["RentPerc"]    = np.where(df["Faturamento"] > 0, df["Margem"] / df["Faturamento"] * 100, 0)
    df["TicketMedio"] = np.where(df["Pedidos"] > 0, df["Faturamento"] / df["Pedidos"], 0)
    return df


# ============================================================================
# SIDEBAR
# ============================================================================
with st.sidebar:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=130)
    st.markdown("### ⚙️ Configurações")
    st.markdown("---")

    _hoje = date.today()
    _fim_mes = _hoje.replace(day=calendar.monthrange(_hoje.year, _hoje.month)[1])
    col1, col2 = st.columns(2)
    with col1:
        dt_inicio = st.date_input("Início", value=_hoje.replace(day=1), format="DD/MM/YYYY")
    with col2:
        dt_fim = st.date_input("Fim", value=_fim_mes, format="DD/MM/YYYY")

    meta_mensal = st.number_input(
        "Meta do período (R$)",
        min_value=0,
        value=1_600_000,
        step=100_000,
        format="%d"
    )

    st.markdown("---")
    st.caption(f"📅 {dt_inicio.strftime('%d/%m/%Y')} a {dt_fim.strftime('%d/%m/%Y')}")
    _, _ts = _load_mov()
    if _ts:
        st.caption(f"📦 Cache de {_ts}")
    else:
        st.caption("⚠️ Consultando banco ao vivo")


# ============================================================================
# CARREGAR DADOS
# ============================================================================
_, _ts = _load_mov()
if not _ts:
    st.error("❌ Cache indisponível — execute o ETL para gerar os arquivos Parquet.")
    st.code("python scripts/etl_cache.py")
    st.stop()

with st.spinner("🔄 Carregando do cache..."):
    df_vendas = q_vendas(str(dt_inicio), str(dt_fim))
    df_rv = q_rentabilidade_vendedor(str(dt_inicio), str(dt_fim))
    df_rp = q_rentabilidade_produtos(str(dt_inicio), str(dt_fim))
    df_rc = q_rentabilidade_clientes(str(dt_inicio), str(dt_fim))

if df_vendas.empty:
    st.warning("Nenhum dado encontrado para o período selecionado.")
    st.stop()

# Filtro de vendedor com persistência
with st.sidebar:
    vendedores_lista = sorted(df_vendas["Vendedor"].dropna().unique())
    _prefs = _load_prefs()
    _saved_vend = [v for v in _prefs.get("app_vendedor_sel", []) if v in vendedores_lista]

    def _save_app_vendor():
        p = _load_prefs()
        p["app_vendedor_sel"] = st.session_state.get("app_vend_key", [])
        _save_prefs(p)

    vendedor_sel = st.multiselect(
        "Filtrar Vendedor", vendedores_lista,
        default=_saved_vend,
        placeholder="Todos os vendedores",
        key="app_vend_key",
        on_change=_save_app_vendor,
    )

if vendedor_sel:
    df_vendas = df_vendas[df_vendas["Vendedor"].isin(vendedor_sel)]
    df_rv = df_rv[df_rv["Vendedor"].isin(vendedor_sel)]
    df_rc = df_rc[df_rc["Vendedor"].isin(vendedor_sel)]


# ============================================================================
# MÉTRICAS GLOBAIS
# ============================================================================
fat_total = df_vendas["ValorLiquido"].sum()
qtd_pedidos = df_vendas["IdMov"].nunique()
qtd_clientes = df_vendas["CodCliFor"].nunique()
rent_total = df_rv["Margem"].sum()
rent_perc = (rent_total / fat_total * 100) if fat_total > 0 else 0
ticket_medio = fat_total / qtd_pedidos if qtd_pedidos > 0 else 0

dias_uteis_total = dias_uteis_entre(dt_inicio, dt_fim)
dias_uteis_passados = dias_uteis_entre(dt_inicio, min(date.today(), dt_fim))
dias_uteis_restantes = max(0, dias_uteis_total - dias_uteis_passados)

media_diaria = fat_total / dias_uteis_passados if dias_uteis_passados > 0 else 0
faltando_meta = max(0, meta_mensal - fat_total)
meta_diaria_restante = faltando_meta / dias_uteis_restantes if dias_uteis_restantes > 0 else 0
projecao = fat_total + (media_diaria * dias_uteis_restantes)
pct_meta = (fat_total / meta_mensal * 100) if meta_mensal > 0 else 0


# ============================================================================
# HEADER
# ============================================================================
hcol1, hcol2, hcol3 = st.columns([1, 5, 3])
with hcol1:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=70)
with hcol2:
    st.markdown(f"## GM LIMPEZA")
    st.caption(f"Dashboard de Vendas · {dt_inicio.strftime('%d/%m/%Y')} a {dt_fim.strftime('%d/%m/%Y')}")
with hcol3:
    st.markdown(f"""
    <div style="text-align:right; padding-top:8px;">
        <span style="font-size:0.8rem; color:#95A5A6;">FATURAMENTO ATUAL</span><br>
        <span style="font-size:2rem; font-weight:700; color:#F39C12;">{fmt_brl(fat_total)}</span><br>
        <span style="font-size:0.8rem; color:#E74C3C;">Meta: {fmt_brl(meta_mensal)} · Faltando: {fmt_brl(faltando_meta)}</span>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")


# ============================================================================
# ABAS
# ============================================================================
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "📊 Visão Geral",
    "👥 Por Supervisor",
    "📈 Gráficos",
    "📋 Detalhamento",
    "📦 Produtos",
    "🏢 Clientes",
    "📅 Pivot Mensal",
    "📖 Guia de Uso",
])


# ======================== ABA 1 — VISÃO GERAL ========================
with tab1:
    # KPIs
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(kpi_html("Faturamento Total", fmt_brl(fat_total), f"{fmt_pct(pct_meta)} da meta"), unsafe_allow_html=True)
    with c2:
        st.markdown(kpi_html("Total de Pedidos", fmt_num(qtd_pedidos), "Pedidos realizados"), unsafe_allow_html=True)
    with c3:
        st.markdown(kpi_html("Rentabilidade", fmt_pct(rent_perc), fmt_brl(rent_total), "green"), unsafe_allow_html=True)
    with c4:
        st.markdown(kpi_html("Meta Diária Necessária", fmt_brl(meta_diaria_restante), f"Para atingir a meta em {dias_uteis_restantes} dias", "yellow"), unsafe_allow_html=True)

    st.markdown("")
    c5, c6, c7, c8 = st.columns(4)
    with c5:
        st.markdown(kpi_html("Média Diária Atual", fmt_brl(media_diaria), f"Últimos {dias_uteis_passados} dias úteis"), unsafe_allow_html=True)
    with c6:
        st.markdown(kpi_html("Faturamento Faltante", fmt_brl(faltando_meta), f"Para atingir {fmt_brl(meta_mensal)}"), unsafe_allow_html=True)
    with c7:
        st.markdown(kpi_html("Clientes Ativos", fmt_num(qtd_clientes), "No período"), unsafe_allow_html=True)
    with c8:
        st.markdown(kpi_html("Dias Úteis Restantes", str(dias_uteis_restantes), "Para o fim do período"), unsafe_allow_html=True)

    # Progresso da Meta
    st.markdown("")
    mc1, mc2 = st.columns([1, 2])
    with mc1:
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=pct_meta,
            number={"suffix": "%", "font": {"size": 42, "color": CORES["azul_escuro"]}},
            title={"text": "Progresso da Meta", "font": {"size": 14, "color": CORES["cinza"]}},
            gauge={
                "axis": {"range": [0, 100], "ticksuffix": "%"},
                "bar": {"color": CORES["amarelo"]},
                "bgcolor": CORES["azul_gelo"],
                "steps": [
                    {"range": [0, 50], "color": "#FDE8E8"},
                    {"range": [50, 80], "color": "#FEF3CD"},
                    {"range": [80, 100], "color": "#D4EDDA"},
                ],
                "threshold": {"line": {"color": CORES["vermelho"], "width": 3}, "value": 100},
            },
        ))
        fig_gauge.update_layout(height=250, margin=dict(t=40, b=20, l=30, r=30))
        st.plotly_chart(fig_gauge, use_container_width=True)

    with mc2:
        # Projeção de Faturamento
        fat_diario = df_vendas.groupby(df_vendas["DataFaturamento"].dt.date)["ValorLiquido"].sum().reset_index()
        fat_diario.columns = ["Data", "Faturamento"]
        fat_diario = fat_diario.sort_values("Data")
        fat_diario["Acumulado"] = fat_diario["Faturamento"].cumsum()
        fat_diario["Tipo"] = "Realizado"

        # Projeção
        if dias_uteis_restantes > 0:
            ultima_data = fat_diario["Data"].max()
            datas_futuras = pd.bdate_range(start=ultima_data + timedelta(days=1), periods=dias_uteis_restantes)
            acum_atual = fat_diario["Acumulado"].iloc[-1]
            proj_rows = []
            for i, d in enumerate(datas_futuras):
                acum_atual += media_diaria
                proj_rows.append({"Data": d.date(), "Faturamento": media_diaria, "Acumulado": acum_atual, "Tipo": "Projeção"})
            df_proj = pd.concat([fat_diario, pd.DataFrame(proj_rows)], ignore_index=True)
        else:
            df_proj = fat_diario.copy()

        fig_proj = go.Figure()
        real = df_proj[df_proj["Tipo"] == "Realizado"]
        proj = df_proj[df_proj["Tipo"] == "Projeção"]

        fig_proj.add_trace(go.Scatter(x=real["Data"], y=real["Acumulado"], mode="lines+markers",
            name="Realizado", line=dict(color=CORES["azul_medio"], width=3), marker=dict(size=4)))

        if not proj.empty:
            # Conectar com último ponto real
            bridge = pd.DataFrame([real.iloc[-1]])
            bridge["Tipo"] = "Projeção"
            proj_plot = pd.concat([bridge, proj], ignore_index=True)
            fig_proj.add_trace(go.Scatter(x=proj_plot["Data"], y=proj_plot["Acumulado"], mode="lines",
                name="Projeção", line=dict(color=CORES["amarelo"], width=3, dash="dash")))

        fig_proj.add_hline(y=meta_mensal, line_dash="dot", line_color=CORES["vermelho"],
            annotation_text=f"META {fmt_brl(meta_mensal)}", annotation_position="top left")

        atinge = "✅ Atingirá a meta" if projecao >= meta_mensal else "⚠️ Abaixo da meta"
        fig_proj.update_layout(
            title=f"Projeção de Faturamento — {atinge} ({fmt_brl(projecao)})",
            height=300, margin=dict(t=50, b=30, l=50, r=20),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(gridcolor="#E8F4FD", tickformat=",.0f"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig_proj, use_container_width=True)


# ======================== ABA 2 — POR SUPERVISOR ========================
with tab2:
    sup_data = df_rv.groupby("Supervisor").agg(
        Faturamento=("Faturamento", "sum"),
        Pedidos=("Pedidos", "sum"),
        Margem=("Margem", "sum"),
        Vendedores=("Vendedor", "nunique"),
    ).reset_index()
    sup_data["RentPerc"] = np.where(sup_data["Faturamento"] > 0, sup_data["Margem"] / sup_data["Faturamento"] * 100, 0)
    sup_data = sup_data.sort_values("Faturamento", ascending=False)

    # Cards de supervisor
    sup_cols = st.columns(len(sup_data))
    for i, (_, row) in enumerate(sup_data.iterrows()):
        with sup_cols[i]:
            st.markdown(f"""
            <div class="sup-card">
                <h3>👔 {row['Supervisor']}</h3>
                <div style="font-size:1.4rem; font-weight:700; color:#1B3A5C;">{fmt_brl(row['Faturamento'])}</div>
                <div style="font-size:0.8rem; color:#95A5A6; margin-bottom:12px;">
                    {int(row['Vendedores'])} vendedor(es) · {fmt_num(row['Pedidos'])} pedidos
                </div>
                <div style="display:flex; justify-content:space-around; border-top:1px solid #E8F4FD; padding-top:10px;">
                    <div class="sup-stat"><div class="num">{fmt_brl(row['Margem'])}</div><div class="lbl">Rentab. R$</div></div>
                    <div class="sup-stat"><div class="num">{fmt_pct(row['RentPerc'])}</div><div class="lbl">Rentab. %</div></div>
                </div>
            </div>""", unsafe_allow_html=True)

    st.markdown("")

    # Ranking por equipe
    for _, sup_row in sup_data.iterrows():
        sup_name = sup_row["Supervisor"]
        st.markdown(f'<div class="section-title">🏆 Ranking — Equipe {sup_name}</div>', unsafe_allow_html=True)

        equipe = df_rv[df_rv["Supervisor"] == sup_name].sort_values("Faturamento", ascending=False)
        for rank, (_, v) in enumerate(equipe.iterrows(), 1):
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"{rank}.")
            st.markdown(f"""
            <div class="rank-row">
                <div><span style="margin-right:8px;">{medal}</span>
                    <span class="rank-name">{v['Vendedor']}</span></div>
                <div style="text-align:right;">
                    <span class="rank-value">{fmt_brl(v['Faturamento'])}</span><br>
                    <span class="rank-sub">{fmt_num(v['Pedidos'])} pedidos · {fmt_pct(v['RentPerc'])} rent.</span>
                </div>
            </div>""", unsafe_allow_html=True)

    # Pizza divisão por supervisor
    st.markdown('<div class="section-title">📊 Divisão por Supervisor</div>', unsafe_allow_html=True)
    fig_pizza = px.pie(sup_data, values="Faturamento", names="Supervisor",
        color_discrete_sequence=[CORES["azul_medio"], CORES["azul_claro"], CORES["cinza_claro"]],
        hole=0.4)
    fig_pizza.update_traces(textinfo="percent+label", textfont_size=13)
    fig_pizza.update_layout(height=350, margin=dict(t=20, b=20))
    st.plotly_chart(fig_pizza, use_container_width=True)

    for _, r in sup_data.iterrows():
        pct = r["Faturamento"] / fat_total * 100 if fat_total > 0 else 0
        st.markdown(f"**Equipe {r['Supervisor']}** — {fmt_brl(r['Faturamento'])} ({fmt_pct(pct)})")


# ======================== ABA 3 — GRÁFICOS ========================
with tab3:
    # Ranking de Faturamento
    st.markdown('<div class="section-title">📊 Ranking de Faturamento por Vendedor</div>', unsafe_allow_html=True)

    rv_sorted = df_rv.sort_values("Faturamento", ascending=True)
    fig_rank = go.Figure(go.Bar(
        y=rv_sorted["Vendedor"], x=rv_sorted["Faturamento"], orientation="h",
        marker_color=[CORES["azul_medio"] if s != "Outros" else CORES["cinza_claro"]
                      for s in rv_sorted["Supervisor"]],
        text=rv_sorted["Faturamento"].apply(fmt_brl),
        textposition="outside", textfont=dict(size=10),
    ))
    fig_rank.update_layout(
        height=max(350, len(rv_sorted) * 35),
        margin=dict(t=10, b=20, l=140, r=80),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(gridcolor="#E8F4FD"),
    )
    st.plotly_chart(fig_rank, use_container_width=True)

    # Rentabilidade por Vendedor
    st.markdown('<div class="section-title">📊 Rentabilidade por Vendedor (%)</div>', unsafe_allow_html=True)
    media_rent = df_rv["RentPerc"].mean()

    rv_rent = df_rv[df_rv["Faturamento"] > 0].sort_values("RentPerc", ascending=True)
    cores_rent = [cor_rentabilidade(r, media_rent) for r in rv_rent["RentPerc"]]

    fig_rent = go.Figure(go.Bar(
        y=rv_rent["Vendedor"], x=rv_rent["RentPerc"], orientation="h",
        marker_color=cores_rent,
        text=rv_rent["RentPerc"].apply(fmt_pct),
        textposition="outside", textfont=dict(size=10),
    ))
    fig_rent.add_vline(x=media_rent, line_dash="dash", line_color=CORES["vermelho"],
        annotation_text=f"Média {fmt_pct(media_rent)}", annotation_position="top right")
    fig_rent.update_layout(
        height=max(350, len(rv_rent) * 35),
        margin=dict(t=10, b=20, l=140, r=80),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(gridcolor="#E8F4FD", title="% Rentabilidade"),
    )
    st.plotly_chart(fig_rent, use_container_width=True)


# ======================== ABA 4 — DETALHAMENTO ========================
with tab4:
    st.markdown('<div class="section-title">📋 Detalhamento por Vendedor</div>', unsafe_allow_html=True)

    # Filtro por supervisor
    sup_filter = st.radio("Filtrar por supervisor:", ["Todos"] + list(sup_data["Supervisor"]), horizontal=True)

    detail = df_rv.copy()
    if sup_filter != "Todos":
        detail = detail[detail["Supervisor"] == sup_filter]

    detail = detail.sort_values("Faturamento", ascending=False).reset_index(drop=True)
    detail.index = detail.index + 1

    st.dataframe(
        detail[["Vendedor", "Pedidos", "Faturamento", "DescMedio", "RentPerc", "Margem"]].rename(columns={
            "Faturamento": "Faturamento (R$)",
            "DescMedio": "Desc. Médio %",
            "RentPerc": "Rent. %",
            "Margem": "Margem (R$)",
        }).style.format({
            "Faturamento (R$)": "R$ {:,.2f}",
            "Desc. Médio %": "{:.2f}%",
            "Rent. %": "{:.2f}%",
            "Margem (R$)": "R$ {:,.2f}",
        }),
        use_container_width=True,
    )

    # Totais
    st.markdown(f"""
    **TOTAL ({len(detail)} vendedores)** — {fmt_num(detail['Pedidos'].sum())} pedidos ·
    {fmt_brl(detail['Faturamento'].sum())} faturamento ·
    {fmt_pct(detail['RentPerc'].mean())} rentabilidade média
    """)

    # Pedidos Pendentes
    st.markdown('<div class="section-title">📋 Pedidos Pendentes (não faturados)</div>', unsafe_allow_html=True)
    _df_pend_all = _load_pedidos_pendentes()
    if _df_pend_all is None:
        st.warning("Cache de pedidos pendentes indisponível — execute o ETL para gerar o arquivo.")
    else:
        df_pend = _df_pend_all.copy()
        if vendedor_sel:
            df_pend = df_pend[df_pend["Vendedor"].isin(vendedor_sel)]
        if df_pend.empty:
            st.info("Nenhum pedido pendente para o filtro atual.")
        else:
            _tot_pend = df_pend["ValorTotal"].sum()
            _, _ts_pend = _load_mov()
            _cache_label = f"Cache ETL de {_ts_pend}" if _ts_pend else "Cache ETL"
            st.caption(f"⚠️ {len(df_pend)} pedidos pendentes · {fmt_brl(_tot_pend)} em aberto · {_cache_label}")
            df_pend_show = df_pend[["NumMov", "Data", "Cliente", "Vendedor", "ValorTotal", "QtdItens"]].copy()
            df_pend_show["Data"] = df_pend_show["Data"].dt.strftime("%d/%m/%Y")
            st.dataframe(
                df_pend_show.rename(columns={
                    "NumMov": "Nº Pedido", "ValorTotal": "Valor Total", "QtdItens": "Qtd Itens",
                }).style.format({"Valor Total": "R$ {:,.2f}"}),
                hide_index=True, use_container_width=True, height=300,
            )


# ======================== ABA 5 — PRODUTOS ========================
with tab5:
    col_top, col_bottom = st.columns(2)

    with col_top:
        st.markdown('<div class="section-title">🏆 Top 20 Produtos — Maior Rentabilidade (R$)</div>', unsafe_allow_html=True)
        top_p = df_rp.nlargest(20, "Margem")

        fig_tp = go.Figure(go.Bar(
            y=top_p["Produto"].str[:40], x=top_p["Margem"], orientation="h",
            marker_color=CORES["verde"],
            text=top_p.apply(lambda r: f"{fmt_brl(r['Margem'])} ({fmt_pct(r['RentPerc'])})", axis=1),
            textposition="outside", textfont=dict(size=9),
        ))
        fig_tp.update_layout(
            height=550, margin=dict(t=10, b=20, l=220, r=100),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(gridcolor="#E8F4FD"), yaxis=dict(autorange="reversed"),
        )
        st.plotly_chart(fig_tp, use_container_width=True)

    with col_bottom:
        st.markdown('<div class="section-title">⚠️ Top 20 Produtos — Menor Rentabilidade (%)</div>', unsafe_allow_html=True)
        # Filtrar produtos com receita mínima relevante
        min_receita = st.slider("Receita mínima para filtrar (R$)", 500, 50000, 5000, step=500, key="min_prod")
        worst_p = df_rp[df_rp["Receita"] >= min_receita].nsmallest(20, "RentPerc")

        fig_wp = go.Figure(go.Bar(
            y=worst_p["Produto"].str[:40], x=worst_p["RentPerc"], orientation="h",
            marker_color=[CORES["vermelho"] if v < 15 else CORES["amarelo"] for v in worst_p["RentPerc"]],
            text=worst_p.apply(lambda r: f"{fmt_pct(r['RentPerc'])} ({fmt_brl(r['Receita'])})", axis=1),
            textposition="outside", textfont=dict(size=9),
        ))
        media_prod = df_rp["RentPerc"].mean()
        fig_wp.add_vline(x=media_prod, line_dash="dash", line_color=CORES["azul_medio"],
            annotation_text=f"Média {fmt_pct(media_prod)}")
        fig_wp.update_layout(
            height=550, margin=dict(t=10, b=20, l=220, r=100),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(gridcolor="#E8F4FD", title="% Rentabilidade"), yaxis=dict(autorange="reversed"),
        )
        st.plotly_chart(fig_wp, use_container_width=True)

    # Tabela completa com busca
    st.markdown('<div class="section-title">🔍 Busca de Produtos</div>', unsafe_allow_html=True)
    busca_prod = st.text_input("Buscar produto pelo nome:", "", key="busca_prod")
    df_rp_show = df_rp.copy()
    if busca_prod:
        df_rp_show = df_rp_show[df_rp_show["Produto"].str.contains(busca_prod, case=False, na=False)]

    st.dataframe(
        df_rp_show.sort_values("Margem", ascending=False)
        [["Produto", "Grupo", "QtdVendida", "Receita", "CustoTotal", "Margem", "RentPerc"]]
        .rename(columns={"QtdVendida": "Qtd", "Receita": "Receita (R$)", "CustoTotal": "Custo (R$)",
                         "Margem": "Margem (R$)", "RentPerc": "Rent. %"})
        .style.format({"Qtd": "{:,.0f}", "Receita (R$)": "R$ {:,.2f}", "Custo (R$)": "R$ {:,.2f}",
                       "Margem (R$)": "R$ {:,.2f}", "Rent. %": "{:.1f}%"}),
        hide_index=True, use_container_width=True, height=400,
    )


# ======================== ABA 6 — CLIENTES ========================
with tab6:
    col_tc, col_wc = st.columns(2)

    with col_tc:
        st.markdown('<div class="section-title">🏆 Top 20 Clientes — Maior Rentabilidade (R$)</div>', unsafe_allow_html=True)
        top_c = df_rc.nlargest(20, "Margem")

        fig_tc = go.Figure(go.Bar(
            y=top_c["Cliente"].str[:40], x=top_c["Margem"], orientation="h",
            marker_color=CORES["azul_medio"],
            text=top_c.apply(lambda r: f"{fmt_brl(r['Margem'])} ({fmt_pct(r['RentPerc'])})", axis=1),
            textposition="outside", textfont=dict(size=9),
        ))
        fig_tc.update_layout(
            height=550, margin=dict(t=10, b=20, l=220, r=100),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(gridcolor="#E8F4FD"), yaxis=dict(autorange="reversed"),
        )
        st.plotly_chart(fig_tc, use_container_width=True)

    with col_wc:
        st.markdown('<div class="section-title">⚠️ Top 20 Clientes — Menor Rentabilidade (%)</div>', unsafe_allow_html=True)
        min_fat_cli = st.slider("Faturamento mínimo (R$)", 500, 50000, 5000, step=500, key="min_cli")
        worst_c = df_rc[df_rc["Faturamento"] >= min_fat_cli].nsmallest(20, "RentPerc")

        fig_wc = go.Figure(go.Bar(
            y=worst_c["Cliente"].str[:40], x=worst_c["RentPerc"], orientation="h",
            marker_color=[CORES["vermelho"] if v < 15 else CORES["amarelo"] for v in worst_c["RentPerc"]],
            text=worst_c.apply(lambda r: f"{fmt_pct(r['RentPerc'])} · {r['Vendedor'][:15]}", axis=1),
            textposition="outside", textfont=dict(size=9),
        ))
        media_cli = df_rc["RentPerc"].mean()
        fig_wc.add_vline(x=media_cli, line_dash="dash", line_color=CORES["azul_medio"],
            annotation_text=f"Média {fmt_pct(media_cli)}")
        fig_wc.update_layout(
            height=550, margin=dict(t=10, b=20, l=220, r=100),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(gridcolor="#E8F4FD", title="% Rentabilidade"), yaxis=dict(autorange="reversed"),
        )
        st.plotly_chart(fig_wc, use_container_width=True)

    # Enriquecer df_rc com metadados cadastrais
    _df_contact = _load_cli_contact()
    _df_cli_info = _load_clientes_info()
    _df_prim = q_primeira_compra()

    df_rc_enrich = df_rc.copy()

    # WhatsApp — vem do radar_clientes.parquet
    if _df_contact is not None:
        df_rc_enrich = df_rc_enrich.merge(_df_contact, on="CodCliFor", how="left")
        df_rc_enrich["WhatsApp"] = df_rc_enrich["Celular"].apply(
            lambda c: f"https://wa.me/{_fmt_whatsapp(c)}" if _fmt_whatsapp(c) else ""
        )
        df_rc_enrich["Celular_Fmt"] = df_rc_enrich["Celular"].apply(_phone_display)
    else:
        df_rc_enrich["WhatsApp"]    = ""
        df_rc_enrich["Celular_Fmt"] = ""

    # Segmento e Região — vêm do clientes_info.parquet (disponível após próximo ETL)
    if _df_cli_info is not None:
        df_rc_enrich = df_rc_enrich.merge(
            _df_cli_info[["CodCliFor", "Regiao", "Segmento"]], on="CodCliFor", how="left"
        )
        df_rc_enrich["Regiao"]   = df_rc_enrich["Regiao"].fillna("Sem Região")
        df_rc_enrich["Segmento"] = df_rc_enrich["Segmento"].fillna("Não Classificado")
    else:
        df_rc_enrich["Regiao"]   = "—"
        df_rc_enrich["Segmento"] = "—"

    # Badge NOVO — primeira compra nos últimos 30 dias
    _hoje_ts = pd.Timestamp.today().normalize()
    if not _df_prim.empty:
        df_rc_enrich = df_rc_enrich.merge(_df_prim, on="CodCliFor", how="left")
        df_rc_enrich["_dias_1a"] = (_hoje_ts - df_rc_enrich["DataPrimeiraCompra"]).dt.days
        df_rc_enrich["Status"]   = df_rc_enrich["_dias_1a"].apply(
            lambda d: "🆕 NOVO" if pd.notna(d) and d <= 30 else ""
        )
    else:
        df_rc_enrich["Status"] = ""

    # Tabela completa com busca e filtros locais
    st.markdown('<div class="section-title">🔍 Busca de Clientes</div>', unsafe_allow_html=True)

    _fc1, _fc2, _fc3 = st.columns([3, 2, 2])
    with _fc1:
        busca_cli = st.text_input("Buscar pelo nome:", "", key="busca_cli")
    with _fc2:
        _seg_opts = sorted(df_rc_enrich["Segmento"].dropna().unique()) if _df_cli_info is not None else []
        seg_sel = st.multiselect("Segmento", _seg_opts, key="seg_cli") if _seg_opts else []
    with _fc3:
        _reg_opts = sorted(df_rc_enrich["Regiao"].dropna().unique()) if _df_cli_info is not None else []
        reg_sel = st.multiselect("Região", _reg_opts, key="reg_cli") if _reg_opts else []

    df_rc_show = df_rc_enrich.copy()
    if busca_cli:
        df_rc_show = df_rc_show[df_rc_show["Cliente"].str.contains(busca_cli, case=False, na=False)]
    if seg_sel:
        df_rc_show = df_rc_show[df_rc_show["Segmento"].isin(seg_sel)]
    if reg_sel:
        df_rc_show = df_rc_show[df_rc_show["Regiao"].isin(reg_sel)]

    # Colunas a exibir
    _cols_base = ["Cliente", "Status", "Vendedor", "Segmento", "Regiao",
                  "Pedidos", "Faturamento", "Margem", "RentPerc", "TicketMedio",
                  "Celular_Fmt", "WhatsApp"]
    _cols_show = [c for c in _cols_base if c in df_rc_show.columns]

    _col_cfg = {
        "Faturamento":  st.column_config.NumberColumn("Faturamento (R$)", format="R$ %.2f"),
        "Margem":       st.column_config.NumberColumn("Margem (R$)",      format="R$ %.2f"),
        "RentPerc":     st.column_config.NumberColumn("Rent. %",          format="%.1f%%"),
        "TicketMedio":  st.column_config.NumberColumn("Ticket Médio",     format="R$ %.2f"),
        "Celular_Fmt":  st.column_config.TextColumn("Celular"),
        "WhatsApp":     st.column_config.LinkColumn("📱", display_text="WA ↗"),
        "Status":       st.column_config.TextColumn("Status"),
    }
    st.dataframe(
        df_rc_show.sort_values("Faturamento", ascending=False)[_cols_show],
        column_config=_col_cfg,
        hide_index=True, use_container_width=True, height=420,
    )


# ======================== ABA 7 — PIVOT MENSAL ========================
with tab7:
    st.markdown('<div class="section-title">📅 Faturamento por Cliente — Pivot Mensal</div>', unsafe_allow_html=True)
    st.caption("Mesma visão do relatório Excel, agora atualizada automaticamente.")

    pivot = df_vendas.pivot_table(
        index=["CodCliFor", "Cliente", "Vendedor"],
        columns="MesAnoStr",
        values="ValorLiquido",
        aggfunc="sum",
        fill_value=0,
    ).reset_index()

    # Ordenar meses cronologicamente
    meses_cols = [c for c in pivot.columns if "/" in str(c)]
    meses_ord = sorted(meses_cols, key=lambda x: (int(x.split("/")[1]), int(x.split("/")[0])))
    pivot = pivot[["CodCliFor", "Cliente", "Vendedor"] + meses_ord]

    n_meses = len(meses_ord)
    pivot["Total"] = pivot[meses_ord].sum(axis=1)
    pivot["Média"] = (pivot["Total"] / n_meses).round(2)

    # Desvio do último mês vs média
    if meses_ord:
        ult = meses_ord[-1]
        pivot["Últ - Média"] = (pivot[ult] - pivot["Média"]).round(2)

    pivot = pivot.sort_values("Total", ascending=False)

    fmt_dict = {c: "R$ {:,.2f}" for c in meses_ord + ["Total", "Média"]}
    if "Últ - Média" in pivot.columns:
        fmt_dict["Últ - Média"] = "R$ {:,.2f}"

    def _color_pivot(df):
        styles = pd.DataFrame("", index=df.index, columns=df.columns)
        if "Média" not in df.columns:
            return styles
        for mes in meses_ord:
            if mes not in df.columns:
                continue
            col = df[mes]
            avg = df["Média"].replace(0, float("nan"))
            styles.loc[col == 0, mes]                            = "background-color:#f5f5f5; color:#aaaaaa"
            styles.loc[col.gt(0) & avg.notna() & col.lt(avg * 0.8), mes] = "background-color:#FFF3CD"
            styles.loc[col.gt(0) & avg.notna() & col.ge(avg * 1.5), mes] = "background-color:#D4EDDA"
        return styles

    _pivot_styled = pivot.style.format(fmt_dict).apply(_color_pivot, axis=None)
    st.dataframe(_pivot_styled, hide_index=True, use_container_width=True, height=600)

    csv = pivot.to_csv(index=False, sep=";", decimal=",")
    st.download_button("📥 Baixar em CSV", csv,
        f"pivot_gm_{dt_inicio.strftime('%Y%m%d')}_{dt_fim.strftime('%Y%m%d')}.csv", "text/csv")


# ======================== ABA 8 — GUIA DE USO ========================
with tab8:
    st.markdown("""
    ## 📖 Guia de Uso do Dashboard

    Este guia orienta como usar o dashboard para tomar decisões que **aumentem o faturamento
    e a rentabilidade** da GM Limpeza.

    ---

    ### 🔴 DIARIAMENTE (5 minutos)

    **O que olhar:** Aba **Visão Geral**

    - O faturamento acumulado está no ritmo da meta?
    - A média diária atual é maior que a meta diária necessária?
    - Se a projeção está abaixo da meta, é hora de agir **hoje** — não no fim do mês.

    **Ação prática:** Se a projeção indica que não vai bater a meta, converse com os supervisores
    para intensificar contato com clientes que compram valores altos (veja aba Clientes).

    ---

    ### 🟡 SEMANALMENTE (15 minutos)

    **O que olhar:** Abas **Por Supervisor** e **Detalhamento**

    - Algum vendedor caiu muito essa semana? Pode ser férias, doença ou desmotivação.
    - O desconto médio de algum vendedor está muito alto? Isso corrói a rentabilidade.
    - Há vendedores com muitos pedidos mas faturamento baixo? Ticket médio baixo = oportunidade de cross-sell.

    **Ação prática:**
    - Vendedor com desconto alto → alinhar política comercial
    - Vendedor com ticket baixo → treinar oferta de produtos complementares
    - Vendedor com poucos pedidos → revisar carteira e metas individuais

    ---

    ### 🟢 MENSALMENTE (30 minutos)

    **O que olhar:** Abas **Produtos**, **Clientes** e **Pivot Mensal**

    #### Produtos
    - Quais produtos geram mais margem em R$? São seus campeões — nunca deixe faltar no estoque.
    - Quais têm margem % muito baixa? Avalie se vale aumentar preço ou parar de vender.
    - Compare mês a mês no Pivot: algum produto caiu de repente? Investigue.

    #### Clientes
    - Os 20 maiores clientes em margem representam quanto do total? Se for mais de 50%, você tem risco
      de concentração — se um sair, o impacto é grande.
    - Clientes com margem % muito baixa: estão recebendo desconto demais? Compram só produtos baratos?
    - Clientes que compravam todo mês e pararam: use o Pivot para identificar e acionar o vendedor.

    ---

    ### 📊 Como Interpretar a Rentabilidade

    | Faixa | Significado | Ação |
    |-------|------------|------|
    | **> 30%** | Excelente | Manter e replicar |
    | **25-30%** | Saudável | Meta ideal para a maioria |
    | **20-25%** | Atenção | Revisar descontos e mix |
    | **< 20%** | Crítico | Investigar urgente |

    A rentabilidade é calculada como: **(Faturamento - Custo) / Faturamento × 100**

    ---

    ### 🎯 As 3 Alavancas para Aumentar o Faturamento

    1. **Aumentar frequência** — clientes que compram 1x/mês podem comprar 2x. Use o Pivot para
       identificar clientes com intervalos longos e peça ao vendedor para ligar proativamente.

    2. **Aumentar ticket** — se o ticket médio é R$ 800, como chegar a R$ 1.000? Sugestão de produtos
       complementares (cross-sell), venda de kits, ou oferta de produtos de maior valor agregado.

    3. **Recuperar inativos** — clientes que compravam e pararam são mais fáceis de recuperar do que
       conquistar novos. O Pivot mostra exatamente quem parou e quando.

    ---

    ### 🔧 Sobre os Pedidos do Cliente

    **Kits de produtos:** O sistema (Cronos) possui a tabela `ProdutoComposto` que permite cadastrar
    kits. Consulte o suporte do Cronos para ativar essa funcionalidade e definir os produtos que
    compõem cada kit com seus preços.

    **Romaneio em ordem alfabética:** É um ajuste no relatório de separação do sistema.
    Solicite ao suporte técnico do Cronos a customização do relatório de romaneio
    para ordenar por nome do cliente (campo `NomeCliFor`).
    """)


# ============================================================================
# RODAPÉ
# ============================================================================
st.markdown("---")
_, _ts_footer = _load_mov()
_cache_info = f"Cache de {_ts_footer}" if _ts_footer else "⚠️ Dados ao vivo (ETL pendente)"
st.caption(
    f"GM Limpeza — Dashboard de Vendas v1.0 · "
    f"Dados: {dt_inicio.strftime('%d/%m/%Y')} a {dt_fim.strftime('%d/%m/%Y')} · "
    f"{_cache_info} · "
    f"Desenvolvido por Victor Monteiro"
)