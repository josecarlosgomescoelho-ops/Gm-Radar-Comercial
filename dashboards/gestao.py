"""
GM Limpeza — Painel Estratégico de Rentabilidade (Gestão)
Dashboard executivo com autenticação restrita (Supervisores, Gestão e Dev).
Versão Streamlit baseada no design do painel_estrategico_de_rentabilidade_gm_limpeza.html
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import date, datetime, timedelta
from pathlib import Path
import calendar

# ============================================================================
# CONFIGURAÇÃO
# ============================================================================
st.set_page_config(
    page_title="GM Limpeza — Painel Estratégico",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Auth gate — deve vir logo após set_page_config
from auth import check_session, render_logout_sidebar

_auth_user = check_session()

# Validar role (apenas supervisor, gestao, dev)
ROLES_PERMITIDOS = {"supervisor", "gestao", "dev"}
if _auth_user["role"] not in ROLES_PERMITIDOS:
    st.error("🚫 Acesso negado. Este painel é restrito a Supervisores, Gestão e Desenvolvedores.")
    st.stop()


LOGO_PATH = Path(__file__).parent / "assets" / "logo.jpg"
CACHE_DIR = Path(__file__).parent.parent / "cache"
HOJE = date.today()


# ============================================================================
# CSS DARK MODE - IDENTIDADE VISUAL DO PAINEL HTML
# ============================================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

    * {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }

    /* Esconder menu */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Background dark */
    .stApp {
        background: linear-gradient(to bottom right, #020617, #090d1f, #0d1527);
    }

    /* Sidebar dark blue */
    section[data-testid="stSidebar"] > div {
        background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
    }
    [data-testid="stSidebar"] .stMarkdown p,
    [data-testid="stSidebar"] .stMarkdown h3,
    [data-testid="stSidebar"] .stCaption,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] .stSelectbox span,
    [data-testid="stSidebar"] .stDateInput span {
        color: #e2e8f0 !important;
    }

    /* KPI Cards Dark Mode */
    .kpi-card {
        background: linear-gradient(135deg, #121a30 0%, #1a1b4b 100%);
        border: 1px solid rgba(99, 102, 241, 0.2);
        border-left: 4px solid #6366f1;
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
        position: relative;
        overflow: hidden;
        transition: all 0.3s;
    }
    .kpi-card:hover {
        border-color: rgba(99, 102, 241, 0.5);
        box-shadow: 0 0 30px rgba(99, 102, 241, 0.3);
        transform: translateY(-2px);
    }
    .kpi-card.green {
        border-left-color: #10b981;
        border-color: rgba(16, 185, 129, 0.2);
    }
    .kpi-card.green:hover {
        border-color: rgba(16, 185, 129, 0.5);
        box-shadow: 0 0 30px rgba(16, 185, 129, 0.3);
    }
    .kpi-card.cyan {
        border-left-color: #06b6d4;
        border-color: rgba(6, 182, 212, 0.2);
    }
    .kpi-card.cyan:hover {
        border-color: rgba(6, 182, 212, 0.5);
        box-shadow: 0 0 30px rgba(6, 182, 212, 0.3);
    }
    .kpi-card.amber {
        border-left-color: #f59e0b;
        border-color: rgba(245, 158, 11, 0.2);
    }
    .kpi-card.amber:hover {
        border-color: rgba(245, 158, 11, 0.5);
        box-shadow: 0 0 30px rgba(245, 158, 11, 0.3);
    }

    .kpi-label {
        color: #94a3b8;
        font-size: 0.65rem;
        text-transform: uppercase;
        letter-spacing: 1.2px;
        font-weight: 800;
        margin-bottom: 6px;
    }
    .kpi-value {
        color: #ffffff;
        font-size: 1.5rem;
        font-weight: 900;
        line-height: 1.2;
    }
    .kpi-value.green { color: #10b981; }
    .kpi-value.cyan { color: #06b6d4; }
    .kpi-value.amber { color: #f59e0b; }
    .kpi-value.purple { color: #6366f1; }

    .kpi-sub {
        font-size: 0.7rem;
        color: #64748b;
        margin-top: 6px;
        font-weight: 600;
    }
    .kpi-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 6px;
        font-size: 0.65rem;
        font-weight: 700;
        margin-top: 4px;
    }
    .badge-green {
        background: rgba(16, 185, 129, 0.15);
        color: #10b981;
        border: 1px solid rgba(16, 185, 129, 0.3);
    }

    /* Section Cards */
    .section-card {
        background: #121a30;
        border: 1px solid rgba(148, 163, 184, 0.1);
        border-radius: 20px;
        padding: 24px;
        box-shadow: 0 2px 15px rgba(0, 0, 0, 0.3);
        margin-bottom: 16px;
    }

    .section-title {
        color: #ffffff;
        font-size: 0.85rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 16px;
        display: flex;
        align-items: center;
        gap: 8px;
    }

    /* Team Cards */
    .team-card {
        background: linear-gradient(135deg, #121a30 0%, #1a1b4b 100%);
        border: 2px solid rgba(99, 102, 241, 0.3);
        border-left: 4px solid #6366f1;
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
    }
    .team-card.cyan {
        border-color: rgba(6, 182, 212, 0.3);
        border-left-color: #06b6d4;
        background: linear-gradient(135deg, #121a30 0%, #042840 100%);
    }

    .team-name {
        color: #ffffff;
        font-size: 1rem;
        font-weight: 700;
        margin-bottom: 12px;
    }

    .team-stat {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 0;
        border-bottom: 1px solid rgba(148, 163, 184, 0.1);
    }
    .team-stat:last-child {
        border-bottom: none;
    }
    .stat-label {
        color: #94a3b8;
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
    }
    .stat-value {
        color: #ffffff;
        font-size: 0.9rem;
        font-weight: 700;
    }

    /* Header */
    .header-container {
        background: linear-gradient(135deg, #0c1224 0%, #1e293b 100%);
        border: 1px solid rgba(148, 163, 184, 0.2);
        border-radius: 16px;
        padding: 16px 24px;
        margin-bottom: 24px;
        box-shadow: 0 2px 12px rgba(0, 0, 0, 0.3);
    }

    .header-title {
        color: #ffffff;
        font-size: 1.4rem;
        font-weight: 900;
        letter-spacing: 0.5px;
    }

    .header-subtitle {
        color: #94a3b8;
        font-size: 0.75rem;
        margin-top: 4px;
    }

    .header-badge {
        background: rgba(16, 185, 129, 0.15);
        color: #10b981;
        border: 1px solid rgba(16, 185, 129, 0.3);
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 0.7rem;
        font-weight: 700;
        display: inline-flex;
        align-items: center;
        gap: 6px;
    }

    .header-badge::before {
        content: '';
        width: 6px;
        height: 6px;
        background: #10b981;
        border-radius: 50%;
        animation: pulse 2s infinite;
    }

    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }

    /* Scrollbar */
    ::-webkit-scrollbar {
        width: 6px;
        height: 6px;
    }
    ::-webkit-scrollbar-track {
        background: #020617;
    }
    ::-webkit-scrollbar-thumb {
        background: #1e293b;
        border-radius: 4px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: #334155;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================================
# FUNÇÕES DE CACHE E DADOS
# ============================================================================
@st.cache_data(ttl=1800)
def _load_movimentos():
    p = CACHE_DIR / "movimentos.parquet"
    if not p.exists():
        return None, None
    df = pd.read_parquet(p)
    df["DataFaturamento"] = pd.to_datetime(df["DataFaturamento"])
    ts = datetime.fromtimestamp(p.stat().st_mtime).strftime("%d/%m/%Y %H:%M")
    return df, ts


@st.cache_data(ttl=1800)
def _load_itens():
    p = CACHE_DIR / "itens.parquet"
    if not p.exists():
        return None
    df = pd.read_parquet(p)
    df["DataFaturamento"] = pd.to_datetime(df["DataFaturamento"])
    return df


def fmt_brl(v):
    """Formata valor em Reais."""
    if pd.isna(v) or v == 0:
        return "R$ 0"
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_pct(v):
    """Formata percentual."""
    if pd.isna(v):
        return "0%"
    return f"{v:.2f}%".replace(".", ",")


def kpi_card(label, value, sub="", accent="", badge=""):
    """Retorna HTML de um KPI card dark mode."""
    value_class = f"kpi-value {accent}" if accent else "kpi-value"
    card_class = f"kpi-card {accent}" if accent else "kpi-card"
    sub_html = f'<div class="kpi-sub">{sub}</div>' if sub else ""
    badge_html = f'<div class="kpi-badge badge-{accent}">{badge}</div>' if badge else ""

    return f"""
    <div class="{card_class}">
        <div class="kpi-label">{label}</div>
        <div class="{value_class}">{value}</div>
        {sub_html}
        {badge_html}
    </div>
    """


# ============================================================================
# SIDEBAR
# ============================================================================
with st.sidebar:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=120)
    st.markdown("### 📊 Painel Estratégico")
    st.markdown("---")

    # Filtro de período
    _fim_mes = HOJE.replace(day=calendar.monthrange(HOJE.year, HOJE.month)[1])
    col1, col2 = st.columns(2)
    with col1:
        dt_inicio = st.date_input("📅 Início", value=HOJE.replace(day=1), format="DD/MM/YYYY")
    with col2:
        dt_fim = st.date_input("📅 Fim", value=HOJE, format="DD/MM/YYYY")

    st.markdown("---")
    st.caption(f"📅 {dt_inicio.strftime('%d/%m/%Y')} a {dt_fim.strftime('%d/%m/%Y')}")

    render_logout_sidebar(_auth_user)


# ============================================================================
# CARREGAR DADOS
# ============================================================================
df_mov, _cache_ts = _load_movimentos()
df_itens = _load_itens()

if df_mov is None or df_itens is None:
    st.error("❌ Cache indisponível — execute o ETL para gerar os arquivos Parquet.")
    st.code("python scripts/etl_cache.py")
    st.stop()

# Filtrar período
d0 = pd.to_datetime(dt_inicio)
d1 = pd.to_datetime(dt_fim)

df_mov = df_mov[(df_mov["DataFaturamento"] >= d0) & (df_mov["DataFaturamento"] <= d1)]
df_itens = df_itens[(df_itens["DataFaturamento"] >= d0) & (df_itens["DataFaturamento"] <= d1)]

if df_mov.empty:
    st.warning("Nenhum dado encontrado para o período selecionado.")
    st.stop()


# ============================================================================
# CÁLCULOS DE MÉTRICAS
# ============================================================================
# Métricas globais
fat_total = df_mov["ValorLiquido"].sum()
qtd_pedidos = df_mov["IdMov"].nunique()
custo_total = df_itens["CustoItem"].sum()
margem_total = fat_total - custo_total
rent_pct = (margem_total / fat_total * 100) if fat_total > 0 else 0
ticket_medio = fat_total / qtd_pedidos if qtd_pedidos > 0 else 0
desc_medio = df_mov["PercDesconto"].mean()

# Métricas por supervisor
df_mov["Supervisor"] = df_mov["Supervisor"].fillna("Outros")
supervisores = df_mov["Supervisor"].unique()

sup_metricas = {}
for sup in supervisores:
    mov_sup = df_mov[df_mov["Supervisor"] == sup]
    # CORREÇÃO: Filtrar itens pelos IdMov do supervisor (não por CodVendedor)
    # Isso garante que pegamos apenas os itens dos pedidos deste supervisor no período
    itens_sup = df_itens[df_itens["IdMov"].isin(mov_sup["IdMov"].unique())]

    fat = mov_sup["ValorLiquido"].sum()
    ped = mov_sup["IdMov"].nunique()
    custo = itens_sup["CustoItem"].sum()
    margem = fat - custo
    rent = (margem / fat * 100) if fat > 0 else 0
    ticket = fat / ped if ped > 0 else 0

    sup_metricas[sup] = {
        "faturamento": fat,
        "pedidos": ped,
        "margem": margem,
        "rent_pct": rent,
        "ticket": ticket,
        "share_ped": (ped / qtd_pedidos * 100) if qtd_pedidos > 0 else 0,
    }


# ============================================================================
# HEADER
# ============================================================================
st.markdown(f"""
<div class="header-container">
    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px;">
        <div>
            <div class="header-title">
                GM LIMPEZA — PAINEL ESTRATÉGICO
            </div>
            <div class="header-subtitle">
                📄 Relatório: {dt_inicio.strftime('%d/%m/%Y')} a {dt_fim.strftime('%d/%m/%Y')}
            </div>
        </div>
        <div class="header-badge">
            {fmt_pct(rent_pct)} Rentabilidade
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# Quick KPI global
kc1, kc2, kc3 = st.columns(3)
with kc1:
    st.markdown(f"""
    <div style="background: #121a30; border: 1px solid rgba(148, 163, 184, 0.1); border-radius: 12px; padding: 12px; text-align: center;">
        <span style="color: #94a3b8; font-size: 0.65rem; text-transform: uppercase; font-weight: 700;">Faturamento Atual</span><br>
        <span style="color: #ffffff; font-size: 1rem; font-weight: 900;">{fmt_brl(fat_total)}</span>
    </div>
    """, unsafe_allow_html=True)

with kc2:
    st.markdown(f"""
    <div style="background: #121a30; border: 1px solid rgba(148, 163, 184, 0.1); border-radius: 12px; padding: 12px; text-align: center;">
        <span style="color: #94a3b8; font-size: 0.65rem; text-transform: uppercase; font-weight: 700;">Resultado Caixa</span><br>
        <span style="color: #10b981; font-size: 1rem; font-weight: 900;">{fmt_brl(margem_total)}</span>
    </div>
    """, unsafe_allow_html=True)

with kc3:
    st.markdown(f"""
    <div style="background: #121a30; border: 1px solid rgba(148, 163, 184, 0.1); border-radius: 12px; padding: 12px; text-align: center;">
        <span style="color: #94a3b8; font-size: 0.65rem; text-transform: uppercase; font-weight: 700;">Volume Geral</span><br>
        <span style="color: #06b6d4; font-size: 1rem; font-weight: 900;">{qtd_pedidos} Pedidos</span>
    </div>
    """, unsafe_allow_html=True)

st.markdown("")


# ============================================================================
# CARDS GLOBAIS DE DESEMPENHO
# ============================================================================
st.markdown('<div class="section-title">📊 Indicadores Globais de Desempenho</div>', unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(
        kpi_card("Preço Total Líquido", fmt_brl(fat_total),
                f"Ticket Médio: {fmt_brl(ticket_medio)}", "purple"),
        unsafe_allow_html=True
    )

with c2:
    st.markdown(
        kpi_card("Rentabilidade de Caixa", fmt_brl(margem_total),
                f"Margem: {fmt_pct(rent_pct)}", "green"),
        unsafe_allow_html=True
    )

with c3:
    st.markdown(
        kpi_card("Volume de Pedidos", f"{qtd_pedidos} Pedidos",
                "Vendas Concluídas no Período", "cyan"),
        unsafe_allow_html=True
    )

with c4:
    st.markdown(
        kpi_card("Desconto Médio Geral", fmt_pct(desc_medio),
                "Limite de Segurança: < 6,00%", "amber"),
        unsafe_allow_html=True
    )

st.markdown("")


# ============================================================================
# GRÁFICOS DE DISTRIBUIÇÃO
# ============================================================================
st.markdown('<div class="section-title">📊 Distribuição Comercial</div>', unsafe_allow_html=True)

gc1, gc2 = st.columns([1, 2])

# Gráfico de Pizza - Share de Pedidos
with gc1:
    labels = list(sup_metricas.keys())
    values = [sup_metricas[s]["pedidos"] for s in labels]
    colors = ["#6366f1", "#06b6d4", "#10b981", "#f59e0b"][:len(labels)]

    fig_pizza = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.4,
        marker=dict(colors=colors),
        textinfo='percent+label',
        textfont=dict(size=12, color='white'),
    )])

    fig_pizza.update_layout(
        title=dict(text="Share de Pedidos (%)", font=dict(size=14, color='#94a3b8')),
        height=300,
        margin=dict(t=40, b=20, l=20, r=20),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='white'),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.2,
            xanchor="center",
            x=0.5,
            font=dict(size=10)
        )
    )

    st.plotly_chart(fig_pizza, use_container_width=True)

# Gráfico de Barras - Rentabilidade Comparativa
with gc2:
    labels = list(sup_metricas.keys())
    rent_values = [sup_metricas[s]["rent_pct"] for s in labels]

    fig_bars = go.Figure(data=[go.Bar(
        x=labels,
        y=rent_values,
        marker=dict(color=colors[:len(labels)]),
        text=[f"{v:.2f}%" for v in rent_values],
        textposition='outside',
        textfont=dict(size=12, color='white'),
    )])

    fig_bars.add_hline(
        y=26.0,
        line_dash="dash",
        line_color="#f59e0b",
        annotation_text="Meta: 26,00%",
        annotation_position="right",
        annotation=dict(font=dict(size=10, color='#f59e0b'))
    )

    fig_bars.update_layout(
        title=dict(text="Rentabilidade (%) por Equipe", font=dict(size=14, color='#94a3b8')),
        height=300,
        margin=dict(t=40, b=40, l=40, r=40),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='white'),
        yaxis=dict(
            title="% Rentabilidade",
            gridcolor='rgba(148, 163, 184, 0.1)',
            title_font=dict(size=11, color='#94a3b8')
        ),
        xaxis=dict(title_font=dict(size=11, color='#94a3b8'))
    )

    st.plotly_chart(fig_bars, use_container_width=True)

st.markdown("")


# ============================================================================
# ANÁLISE POR EQUIPE
# ============================================================================
st.markdown('<div class="section-title">👥 Análise Tática por Equipe</div>', unsafe_allow_html=True)

team_cols = st.columns(len(supervisores))
for i, sup in enumerate(supervisores):
    with team_cols[i]:
        m = sup_metricas[sup]
        card_class = "team-card cyan" if i % 2 else "team-card"

        team_html = f"""<div class="{card_class}">
<div class="team-name">Equipe {sup}</div>
<div class="team-stat">
<span class="stat-label">Preço Líquido</span>
<span class="stat-value">{fmt_brl(m['faturamento'])}</span>
</div>
<div class="team-stat">
<span class="stat-label">Rentabilidade R$</span>
<span class="stat-value" style="color: #10b981;">{fmt_brl(m['margem'])}</span>
</div>
<div class="team-stat">
<span class="stat-label">Rentabilidade %</span>
<span class="stat-value" style="color: #10b981;">{fmt_pct(m['rent_pct'])}</span>
</div>
<div class="team-stat">
<span class="stat-label">Ticket Médio</span>
<span class="stat-value">{fmt_brl(m['ticket'])}</span>
</div>
<div class="team-stat">
<span class="stat-label">Volume Pedidos</span>
<span class="stat-value">{m['pedidos']} ({fmt_pct(m['share_ped'])})</span>
</div>
</div>"""

        st.markdown(team_html, unsafe_allow_html=True)


# ============================================================================
# RANKING DE VENDEDORES
# ============================================================================
st.markdown("")
st.markdown('<div class="section-title">🏆 Ranking Individual de Vendedoras</div>', unsafe_allow_html=True)

# Calcular rentabilidade por vendedor
df_vendedor = df_mov.groupby(["CodVendedor", "Vendedor", "Supervisor"]).agg(
    Pedidos=("IdMov", "nunique"),
    Faturamento=("ValorLiquido", "sum"),
    DescMedio=("PercDesconto", "mean"),
).reset_index()

df_vendedor_custo = df_itens.groupby("CodVendedor").agg(
    CustoTotal=("CustoItem", "sum")
).reset_index()

df_vendedor = df_vendedor.merge(df_vendedor_custo, on="CodVendedor", how="left")
df_vendedor["CustoTotal"] = df_vendedor["CustoTotal"].fillna(0)
df_vendedor["Margem"] = df_vendedor["Faturamento"] - df_vendedor["CustoTotal"]
df_vendedor["RentPerc"] = np.where(
    df_vendedor["Faturamento"] > 0,
    df_vendedor["Margem"] / df_vendedor["Faturamento"] * 100,
    0
)
df_vendedor["TicketMedio"] = np.where(
    df_vendedor["Pedidos"] > 0,
    df_vendedor["Faturamento"] / df_vendedor["Pedidos"],
    0
)

df_vendedor = df_vendedor.sort_values("Faturamento", ascending=False)

# Exibir tabela com estilo
st.dataframe(
    df_vendedor[["Vendedor", "Supervisor", "Pedidos", "Faturamento", "Margem", "RentPerc", "DescMedio", "TicketMedio"]]
    .rename(columns={
        "Faturamento": "Faturamento (R$)",
        "Margem": "Margem (R$)",
        "RentPerc": "Rent. %",
        "DescMedio": "Desc. Médio %",
        "TicketMedio": "Ticket Médio (R$)",
    })
    .style.format({
        "Faturamento (R$)": "R$ {:,.2f}",
        "Margem (R$)": "R$ {:,.2f}",
        "Rent. %": "{:.2f}%",
        "Desc. Médio %": "{:.2f}%",
        "Ticket Médio (R$)": "R$ {:,.2f}",
    }),
    hide_index=True,
    use_container_width=True,
    height=400,
)


# ============================================================================
# RODAPÉ
# ============================================================================
st.markdown("---")
st.caption(
    f"GM Limpeza — Painel Estratégico de Rentabilidade v1.0 · "
    f"{dt_inicio.strftime('%d/%m/%Y')} a {dt_fim.strftime('%d/%m/%Y')} · "
    f"Cache de {_cache_ts} · "
    f"Desenvolvido por Victor Monteiro"
)
