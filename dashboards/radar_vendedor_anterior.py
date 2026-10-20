"""
GM Limpeza — Radar de Risco do Vendedor v2.1
Multi-vendedor, filtro por supervisor, cards clicáveis, autenticação por sessão.
"""

import json
import os
import re
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import pymssql
import numpy as np
from decimal import Decimal
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

LOGO_PATH  = Path(__file__).parent / "assets" / "logo.jpg"
CACHE_DIR  = Path(__file__).parent.parent / "cache"
PREFS_FILE = CACHE_DIR / "user_prefs.json"
HOJE = pd.Timestamp.now(tz="America/Sao_Paulo").date()

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
    """Retorna número para wa.me (55 + DDD + número, só dígitos)."""
    if not celular or str(celular).strip() in ("", "nan", "None"):
        return ""
    num = re.sub(r"\D", "", str(celular))
    if len(num) < 10:
        return ""
    return f"55{num}" if not num.startswith("55") else num


def _fmt_phone_display(celular) -> str:
    """Formata número para exibição: (41) 99999-8888."""
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

# CSS embutido nos cards de cliente (usado nos iframes de components.html)
CARD_CSS = """
<script>
  function _reportHeight() {
    var h = document.documentElement.scrollHeight;
    window.parent.postMessage({ type: 'streamlit:setFrameHeight', height: h + 4 }, '*');
  }
  window.addEventListener('load', _reportHeight);
  window.addEventListener('resize', _reportHeight);
</script>
<style>
  body { margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
  .cliente-card {
    background: #FFFFFF; border-radius: 10px; padding: 14px 18px;
    box-shadow: 0 1px 6px rgba(0,0,0,0.08); border-left: 5px solid #95A5A6;
  }
  .risco-critico  { border-left-color: #E74C3C; background: #FFF5F5; }
  .risco-atencao  { border-left-color: #F39C12; background: #FFFDF5; }
  .risco-ativo    { border-left-color: #27AE60; background: #FFFFFF; }
  .risco-perdido  { border-left-color: #8E44AD; background: #FBF5FF; }
  .risco-novo     { border-left-color: #2E6BA6; background: #F0F7FF; }
  .cliente-nome   { font-size: 0.98rem; font-weight: 700; color: #1B3A5C; }
  .cliente-badge  { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 0.7rem; font-weight: 700; margin-left: 8px; }
  .badge-critico  { background: #E74C3C; color: white; }
  .badge-atencao  { background: #F39C12; color: white; }
  .badge-ativo    { background: #27AE60; color: white; }
  .badge-perdido  { background: #8E44AD; color: white; }
  .badge-novo     { background: #2E6BA6; color: white; }
  .cliente-meta   { font-size: 0.8rem; color: #5D6D7E; margin-top: 6px; line-height: 1.7; word-wrap: break-word; overflow-wrap: break-word; }
  .cliente-alerta { font-size: 0.82rem; font-weight: 600; margin-top: 4px; }
  .cliente-acao   { font-size: 0.82rem; color: #2E6BA6; font-weight: 600; margin-top: 4px; }
  .pivot-cell     { text-align: right; padding: 3px 8px; font-size: 0.8rem; }
  .pivot-zero     { color: #E74C3C; font-weight: 700; }
  .pivot-value    { color: #1B3A5C; }
  table           { width: 100%; margin-top: 8px; border-collapse: collapse; }
  th              { text-align: right; padding: 3px 8px; font-size: 0.7rem; color: #95A5A6; }
</style>
"""

# ============================================================================
# PÁGINA
# ============================================================================
st.set_page_config(
    page_title="GM Limpeza — Radar de Risco",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Auth gate — deve vir logo após set_page_config
from auth import check_session, render_logout_sidebar, salvar_filtros_usuario
_auth_user = check_session()

st.markdown("""
<style>
    /* Esconder menu */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Sidebar */
    section[data-testid="stSidebar"] > div {
        background: linear-gradient(180deg, #1B3A5C 0%, #2E6BA6 100%);
    }
    [data-testid="stSidebar"] .stMarkdown p,
    [data-testid="stSidebar"] .stMarkdown h3,
    [data-testid="stSidebar"] .stCaption,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] .stMultiSelect span {
        color: #E8F4FD !important;
    }

    /* Cards de status clicáveis — estilos via posição de coluna */
    .element-container:has(#status-cards-marker) + div button,
    .element-container:has(#status-cards-marker) ~ div [data-testid="stHorizontalBlock"] button {
        min-height: 88px !important;
        border-radius: 12px !important;
        white-space: pre-line !important;
        font-size: 0.8rem !important;
        text-align: center !important;
        width: 100% !important;
        transition: all 0.15s !important;
        line-height: 1.5 !important;
    }
    /* Crítico — coluna 1 */
    [data-testid="stHorizontalBlock"] [data-testid="stColumn"]:nth-child(1) button[kind="secondary"] {
        background: #FDEDEC !important; color: #E74C3C !important; border-left: 4px solid #E74C3C !important;
    }
    [data-testid="stHorizontalBlock"] [data-testid="stColumn"]:nth-child(1) button[kind="primary"] {
        background: #E74C3C !important; color: white !important; border-left: 4px solid #C0392B !important;
    }
    /* Atenção — coluna 2 */
    [data-testid="stHorizontalBlock"] [data-testid="stColumn"]:nth-child(2) button[kind="secondary"] {
        background: #FEF9E7 !important; color: #F39C12 !important; border-left: 4px solid #F39C12 !important;
    }
    [data-testid="stHorizontalBlock"] [data-testid="stColumn"]:nth-child(2) button[kind="primary"] {
        background: #F39C12 !important; color: white !important; border-left: 4px solid #D68910 !important;
    }
    /* Ativo — coluna 3 */
    [data-testid="stHorizontalBlock"] [data-testid="stColumn"]:nth-child(3) button[kind="secondary"] {
        background: #D5F5E3 !important; color: #27AE60 !important; border-left: 4px solid #27AE60 !important;
    }
    [data-testid="stHorizontalBlock"] [data-testid="stColumn"]:nth-child(3) button[kind="primary"] {
        background: #27AE60 !important; color: white !important; border-left: 4px solid #1E8449 !important;
    }
    /* Perdido — coluna 4 */
    [data-testid="stHorizontalBlock"] [data-testid="stColumn"]:nth-child(4) button[kind="secondary"] {
        background: #F4ECF7 !important; color: #8E44AD !important; border-left: 4px solid #8E44AD !important;
    }
    [data-testid="stHorizontalBlock"] [data-testid="stColumn"]:nth-child(4) button[kind="primary"] {
        background: #8E44AD !important; color: white !important; border-left: 4px solid #6C3483 !important;
    }
    /* Novo — coluna 5 */
    [data-testid="stHorizontalBlock"] [data-testid="stColumn"]:nth-child(5) button[kind="secondary"] {
        background: #EBF5FB !important; color: #2E6BA6 !important; border-left: 4px solid #2E6BA6 !important;
    }
    [data-testid="stHorizontalBlock"] [data-testid="stColumn"]:nth-child(5) button[kind="primary"] {
        background: #2E6BA6 !important; color: white !important; border-left: 4px solid #1B3A5C !important;
    }

    /* Compactar espaço entre iframes dos cards de cliente */
    [data-testid="stCustomComponentV1"] iframe {
        display: block;
        margin-bottom: -10px !important;
    }

    /* Info box */
    .info-box {
        background: #F0F5FA; border-radius: 8px; padding: 14px 18px;
        font-size: 0.82rem; color: #5D6D7E; line-height: 1.6; margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================================
# CONEXÃO
# ============================================================================
def get_conn():
    """Conexão com timeout de 30s para evitar travar o servidor."""
    return pymssql.connect(**DB_CONFIG, login_timeout=15, timeout=30, charset="UTF-8")

def query_segura(sql, params=None):
    for tentativa in range(2):
        try:
            conn = get_conn()
            df = pd.read_sql(sql, conn, params=params)
            conn.close()
            return df
        except Exception as e:
            if tentativa == 1:
                raise e


# ---- Loaders de cache (Parquet) --------------------------------------------

VERSAO_FINANCEIRO_CRONOS = 1


def _versao_cache_financeiro():
    p = CACHE_DIR / "rentabilidade_cronos.parquet"
    return (p.stat().st_mtime_ns, p.stat().st_size)


@st.cache_data(ttl=1800)
def _load_financeiro_cronos(versao):
    """Recusa esquemas antigos e invalida o cache ao trocar o arquivo."""
    df = pd.read_parquet(CACHE_DIR / "rentabilidade_cronos.parquet")
    meta = {"VersaoFinanceiroCronos", "PeriodoInicio", "PeriodoFimInclusivo",
            "DataReferencia", "AtualizadoEmUTC"}
    dados = {"CodVendedor", "NomeVendedor", "NomeFilial", "IdImagem", "Qtd",
             "ReceitaUnidades", "CustoUnidades", "LucroUnidades",
             "PercRetabilidadeItem", "LinhaFinanceira"}
    if df.empty or not (meta | dados).issubset(df.columns):
        raise ValueError("Cache financeiro ausente ou antigo; execute o ETL atualizado.")
    for coluna in meta:
        if df[coluna].isna().any() or df[coluna].nunique(dropna=False) != 1:
            raise ValueError("Metadados financeiros inconsistentes.")
    if df["VersaoFinanceiroCronos"].ne(VERSAO_FINANCEIRO_CRONOS).any():
        raise ValueError("Versao do financeiro desatualizada.")
    if pd.Timestamp(df["AtualizadoEmUTC"].iloc[0]).tzinfo is None:
        raise ValueError("Horario de atualizacao financeira sem fuso.")
    inicio = pd.Timestamp(df["PeriodoInicio"].iloc[0])
    fim = pd.Timestamp(df["PeriodoFimInclusivo"].iloc[0])
    referencia = pd.Timestamp(df["DataReferencia"].iloc[0])
    if (inicio != referencia.replace(day=1) or fim != referencia
            or referencia != referencia.normalize() or referencia.date() > HOJE
            or (referencia.year, referencia.month) != (HOJE.year, HOJE.month)):
        raise ValueError("Financeiro de outro periodo; atualize o ETL.")
    if not df["LinhaFinanceira"].isin([True, False]).all():
        raise ValueError("Marcador de linhas financeiras invalido.")
    df["LinhaFinanceira"] = df["LinhaFinanceira"].astype(bool)
    if not df["LinhaFinanceira"].all() and (len(df) != 1 or df["LinhaFinanceira"].any()):
        raise ValueError("Registro financeiro vazio misturado com vendas.")
    for coluna in ["ReceitaUnidades", "CustoUnidades", "LucroUnidades"]:
        if df[coluna].isna().any():
            raise ValueError("Valores financeiros incompletos.")
        df[coluna] = pd.to_numeric(df[coluna], errors="raise").astype("Int64")
        if not df["LinhaFinanceira"].any() and df[coluna].ne(0).any():
            raise ValueError("Periodo sem vendas com valores financeiros.")
    df["Qtd"] = pd.to_numeric(df["Qtd"], errors="raise").astype("Int64")
    df["PercRetabilidadeItem"] = pd.to_numeric(
        df["PercRetabilidadeItem"], errors="raise"
    ).astype("Float64")
    sem_margem = df["PercRetabilidadeItem"].isna()
    if (sem_margem & df["ReceitaUnidades"].ne(0)).any():
        raise ValueError("Margem ausente para receita diferente de zero.")
    if not np.isfinite(df.loc[~sem_margem, "PercRetabilidadeItem"].astype(float)).all():
        raise ValueError("Margem financeira invalida.")
    df["CodVendedor"] = df["CodVendedor"].astype("string").str.strip()
    if _versao_cache_financeiro() != versao:
        raise ValueError("Financeiro em atualizacao; recarregue a pagina.")
    return df


def _resumo_financeiro_cronos(df, vendedores, visao_global=False):
    """Agrega MONEY sem perder casas decimais; respeita a selecao autorizada."""
    linhas = df.loc[df["LinhaFinanceira"]].copy()
    codigos = {str(c).strip() for c in vendedores}
    if not visao_global:
        linhas = linhas.loc[linhas["CodVendedor"].isin(codigos)].copy()
    receita = Decimal(sum(int(v) for v in linhas["ReceitaUnidades"])) / 10000
    custo = Decimal(sum(int(v) for v in linhas["CustoUnidades"])) / 10000
    lucro = Decimal(sum(int(v) for v in linhas["LucroUnidades"])) / 10000
    qtd = linhas["Qtd"].sum(min_count=1) if not linhas.empty else 0
    qtd = None if pd.isna(qtd) else int(qtd)
    margem = (receita - custo) / receita * 100 if receita != 0 else None
    # A linha individual usa o percentual da SQL, inclusive sua aritmetica MONEY.
    # O consolidado usa os totais, como o rodape do relatorio, sem media de margens.
    if not visao_global and len(codigos) == 1 and len(linhas) == 1:
        percentual = linhas["PercRetabilidadeItem"].iloc[0]
        margem = None if pd.isna(percentual) else Decimal(str(percentual))
    return {"receita": receita, "custo": custo, "lucro": lucro,
            "qtd": qtd, "margem": margem, "linhas": linhas}


def _exportar_financeiro_cronos(linhas):
    df = linhas[["CodVendedor", "NomeVendedor", "NomeFilial", "IdImagem", "Qtd"]].copy()
    for origem, destino in [("ReceitaUnidades", "PrecoLiquido"),
                            ("CustoUnidades", "CustoLiqU"),
                            ("LucroUnidades", "ValorRentabilidadeItem")]:
        df[destino] = [format(Decimal(int(v)) / 10000, ".4f") for v in linhas[origem]]
    df["PercRetabilidadeItem"] = linhas["PercRetabilidadeItem"]
    return df


def _vendedores_autorizados(df, usuario):
    """Aplica o acesso antes dos widgets e tambem antes de carregar a carteira."""
    role = str(usuario.get("role", "")).strip().lower()
    cod = str(usuario.get("cod", "")).strip()
    if role in {"dev", "gestao"}:
        return df.copy()
    if role in {"supervisor", "supervisao"}:
        return df.loc[df["CodSupervisor"].eq(cod) | df["CodVendedor"].eq(cod)].copy()
    return df.loc[df["CodVendedor"].eq(cod)].copy()
def _versao_cache_carteira():
    paths = [CACHE_DIR / "carteira_clientes.parquet", CACHE_DIR / "carteira_historico.parquet"]
    return tuple((p.stat().st_mtime_ns, p.stat().st_size) for p in paths)


@st.cache_data(ttl=1800)
def _load_carteira_abc(versoes):
    """Le os dois caches juntos; a versao dos arquivos invalida o cache da tela."""
    df = pd.read_parquet(CACHE_DIR / "carteira_clientes.parquet")
    hist = pd.read_parquet(CACHE_DIR / "carteira_historico.parquet")
    meta = {"SnapshotCarteira", "DataReferencia", "PeriodoInicio", "PeriodoFimExclusivo"}
    cadastro = {
        "IdEmpresa", "CodCliFor", "Cliente", "Telefone", "Celular",
        "CodVendedorCarteira", "VendedorCarteira", "CarteiraVAtiva",
        "TotalPeriodo", "MediaMensal", "QuantidadeMovimentos",
        "CurvaABC", "PosicaoCurva", "QtdClientesCurva",
    }
    movimento = {"IdEmpresa", "CodCliFor", "IdMov", "DtMov", "DataFaturamento", "ValorLiquido"}
    if not (meta | cadastro).issubset(df.columns) or not (meta | movimento).issubset(hist.columns):
        raise ValueError("Caches antigos: execute o ETL com o bloco de carteira atualizado.")
    if df.empty or hist.empty:
        raise ValueError("Cache de carteira vazio.")
    for coluna in meta:
        valores = [t[coluna].drop_duplicates() for t in [df, hist]]
        if any(len(v) != 1 or v.isna().any() for v in valores) or valores[0].iloc[0] != valores[1].iloc[0]:
            raise ValueError("Carteira e historico de atualizacoes diferentes; aguarde o ETL e recarregue.")
    for tabela in [df, hist]:
        if tabela[["IdEmpresa", "CodCliFor"]].isna().any().any() or tabela["IdEmpresa"].ne(1).any():
            raise ValueError("Chaves de carteira invalidas.")
        tabela["CodCliFor"] = tabela["CodCliFor"].astype("string").str.strip()
        if tabela["CodCliFor"].eq("").any():
            raise ValueError("Codigo de cliente vazio no cache.")
    if df.duplicated(["IdEmpresa", "CodCliFor"]).any() or not df["CarteiraVAtiva"].isin([0, 1]).all():
        raise ValueError("Carteira duplicada ou com elegibilidade invalida.")
    df["CarteiraVAtiva"] = df["CarteiraVAtiva"].eq(1)
    df["CodVendedorCarteira"] = df["CodVendedorCarteira"].astype("string").str.strip()
    base = df.loc[df["CarteiraVAtiva"]].copy()
    if base.empty or base["CodVendedorCarteira"].isna().any():
        raise ValueError("Carteira elegivel ausente ou sem responsavel.")
    numeros = ["TotalPeriodo", "MediaMensal", "QuantidadeMovimentos", "PosicaoCurva", "QtdClientesCurva"]
    for coluna in numeros:
        base[coluna] = pd.to_numeric(base[coluna], errors="raise")
    if not np.isfinite(base[numeros].to_numpy(dtype=float)).all():
        raise ValueError("Receita ou classificacao incompleta.")
    n = len(base)
    if (
        base["QtdClientesCurva"].ne(n).any()
        or sorted(base["PosicaoCurva"].tolist()) != list(range(1, n + 1))
        or not np.allclose(base["MediaMensal"], base["TotalPeriodo"] / 12, rtol=0, atol=0.000001)
    ):
        raise ValueError("Media ou ranking global inconsistente.")
    esperado = np.where(base["PosicaoCurva"] <= (n + 4) // 5, "A",
                        np.where(base["PosicaoCurva"] <= (n + 1) // 2, "B", "C"))
    if base["CurvaABC"].isna().any() or not base["CurvaABC"].eq(esperado).all():
        raise ValueError("Cortes da curva global inconsistentes.")
    ordem = base.sort_values(["TotalPeriodo", "CodCliFor"], ascending=[False, True], kind="stable")
    if ordem["PosicaoCurva"].tolist() != list(range(1, n + 1)):
        raise ValueError("Ordem da curva global inconsistente.")

    hist["IdMov"] = pd.to_numeric(hist["IdMov"], errors="raise").astype("Int64")
    hist["ValorLiquido"] = pd.to_numeric(hist["ValorLiquido"], errors="raise").astype(float)
    if not np.isfinite(hist["ValorLiquido"]).all():
        raise ValueError("Receita do historico incompleta.")
    for coluna in ["DataFaturamento", "DtMov"]:
        hist[coluna] = pd.to_datetime(hist[coluna], errors="raise")
    reais = hist["IdMov"].notna()
    if hist.loc[reais].duplicated(["IdEmpresa", "IdMov"]).any():
        raise ValueError("Movimentos duplicados no historico.")
    inicio = pd.Timestamp(df["PeriodoInicio"].iloc[0])
    fim = pd.Timestamp(df["PeriodoFimExclusivo"].iloc[0])
    referencia = pd.Timestamp(df["DataReferencia"].iloc[0])
    if inicio != referencia.replace(day=1) - pd.DateOffset(months=11) or fim != referencia + pd.Timedelta(days=1):
        raise ValueError("Janela do cache diferente dos 12 meses definidos.")
    for coluna in ["DtMov", "DataFaturamento"]:
        if not hist.loc[reais, coluna].between(inicio, fim, inclusive="left").all():
            raise ValueError("Historico fora da janela da carteira.")
    if hist.loc[~reais, "ValorLiquido"].ne(0).any() or hist.loc[~reais, ["DataFaturamento", "DtMov"]].notna().any().any():
        raise ValueError("Registro de cliente sem compra invalido.")
    if set(hist["CodCliFor"]) != set(base["CodCliFor"]):
        raise ValueError("Historico nao cobre a carteira completa.")
    resumo = hist.loc[reais].groupby("CodCliFor").agg(
        ReceitaHistorico=("ValorLiquido", "sum"), MovimentosHistorico=("IdMov", "count")
    )
    conferencia = base.join(resumo, on="CodCliFor")
    if (
        not np.allclose(conferencia["TotalPeriodo"], conferencia["ReceitaHistorico"].fillna(0), rtol=0, atol=0.005)
        or conferencia["QuantidadeMovimentos"].ne(conferencia["MovimentosHistorico"].fillna(0)).any()
    ):
        raise ValueError("Receita ou quantidade diverge entre carteira e historico.")
    if _versao_cache_carteira() != versoes:
        raise ValueError("Atualizacao em andamento; recarregue a pagina em alguns instantes.")
    return df, hist


def q_base_carteira(codigos_vendedores):
    df, hist = _load_carteira_abc(_versao_cache_carteira())
    referencia = pd.Timestamp(df["DataReferencia"].iloc[0]).date()
    if referencia > HOJE or (referencia.year, referencia.month) != (HOJE.year, HOJE.month):
        raise ValueError("Carteira de outro mes: atualize o ETL antes de analisar o mes atual.")
    codigos = {str(c).strip() for c in codigos_vendedores}
    carteira = df.loc[df["CarteiraVAtiva"] & df["CodVendedorCarteira"].isin(codigos)].copy()
    historico = hist.loc[hist["CodCliFor"].isin(carteira["CodCliFor"])].copy()
    return carteira, historico

@st.cache_data(ttl=1800)
def _load_radar_clientes():
    p = CACHE_DIR / "radar_clientes.parquet"
    if not p.exists():
        return None
    df = pd.read_parquet(p)
    df["DataFaturamento"] = pd.to_datetime(df["DataFaturamento"])
    return df

@st.cache_data(ttl=1800)
def _load_radar_produtos():
    p = CACHE_DIR / "radar_produtos.parquet"
    if not p.exists():
        return None
    return pd.read_parquet(p)

@st.cache_data(ttl=1800)
def _load_radar_rent_cli(versao=None):
    p = CACHE_DIR / "radar_rent_cli.parquet"
    if not p.exists():
        return None
    df = pd.read_parquet(p)
    if "VersaoRentabilidadeCronos" not in df or df["VersaoRentabilidadeCronos"].ne(1).any():
        return None
    if not df.empty:
        fim = pd.Timestamp(df["PeriodoFimExclusivo"].iloc[0]) - pd.Timedelta(days=1)
        if fim.date() > HOJE or (fim.year, fim.month) != (HOJE.year, HOJE.month):
            return None
        df["CodCliFor"] = df["CodCliFor"].astype("string").str.strip()
    return df

@st.cache_data(ttl=1800)
def _load_radar_itens():
    p = CACHE_DIR / "itens.parquet"
    if not p.exists():
        return None
    df = pd.read_parquet(p)
    df["DataFaturamento"] = pd.to_datetime(df["DataFaturamento"])
    return df

@st.cache_data(ttl=1800)
def _load_mov_cache():
    p = CACHE_DIR / "movimentos.parquet"
    if not p.exists():
        return None
    df = pd.read_parquet(p)
    df["DataFaturamento"] = pd.to_datetime(df["DataFaturamento"])
    return df

@st.cache_data(ttl=1800)
def _load_prevendas_cache():
    p = CACHE_DIR / "prevendas.parquet"
    if not p.exists():
        return None
    df = pd.read_parquet(p)
    df["DtMov"] = pd.to_datetime(df["DtMov"])
    return df

@st.cache_data(ttl=1800)
def _load_orcamentos_cache():
    p = CACHE_DIR / "orcamentos_abertos.parquet"
    if not p.exists():
        return None
    df = pd.read_parquet(p)
    df["DtMov"] = pd.to_datetime(df["DtMov"])
    return df


@st.cache_data(ttl=1800)
def _load_vendedores_cache():
    p = CACHE_DIR / "vendedores.parquet"
    if not p.exists():
        return None
    return pd.read_parquet(p)

@st.cache_data(ttl=1800)
def _load_supervisores_cache():
    p = CACHE_DIR / "supervisores.parquet"
    if not p.exists():
        return None
    return pd.read_parquet(p)

def _cache_ts():
    p = CACHE_DIR / "carteira_clientes.parquet"
    if not p.exists():
        return None
    return pd.Timestamp(p.stat().st_mtime, unit="s", tz="UTC").tz_convert(
        "America/Sao_Paulo"
    ).strftime("%d/%m/%Y %H:%M")

# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================
def fmt_moeda(v):
    if pd.isna(v):
        return "—"
    valor = f"R$ {float(v):,.2f}"
    return valor.replace(",", "X").replace(".", ",").replace("X", ".")

def fmt_brl(v):
    if pd.isna(v) or v == 0: return "—"
    if abs(v) >= 1_000_000: return f"R$ {v/1_000_000:,.2f}M"
    if abs(v) >= 1_000: return f"R$ {v/1_000:,.1f}K"
    return f"R$ {v:,.2f}"

def fmt_dias(dias):
    if dias <= 0: return "hoje"
    if dias == 1: return "1 dia"
    return f"{int(dias)} dias"


# ============================================================================
# QUERIES (cache → fallback DB)
# ============================================================================
@st.cache_data(ttl=1800)
def q_carteira_vendedores():
    df = _load_vendedores_cache()
    if df is not None:
        return df
    sql = """
    SELECT DISTINCT V.CodVendedor, V.NomeVendedor AS Vendedor,
           ISNULL(V.CodSupervisor, '') AS CodSupervisor
    FROM Vendedores V WITH (NOLOCK) WHERE V.Inativo = 'N' AND V.Tipo = 'V' ORDER BY V.NomeVendedor
    """
    return query_segura(sql)

@st.cache_data(ttl=1800)
def q_supervisores():
    df = _load_supervisores_cache()
    if df is not None:
        return df
    sql = """
    SELECT DISTINCT SUP.CodVendedor, SUP.NomeVendedor AS Supervisor
    FROM Vendedores V WITH (NOLOCK)
    INNER JOIN Vendedores SUP WITH (NOLOCK) ON V.CodSupervisor = SUP.CodVendedor
    WHERE V.Inativo = 'N' AND V.Tipo = 'V' ORDER BY SUP.NomeVendedor
    """
    return query_segura(sql)

@st.cache_data(ttl=1800)
def q_historico_cliente(cod_vendedor: str, meses_lookback: int = 12):
    df_all = _load_radar_clientes()
    if df_all is not None:
        return df_all[df_all["CodVendedor"] == cod_vendedor].drop(columns=["CodVendedor"]).copy()
    # fallback DB
    dt_inicio = (HOJE.replace(day=1) - timedelta(days=meses_lookback * 31)).replace(day=1)
    sql = """
    ;WITH Compras AS (
        SELECT M.CodCliFor, CF.NomeCliFor AS Cliente,
               CF.FoneCliFor AS Telefone, CF.CelCliFor AS Celular,
               M.DataFaturamento, M.IdMov,
               -- TotMov já embute PercDescontoItem (desconto por item, aplicado pelo Cronos antes de salvar).
               -- PercDesconto é o desconto adicional de cabeçalho — único nível não refletido em TotMov.
               -- Validado nota a nota: TotMov * (1 - PercDesconto/100) bate com o sistema ao centavo.
               CASE WHEN M.TipoMov IN ('2.8','2.3') THEN (M.TotMov * (1 - ISNULL(M.PercDesconto, 0)/100.0) * -1) + ISNULL(M.ValorFrete, 0)
                    ELSE (M.TotMov * (1 - ISNULL(M.PercDesconto, 0)/100.0)) + ISNULL(M.ValorFrete, 0) END AS ValorLiquido
        FROM Movimento M WITH (NOLOCK)
        INNER JOIN Cli_For CF WITH (NOLOCK) ON M.CodCliFor = CF.CodCliFor
        WHERE CF.CodFunc = %s AND CF.Inativo = 'N'
          AND M.DataFaturamento >= %s
          AND M.TipoMov IN ('2.4','2.1','2.8','2.3')
          AND M.Status NOT IN ('C','T')
    ),
    ClientesCarteira AS (
        SELECT CF.CodCliFor, CF.NomeCliFor AS Cliente,
               CF.FoneCliFor AS Telefone, CF.CelCliFor AS Celular
        FROM Cli_For CF WITH (NOLOCK) WHERE CF.CodFunc = %s AND CF.Inativo = 'N'
    )
    SELECT CC.CodCliFor, CC.Cliente, CC.Telefone, CC.Celular,
           C.DataFaturamento, C.IdMov, ISNULL(C.ValorLiquido, 0) AS ValorLiquido
    FROM ClientesCarteira CC
    LEFT JOIN Compras C ON CC.CodCliFor = C.CodCliFor
    """
    df = query_segura(sql, (cod_vendedor, str(dt_inicio), cod_vendedor))
    if not df.empty and "DataFaturamento" in df.columns:
        df["DataFaturamento"] = pd.to_datetime(df["DataFaturamento"])
    return df

@st.cache_data(ttl=1800)
def q_produtos_habituais(cod_vendedor: str):
    df_all = _load_radar_produtos()
    if df_all is not None:
        return df_all[df_all["CodVendedor"] == cod_vendedor].drop(columns=["CodVendedor"]).copy()
    # fallback DB
    sql = """
    SELECT M.CodCliFor, P.NOMEPRODUTO AS Produto,
           SUM(IM.Qtd) AS QtdTotal, COUNT(DISTINCT M.IdMov) AS Frequencia
    FROM Movimento M WITH (NOLOCK)
    INNER JOIN Cli_For CF  WITH (NOLOCK) ON M.CodCliFor = CF.CodCliFor
    INNER JOIN ItensMov IM WITH (NOLOCK) ON M.IdMov = IM.IdMov
    INNER JOIN Produtos P  WITH (NOLOCK) ON IM.IdProduto = P.IdProduto
    WHERE CF.CodFunc = %s
      AND M.DataFaturamento >= DATEADD(MONTH, -6, GETDATE())
      AND M.TipoMov IN ('2.4','2.1') AND M.Status NOT IN ('C','T')
    GROUP BY M.CodCliFor, P.NOMEPRODUTO
    """
    return query_segura(sql, (cod_vendedor,))

@st.cache_data(ttl=1800)
def q_rentabilidade_cliente(cod_vendedor: str, versao=None):
    df_all = _load_radar_rent_cli(versao)
    if df_all is None:
        return pd.DataFrame(columns=["CodCliFor", "Faturamento", "CustoTotal", "Margem", "RentPerc"])
    df = df_all.loc[df_all["CodVendedor"].astype("string").str.strip().eq(cod_vendedor)].copy()
    for coluna in ["Faturamento", "CustoTotal"]:
        df[coluna] = pd.to_numeric(df[coluna], errors="raise")
        if not np.isfinite(df[coluna].to_numpy(dtype=float)).all():
            raise ValueError("Rentabilidade por cliente incompleta.")
    df["Margem"] = df["Faturamento"] - df["CustoTotal"]
    df["RentPerc"] = np.nan
    com_receita = df["Faturamento"].ne(0)
    df.loc[com_receita, "RentPerc"] = (
        df.loc[com_receita, "Margem"] / df.loc[com_receita, "Faturamento"] * 100
    )
    return df.drop(columns=["CodVendedor"])


# ============================================================================
# MOTOR DE CLASSIFICAÇÃO DE RISCO
# ============================================================================
def classificar_clientes(df_hist, df_rent, df_carteira):
    if df_carteira.empty:
        return pd.DataFrame()

    clientes_info = []

    grupos = {cod: grupo for cod, grupo in df_hist.groupby("CodCliFor")}
    for _, cliente in df_carteira.iterrows():
        cod_cli = cliente["CodCliFor"]
        grupo = grupos.get(cod_cli, df_hist.iloc[0:0])
        total_periodo = float(cliente["TotalPeriodo"])
        media_mensal = float(cliente["MediaMensal"])
        info = {
            "CodCliFor":       cod_cli,
            "Cliente":         str(cliente["Cliente"]),
            "Telefone":        "" if pd.isna(cliente["Telefone"]) else str(cliente["Telefone"]),
            "Celular":         "" if pd.isna(cliente["Celular"]) else str(cliente["Celular"]),
            "VendedorCarteira": str(cliente["VendedorCarteira"]),
            "CodVendedorCarteira": cliente["CodVendedorCarteira"],
            "CurvaABC":         cliente["CurvaABC"],
            "PosicaoCurva":     int(cliente["PosicaoCurva"]),
        }

        vendas = grupo[grupo["DataFaturamento"].notna() & (grupo["ValorLiquido"] != 0)].copy()

        if vendas.empty:
            info.update({
                "UltimaCompra": None, "DiasUltimaCompra": 999, "MediaMensal": media_mensal,
                "FatMesAtual": 0, "MesesComCompra": 0, "TotalPeriodo": total_periodo,
                "CicloMedioDias": None, "DiaHabitualCompra": None, "AtrasoCiclo": None,
                "ReceitaEmRisco": 0, "VariacaoVsMedia": -100, "Status": "PERDIDO",
                "TicketMedio": 0, "AbaixoMedia": False,
            })
        else:
            ultima_compra      = vendas["DataFaturamento"].max().date()
            dias_sem_compra    = (HOJE - ultima_compra).days
            primeira_compra    = vendas["DataFaturamento"].min().date()
            dias_desde_primeira = (HOJE - primeira_compra).days

            vendas["MesAno"]   = vendas["DataFaturamento"].dt.to_period("M")
            mensal             = vendas.groupby("MesAno")["ValorLiquido"].sum()
            meses_com_compra   = len(mensal)
            mes_atual_period   = pd.Period(HOJE, freq="M")
            fat_mes_atual      = mensal.get(mes_atual_period, 0)
            qtd_pedidos        = int(cliente["QuantidadeMovimentos"])
            ticket_medio       = total_periodo / qtd_pedidos if qtd_pedidos > 0 else 0
            variacao           = ((fat_mes_atual - media_mensal) / media_mensal * 100) if media_mensal > 0 else 0

            datas_pedidos      = sorted(vendas["DataFaturamento"].dt.date.unique())
            ciclo_medio = dia_habitual = atraso_ciclo = None

            if len(datas_pedidos) >= 3:
                intervalos = [i for i in [(datas_pedidos[j+1] - datas_pedidos[j]).days
                              for j in range(len(datas_pedidos)-1)] if i > 0]
                if intervalos:
                    ciclo_medio       = np.mean(intervalos)
                    dia_habitual      = int(np.median([d.day for d in datas_pedidos]))
                    proxima_esperada  = ultima_compra + timedelta(days=int(ciclo_medio))
                    atraso_ciclo      = max(0, (HOJE - proxima_esperada).days) if HOJE > proxima_esperada else 0

            meses_parado = max(0, dias_sem_compra / 30)
            info.update({
                "UltimaCompra":      ultima_compra,
                "DiasUltimaCompra":  dias_sem_compra,
                "MediaMensal":       media_mensal,
                "FatMesAtual":       round(fat_mes_atual, 2),
                "MesesComCompra":    meses_com_compra,
                "TotalPeriodo":      round(total_periodo, 2),
                "CicloMedioDias":    round(ciclo_medio, 0) if ciclo_medio else None,
                "DiaHabitualCompra": dia_habitual,
                "AtrasoCiclo":       atraso_ciclo,
                "VariacaoVsMedia":   round(variacao, 1),
                "TicketMedio":       round(ticket_medio, 2),
                "ReceitaEmRisco":    round(media_mensal * max(1, meses_parado), 2),
            })

            # Classificação (ordem de prioridade)
            if dias_desde_primeira <= 30:
                info["Status"] = "NOVO"
            elif dias_sem_compra >= 120:
                info["Status"] = "PERDIDO"
            elif dias_sem_compra >= 60:
                info["Status"] = "CRITICO"
            elif fat_mes_atual == 0:
                info["Status"] = "ATENCAO"
            else:
                info["Status"] = "ATIVO"

            # Flag de compra abaixo da média (apenas para quem comprou este mês)
            info["AbaixoMedia"] = bool(fat_mes_atual > 0 and media_mensal > 0 and variacao < -20)

        rent_row = df_rent[df_rent["CodCliFor"] == cod_cli] if not df_rent.empty else pd.DataFrame()
        info["RentPerc"]  = round(rent_row["RentPerc"].iloc[0], 1) if not rent_row.empty else None
        info["MargemRS"]  = round(rent_row["Margem"].iloc[0], 2)   if not rent_row.empty else None

        clientes_info.append(info)

    df_result = pd.DataFrame(clientes_info)
    status_ordem = {"CRITICO": 0, "ATENCAO": 1, "NOVO": 2, "ATIVO": 3, "PERDIDO": 4}
    df_result["_ordem"] = df_result["Status"].map(status_ordem)
    df_result = df_result.sort_values(["_ordem", "ReceitaEmRisco"], ascending=[True, False])
    return df_result.drop(columns=["_ordem"])


def gerar_pivot_cliente(df_hist, cod_cli, n_meses=6):
    vendas = df_hist[(df_hist["CodCliFor"] == cod_cli) & df_hist["DataFaturamento"].notna()]
    if vendas.empty:
        return {}
    vendas = vendas.copy()
    vendas["MesAno"] = vendas["DataFaturamento"].dt.to_period("M")
    mensal = vendas.groupby("MesAno")["ValorLiquido"].sum()
    meses  = pd.period_range(end=pd.Period(HOJE, "M"), periods=n_meses, freq="M")
    return {m.strftime("%m/%Y"): round(mensal.get(m, 0), 2) for m in meses}


def top_produtos_cliente(df_prods, cod_cli, top_n=3):
    cli_prods = df_prods[df_prods["CodCliFor"] == cod_cli]
    if cli_prods.empty:
        return []
    return cli_prods.nlargest(top_n, "Frequencia")["Produto"].tolist()


def render_faixa_prevendas(df_prev_all, vendedores_sel):
    if df_prev_all is None or df_prev_all.empty:
        return
    df = df_prev_all[df_prev_all["CodVendedor"].isin(vendedores_sel)].copy()
    if df.empty:
        return

    df["DiasAberto"] = df["DtMov"].apply(lambda x: (HOJE - x.date()).days)
    df = df.sort_values("DtMov", ascending=True)

    total       = len(df)
    valor_total = df["ValorLiquido"].sum()
    n_travadas  = int((df["DiasAberto"] >= 1).sum())
    n_problemas = int((df["DiasAberto"] >= 2).sum())

    def _brl(v):
        return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    # Cor da faixa
    if n_problemas > 0:
        border_color = "#E74C3C"
        bg_color     = "#FEE2E2"
        icon         = "🔴"
    elif n_travadas > 0:
        border_color = "#F39C12"
        bg_color     = "#FEF3C7"
        icon         = "⚠️"
    else:
        border_color = "#2E6BA6"
        bg_color     = "#EBF5FB"
        icon         = "📋"

    # Label do expander
    label = f"{icon} {total} pré-{'venda aberta' if total == 1 else 'vendas abertas'} · {_brl(valor_total)} em aberto"
    if n_problemas > 0:
        max_dias = int(df[df["DiasAberto"] >= 2]["DiasAberto"].max())
        label += f" · 🔴 {n_problemas} com problema ({max_dias}d parada{'s' if max_dias > 1 else ''})"
    elif n_travadas > 0:
        max_dias = int(df[df["DiasAberto"] >= 1]["DiasAberto"].max())
        label += f" · ⚠️ {n_travadas} travada{'s' if n_travadas > 1 else ''} ({max_dias}d parada{'s' if max_dias > 1 else ''})"

    with st.expander(label, expanded=False):
        rows_html = ""
        for _, row in df.iterrows():
            dias = int(row["DiasAberto"])
            if dias >= 2:
                row_bg    = "#FEE2E2"
                dias_html = f'<span style="color:#E74C3C;font-weight:700;">{dias}d 🔴</span>'
            elif dias == 1:
                row_bg    = "#FEF3C7"
                dias_html = f'<span style="color:#F39C12;font-weight:700;">{dias}d ⚠️</span>'
            else:
                row_bg    = "#FFFFFF"
                dias_html = f'<span style="color:#27AE60;">hoje</span>'

            dt_str  = row["DtMov"].strftime("%d/%m/%Y")
            nome    = str(row["NomeVendedor"])
            cliente = str(row["Cliente"])

            rows_html += f"""
            <tr style="background:{row_bg};">
                <td style="padding:5px 10px;white-space:nowrap;">{nome}</td>
                <td style="padding:5px 10px;">{row['NumMov']}</td>
                <td style="padding:5px 10px;">{cliente}</td>
                <td style="padding:5px 10px;white-space:nowrap;">{dt_str}</td>
                <td style="padding:5px 10px;text-align:center;">{dias_html}</td>
                <td style="padding:5px 10px;text-align:right;font-weight:600;white-space:nowrap;">{_brl(row['ValorLiquido'])}</td>
            </tr>
            """

        table_html = f"""
        <style>
          table.prev-tbl {{
            width:100%;border-collapse:collapse;
            font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
            font-size:0.8rem;color:#1B3A5C;
          }}
          table.prev-tbl th {{
            background:#1B3A5C;color:white;padding:5px 10px;
            font-size:0.7rem;font-weight:700;text-align:left;
            white-space:nowrap;letter-spacing:.4px;
          }}
          table.prev-tbl td {{ border-bottom:1px solid #F0F0F0; }}
        </style>
        <table class="prev-tbl">
          <thead><tr>
            <th>Vendedor</th><th>NumMov</th><th>Cliente</th><th>DtMov</th>
            <th style="text-align:center;">Dias</th>
            <th style="text-align:right;">Valor Líquido</th>
          </tr></thead>
          <tbody>{rows_html}</tbody>
        </table>
        """

        components.html(table_html, height=46 + total * 36, scrolling=False)


def render_faixa_orcamentos(df_orc_all, vendedores_sel):
    """Renderiza faixa de orçamentos em aberto com status do pipeline."""
    if df_orc_all is None or df_orc_all.empty:
        return

    df = df_orc_all[df_orc_all["CodVendedor"].isin(vendedores_sel)].copy()
    if df.empty:
        return

    df["DiasAberto"] = df["DtMov"].apply(lambda x: (HOJE - x.date()).days)

    total       = len(df)
    valor_total = df["ValorLiquido"].sum()

    # Contar por status de pipeline
    status_counts = df["CodTd_PO"].value_counts().to_dict()
    n_venda_perdida = status_counts.get("Venda Perdida", 0)
    n_problemas = int((df["DiasAberto"] >= 7).sum())  # Orçamentos com 7+ dias

    def _brl(v):
        return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    # Cor da faixa baseada em vendas perdidas ou tempo
    if n_venda_perdida > 0:
        icon = "🔴"
    elif n_problemas > 0:
        icon = "⚠️"
    else:
        icon = "💼"

    # Label do expander
    label = f"{icon} {total} orçamento{'s' if total != 1 else ''} em aberto · {_brl(valor_total)}"
    if n_venda_perdida > 0:
        label += f" · 🔴 {n_venda_perdida} venda{'s' if n_venda_perdida > 1 else ''} perdida{'s' if n_venda_perdida > 1 else ''}"

    with st.expander(label, expanded=False):
        rows_html = ""
        for _, row in df.iterrows():
            dias = int(row["DiasAberto"])
            status_pipeline = str(row["CodTd_PO"])

            # Cor baseada no status do pipeline
            if status_pipeline == "Venda Perdida":
                row_bg = "#FEE2E2"
                status_badge = '<span style="background:#E74C3C;color:white;padding:2px 8px;border-radius:8px;font-size:0.7rem;font-weight:700;">Venda Perdida</span>'
            elif status_pipeline == "Preço Concorren":
                row_bg = "#FEF3C7"
                status_badge = '<span style="background:#F39C12;color:white;padding:2px 8px;border-radius:8px;font-size:0.7rem;font-weight:700;">Preço Concorren</span>'
            elif status_pipeline == "Faltas":
                row_bg = "#FFF9E6"
                status_badge = '<span style="background:#FFA500;color:white;padding:2px 8px;border-radius:8px;font-size:0.7rem;font-weight:700;">Faltas</span>'
            else:  # Negociando
                row_bg = "#F0F7FF"
                status_badge = '<span style="background:#2E6BA6;color:white;padding:2px 8px;border-radius:8px;font-size:0.7rem;font-weight:700;">Negociando</span>'

            dt_str  = row["DtMov"].strftime("%d/%m/%Y")
            nome    = str(row["NomeVendedor"])
            cliente = str(row["NomeCliFor"])

            rows_html += f"""
            <tr style="background:{row_bg};">
                <td style="padding:5px 10px;white-space:nowrap;">{nome}</td>
                <td style="padding:5px 10px;">{row['NumMov']}</td>
                <td style="padding:5px 10px;">{cliente}</td>
                <td style="padding:5px 10px;white-space:nowrap;">{dt_str}</td>
                <td style="padding:5px 10px;text-align:center;white-space:nowrap;">{dias}d</td>
                <td style="padding:5px 10px;text-align:center;">{status_badge}</td>
                <td style="padding:5px 10px;text-align:right;font-weight:600;white-space:nowrap;">{_brl(row['ValorLiquido'])}</td>
            </tr>
            """

        table_html = f"""
        <style>
          table.orc-tbl {{
            width:100%;border-collapse:collapse;
            font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
            font-size:0.8rem;color:#1B3A5C;
          }}
          table.orc-tbl th {{
            background:#1B3A5C;color:white;padding:5px 10px;
            font-size:0.7rem;font-weight:700;text-align:left;
            white-space:nowrap;letter-spacing:.4px;
          }}
          table.orc-tbl td {{ border-bottom:1px solid #F0F0F0; }}
        </style>
        <table class="orc-tbl">
          <thead><tr>
            <th>Vendedor</th><th>NumMov</th><th>Cliente</th><th>Data</th>
            <th style="text-align:center;">Dias</th>
            <th style="text-align:center;">Status</th>
            <th style="text-align:right;">Valor Líquido</th>
          </tr></thead>
          <tbody>{rows_html}</tbody>
        </table>
        """

        components.html(table_html, height=46 + total * 36, scrolling=False)


# ============================================================================
# SESSION STATE
# ============================================================================
# multiselect_vendedores já foi inicializado pelo check_session() com base no role
if "multiselect_vendedores" not in st.session_state:
    st.session_state["multiselect_vendedores"] = []

if "filtro_status_list" not in st.session_state:
    st.session_state["filtro_status_list"] = ["CRITICO", "ATENCAO"]


# ============================================================================
# CARREGAR LISTA DE VENDEDORES E SUPERVISORES
# ============================================================================
try:
    df_vendedores  = q_carteira_vendedores()
    df_supervisores = q_supervisores()
except Exception as e:
    st.error(f"❌ Erro de conexão: {e}")
    st.stop()

for _coluna in ["CodVendedor", "CodSupervisor"]:
    df_vendedores[_coluna] = df_vendedores[_coluna].fillna("").astype("string").str.strip()
df_supervisores["CodVendedor"] = df_supervisores["CodVendedor"].fillna("").astype("string").str.strip()
_role_radar = str(_auth_user.get("role", "")).strip().lower()
_gestao_radar = _role_radar in {"dev", "gestao"}
df_vendedores = _vendedores_autorizados(df_vendedores, _auth_user)
if df_vendedores.empty and not _gestao_radar:
    st.error("Seu acesso ainda nao esta vinculado a uma carteira ou equipe. Solicite a revisao do cadastro.")
    render_logout_sidebar(_auth_user)
    st.stop()
if not _gestao_radar:
    df_supervisores = df_supervisores.loc[
        df_supervisores["CodVendedor"].isin(df_vendedores["CodSupervisor"])
    ].copy()
_codigos_permitidos = set(df_vendedores["CodVendedor"])
_selecionados_validos = [str(c).strip() for c in st.session_state.get("multiselect_vendedores", [])
                         if str(c).strip() in _codigos_permitidos]
if not _selecionados_validos and not _gestao_radar:
    _selecionados_validos = df_vendedores["CodVendedor"].tolist()
st.session_state["multiselect_vendedores"] = _selecionados_validos
_supervisores_permitidos = {"TODOS"} | set(df_supervisores["CodVendedor"])
if st.session_state.get("sel_supervisor", "TODOS") not in _supervisores_permitidos:
    st.session_state["sel_supervisor"] = "TODOS"

nome_vendedor_map = dict(zip(df_vendedores["CodVendedor"], df_vendedores["Vendedor"]))


# ============================================================================
# SIDEBAR
# ============================================================================
def _save_radar_vendedores():
    selecionados = st.session_state.get("multiselect_vendedores", [])
    # Persistir no JSON local (compatibilidade)
    prefs = _load_prefs()
    prefs["radar_vendedores"] = selecionados
    _save_prefs(prefs)
    # Persistir no parquet para dev/gestao (cross-session)
    salvar_filtros_usuario(_auth_user["cod"], selecionados, _auth_user.get("token", ""))


def on_supervisor_change():
    sup = st.session_state.get("sel_supervisor", "TODOS")
    if sup != "TODOS":
        vendors_sup = df_vendedores[df_vendedores["CodSupervisor"] == sup]["CodVendedor"].tolist()
        if vendors_sup:
            st.session_state["multiselect_vendedores"] = vendors_sup
            _save_radar_vendedores()


def _selecionar_todas():
    st.session_state["multiselect_vendedores"] = df_vendedores["CodVendedor"].tolist()
    _save_radar_vendedores()


def _limpar_vendedores():
    st.session_state["multiselect_vendedores"] = []
    _save_radar_vendedores()

with st.sidebar:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=120)
    st.markdown("### 🎯 Radar de Risco")
    st.markdown("---")

    # Filtro supervisor
    sup_options = ["TODOS"] + df_supervisores["CodVendedor"].tolist()
    st.selectbox(
        "👥 Supervisor:",
        options=sup_options,
        format_func=lambda x: "Todos os supervisores" if x == "TODOS" else
            df_supervisores[df_supervisores["CodVendedor"] == x]["Supervisor"].iloc[0],
        key="sel_supervisor",
        on_change=on_supervisor_change,
    )

    # Multi-select vendedoras
    st.multiselect(
        "👤 Vendedora(s):",
        options=df_vendedores["CodVendedor"].tolist(),
        format_func=lambda x: nome_vendedor_map.get(x, x),
        key="multiselect_vendedores",
        on_change=_save_radar_vendedores,
        placeholder="Selecione uma ou mais vendedoras...",
    )

    col_a, col_b = st.columns(2)
    with col_a:
        st.button("✅ Todas", use_container_width=True, on_click=_selecionar_todas)
    with col_b:
        st.button("✖ Limpar", use_container_width=True, on_click=_limpar_vendedores)

    st.markdown("---")

    # Filtro de status (sincronizado com os cards)
    st.multiselect(
        "Filtrar por status:",
        ["CRITICO", "ATENCAO", "ATIVO", "NOVO", "PERDIDO"],
        key="filtro_status_list",
        format_func=lambda x: {
            "CRITICO": "🔴 Crítico", "ATENCAO": "🟡 Atenção",
            "ATIVO": "🟢 Ativo",    "NOVO": "🔵 Novo", "PERDIDO": "💀 Perdido",
        }[x],
    )

    st.markdown("---")
    st.caption(f"📅 Hoje: {HOJE.strftime('%d/%m/%Y')}")
    _ts = _cache_ts()
    if _ts:
        st.caption(f"📦 Cache de {_ts}")
    else:
        st.caption("⚠️ Carteira aguardando atualizacao")
    render_logout_sidebar(_auth_user)


# ============================================================================
# VALIDAÇÃO
# ============================================================================
vendedores_sel = st.session_state.get("multiselect_vendedores", [])
# Filtrar para garantir que só contém códigos válidos (JSON pode ter códigos antigos)
vendedores_validos = set(df_vendedores["CodVendedor"].tolist())
vendedores_sel = [v for v in vendedores_sel if v in vendedores_validos]

if not vendedores_sel:
    st.markdown("""
    <div style="text-align:center; padding:60px 20px;">
        <div style="font-size:3rem;">🎯</div>
        <div style="font-size:1.6rem; font-weight:700; color:#1B3A5C; margin:16px 0 8px;">
            Bem-vindo ao Radar de Risco
        </div>
        <div style="font-size:1rem; color:#95A5A6; margin-bottom:24px;">
            Selecione uma ou mais vendedoras no painel lateral para carregar a carteira.
        </div>
        <div style="font-size:0.85rem; color:#BDC3C7;">
            ← Use o filtro à esquerda. A última seleção é salva automaticamente.
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()


# ============================================================================
# CARREGAR DADOS
# ============================================================================
try:
    with st.spinner("🔄 Analisando carteira..."):
        df_carteira, df_hist = q_base_carteira(vendedores_sel)
        _rent_path = CACHE_DIR / "radar_rent_cli.parquet"
        _rent_versao = ((_rent_path.stat().st_mtime_ns, _rent_path.stat().st_size)
                        if _rent_path.exists() else None)
        dfs_rent = [q_rentabilidade_cliente(cod, _rent_versao) for cod in vendedores_sel]
        dfs_rent = [df for df in dfs_rent if not df.empty]
        df_rent = (
            pd.concat(dfs_rent, ignore_index=True).drop_duplicates(subset=["CodCliFor"])
            if dfs_rent else pd.DataFrame()
        )
        df_clientes = classificar_clientes(df_hist, df_rent, df_carteira)
except Exception as e:
    print(f"[Radar carteira] {type(e).__name__}: {e}")
    st.error("Nao foi possivel carregar a carteira atualizada. Solicite a atualizacao dos dados e recarregue a pagina.")
    st.stop()

# ============================================================================
# HEADER — título dinâmico conforme seleção
# ============================================================================
n_sel = len(vendedores_sel)
todos_os_vendedores = set(df_vendedores["CodVendedor"].tolist())

if n_sel == 1:
    titulo = f"🎯 Radar de Risco — {nome_vendedor_map.get(vendedores_sel[0], vendedores_sel[0])}"
elif set(vendedores_sel) == todos_os_vendedores:
    titulo = "🎯 Radar de Risco — Equipe Completa"
else:
    sup_sel = st.session_state.get("sel_supervisor", "TODOS")
    if sup_sel != "TODOS" and not df_supervisores.empty:
        row = df_supervisores[df_supervisores["CodVendedor"] == sup_sel]
        sup_nome = row["Supervisor"].iloc[0] if not row.empty else ""
        titulo = f"🎯 Radar de Risco — Equipe {sup_nome}" if sup_nome else f"🎯 Radar de Risco — {n_sel} Vendedoras"
    else:
        titulo = f"🎯 Radar de Risco — {n_sel} Vendedoras"

subtitulo_extra = "" if n_sel == 1 else f" · {n_sel} vendedoras · {len(df_clientes)} clientes"

st.markdown(f"""
<div style="display:flex; align-items:center; gap:16px; padding-bottom:16px;
            border-bottom:3px solid #2E6BA6; margin-bottom:20px;">
    <div>
        <div style="font-size:1.6rem; font-weight:700; color:#1B3A5C;">{titulo}</div>
        <div style="font-size:0.85rem; color:#95A5A6;">
            Carteira de clientes · {HOJE.strftime('%d/%m/%Y')}{subtitulo_extra}
        </div>
    </div>
</div>
""", unsafe_allow_html=True)


# ============================================================================
# KPIs DO MÊS ATUAL
# Fonte: QueryPrincipal de Rentabilidade por Periodo - GM.
# Carteira por CodFunc; indicadores financeiros por Movimento.CodVendedor.
# ============================================================================
_kpi_pedidos  = None
_kpi_fat_mes  = None
_kpi_rent_pct = None
_financeiro = None
_resumo_financeiro = None
_visao_global_financeiro = (
    _gestao_radar and n_sel > 1 and set(vendedores_sel) == todos_os_vendedores
)
try:
    _financeiro = _load_financeiro_cronos(_versao_cache_financeiro())
    _resumo_financeiro = _resumo_financeiro_cronos(
        _financeiro, vendedores_sel, visao_global=_visao_global_financeiro
    )
    _kpi_pedidos = _resumo_financeiro["qtd"]
    _kpi_fat_mes = _resumo_financeiro["receita"]
    _kpi_rent_pct = _resumo_financeiro["margem"]
except Exception as e:
    print(f"[Radar financeiro] {type(e).__name__}: {e}")
    st.warning("Os indicadores financeiros aguardam atualizacao dos dados.")

kc1, kc2, kc3 = st.columns(3)
_card_style = ("background:#F0F5FA; border-radius:10px; padding:14px 20px; text-align:center;"
               " box-shadow:0 1px 4px rgba(0,0,0,0.06);")
with kc1:
    _v = str(_kpi_pedidos) if _kpi_pedidos is not None else "—"
    st.markdown(f"""
    <div style="{_card_style}">
        <div style="font-size:0.7rem; color:#95A5A6; text-transform:uppercase; letter-spacing:.8px;">
            Qtd. pedidos — Cronos</div>
        <div style="font-size:1.8rem; font-weight:700; color:#1B3A5C;">{_v}</div>
    </div>""", unsafe_allow_html=True)
with kc2:
    if _kpi_fat_mes is not None:
        _v = f"R$ {_kpi_fat_mes:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    else:
        _v = "—"
    st.markdown(f"""
    <div style="{_card_style}">
        <div style="font-size:0.7rem; color:#95A5A6; text-transform:uppercase; letter-spacing:.8px;">
            Faturado — mês atual</div>
        <div style="font-size:1.8rem; font-weight:700; color:#1B3A5C;">{_v}</div>
    </div>""", unsafe_allow_html=True)
with kc3:
    if _kpi_rent_pct is not None:
        _rent_color = "#27AE60" if _kpi_rent_pct >= 25 else ("#F39C12" if _kpi_rent_pct >= 15 else "#E74C3C")
        _v = f"{_kpi_rent_pct:.2f}%".replace(".", ",")
    else:
        _rent_color = "#BDC3C7"
        _v = "—"
    st.markdown(f"""
    <div style="{_card_style}">
        <div style="font-size:0.7rem; color:#95A5A6; text-transform:uppercase; letter-spacing:.8px;">
            Rentabilidade — mês atual</div>
        <div style="font-size:1.8rem; font-weight:700; color:{_rent_color};">{_v}</div>
    </div>""", unsafe_allow_html=True)

st.markdown("")

if _financeiro is not None and _resumo_financeiro is not None:
    _inicio_fin = pd.Timestamp(_financeiro["PeriodoInicio"].iloc[0])
    _fim_fin = pd.Timestamp(_financeiro["PeriodoFimInclusivo"].iloc[0])
    _atualizado_fin = pd.Timestamp(_financeiro["AtualizadoEmUTC"].iloc[0]).tz_convert("America/Sao_Paulo")
    _escopo_fin = "Consolidado geral" if _visao_global_financeiro else "Vendedoras selecionadas"
    st.caption(
        f"{_escopo_fin} · {_inicio_fin:%d/%m} a {_fim_fin:%d/%m/%Y} · "
        f"Atualizado em {_atualizado_fin:%d/%m/%Y %H:%M}"
    )
    if _gestao_radar:
        with st.expander("Conferencia com o Cronos"):
            st.caption(
                "Faturamento e custo seguem a data de faturamento e o vendedor da movimentacao. "
                "Qtd. pedidos segue a contagem propria do relatorio, pela data do movimento. "
                "O consolidado geral inclui EMPRESA, INATIVADOS e demais registros do relatorio. "
                "A carteira de clientes segue a responsavel atual."
            )
            _conferencia_fin = _exportar_financeiro_cronos(_resumo_financeiro["linhas"])
            _tabela_fin = _conferencia_fin.copy()
            for _col in ["PrecoLiquido", "CustoLiqU", "ValorRentabilidadeItem"]:
                _tabela_fin[_col] = _tabela_fin[_col].map(fmt_moeda)
            st.dataframe(_tabela_fin, hide_index=True, use_container_width=True)
            st.markdown(
                f"**Custo:** {fmt_moeda(_resumo_financeiro['custo'])} · "
                f"**Rentabilidade em reais:** {fmt_moeda(_resumo_financeiro['lucro'])}"
            )
            st.download_button(
                "Baixar conferencia financeira (CSV)",
                data=_conferencia_fin.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"radar_cronos_{_inicio_fin:%Y%m%d}_{_fim_fin:%Y%m%d}.csv",
                mime="text/csv", key="download_conferencia_cronos",
            )

# ============================================================================
# FAIXA DE PRÉ-VENDAS ABERTAS
# ============================================================================
render_faixa_prevendas(_load_prevendas_cache(), vendedores_sel)

# ============================================================================
# FAIXA DE ORÇAMENTOS ABERTOS
# ============================================================================
render_faixa_orcamentos(_load_orcamentos_cache(), vendedores_sel)

# ============================================================================
# CARDS DE STATUS — clicáveis, sincronizados com sidebar
# ============================================================================

if df_clientes.empty:
    st.info("Nenhum cliente encontrado na carteira das vendedoras selecionadas.")
    st.stop()
def toggle_status(status):
    current = list(st.session_state.get("filtro_status_list", []))
    if status in current:
        current.remove(status)
    else:
        current.append(status)
    st.session_state["filtro_status_list"] = current


contagens    = df_clientes["Status"].value_counts()
receita_risco = df_clientes.groupby("Status")["ReceitaEmRisco"].sum()
active_filters = set(st.session_state.get("filtro_status_list", []))

# Marcador para scoping CSS dos cards
st.markdown('<div id="status-cards-marker"></div>', unsafe_allow_html=True)

c1, c2, c3, c4, c5 = st.columns(5)

with c1:
    n = contagens.get("CRITICO", 0)
    r = receita_risco.get("CRITICO", 0)
    is_on = "CRITICO" in active_filters
    st.button(
        f"🔴  {n}\nCRÍTICO\n{fmt_brl(r)} em risco",
        key="btn_critico", use_container_width=True,
        type="primary" if is_on else "secondary",
        on_click=toggle_status, args=("CRITICO",),
    )

with c2:
    n = contagens.get("ATENCAO", 0)
    r = receita_risco.get("ATENCAO", 0)
    is_on = "ATENCAO" in active_filters
    st.button(
        f"🟡  {n}\nATENÇÃO\n{fmt_brl(r)} em risco",
        key="btn_atencao", use_container_width=True,
        type="primary" if is_on else "secondary",
        on_click=toggle_status, args=("ATENCAO",),
    )

with c3:
    n   = contagens.get("ATIVO", 0)
    fat = df_clientes[df_clientes["Status"] == "ATIVO"]["FatMesAtual"].sum()
    is_on = "ATIVO" in active_filters
    st.button(
        f"🟢  {n}\nATIVO\n{fmt_brl(fat)} no mês",
        key="btn_ativo", use_container_width=True,
        type="primary" if is_on else "secondary",
        on_click=toggle_status, args=("ATIVO",),
    )

with c4:
    n = contagens.get("PERDIDO", 0)
    is_on = "PERDIDO" in active_filters
    st.button(
        f"💀  {n}\nPERDIDO\n ",
        key="btn_perdido", use_container_width=True,
        type="primary" if is_on else "secondary",
        on_click=toggle_status, args=("PERDIDO",),
    )

with c5:
    n = contagens.get("NOVO", 0)
    is_on = "NOVO" in active_filters
    st.button(
        f"🔵  {n}\nNOVO\n ",
        key="btn_novo", use_container_width=True,
        type="primary" if is_on else "secondary",
        on_click=toggle_status, args=("NOVO",),
    )


# ============================================================================
# TOOLTIP EXPLICATIVO
# ============================================================================
with st.expander("ℹ️ Como funciona a classificação de risco?"):
    st.markdown("""
    <div class="info-box">
    <strong>🔴 CRÍTICO</strong> — Cliente sem compra há <strong>60 dias ou mais</strong>.
    Pulou pelo menos 2 ciclos. Risco real de perda. <strong>Ação:</strong> ligar HOJE.<br><br>

    <strong>🟡 ATENÇÃO</strong> — Cliente que <strong>ainda não comprou no mês vigente</strong>.
    No momento que virar o mês, entra em atenção até realizar uma compra. <strong>Ação:</strong> ligar esta semana.<br><br>
    <strong>📉 Abaixo da média</strong> — Cliente <strong>ATIVO</strong> que comprou este mês mas com valor
    <strong>20%+ abaixo da média mensal</strong>. Aparece com bandeira laranja na listagem de ativos.<br><br>

    <strong>🟢 ATIVO</strong> — Cliente comprando dentro do padrão esperado.<br><br>

    <strong>🔵 NOVO</strong> — Primeira compra nos últimos <strong>30 dias</strong>. Fidelizar com follow-up antes que a segunda compra não aconteça.<br><br>

    <strong>💀 PERDIDO</strong> — Sem compra há <strong>120+ dias</strong>. Provável migração para
    concorrente. Tentar resgate.<br><br>

    <strong>📊 Receita em Risco</strong> = Média mensal × meses parado.<br>
    <strong>🔄 Ciclo de Compra</strong> = Média de dias entre pedidos. O <strong>dia habitual</strong>
    é a mediana do dia do mês em que o cliente costuma comprar.
    </div>
    """, unsafe_allow_html=True)


# ============================================================================
# LISTA DE CLIENTES
# ============================================================================
st.markdown("---")

filtro_status = st.session_state.get("filtro_status_list", [])
df_filtrado   = df_clientes[df_clientes["Status"].isin(filtro_status)] if filtro_status else df_clientes
filtro_curva = st.multiselect(
    "Filtrar por curva ABC:", ["A", "B", "C"], default=[], key="filtro_curva_abc"
)
st.caption("Curva global da carteira: 20% A, 30% B e 50% C. A selecao de vendedoras preserva a curva.")
if filtro_curva:
    df_filtrado = df_filtrado[df_filtrado["CurvaABC"].isin(filtro_curva)]

busca = st.text_input("🔍 Buscar cliente:", "", placeholder="Digite o nome do cliente...")
if busca:
    df_filtrado = df_filtrado[df_filtrado["Cliente"].str.contains(busca, case=False, na=False, regex=False)]

st.markdown(
    f'<div style="color:#1B3A5C; font-size:1rem; font-weight:600; '
    f'border-bottom:2px solid #E8F4FD; padding-bottom:8px; margin-bottom:12px;">'
    f'📋 {len(df_filtrado)} clientes encontrados</div>',
    unsafe_allow_html=True,
)

# Renderizar cada cliente via components.html (evita bug de HTML quebrado no st.markdown)
for _, cli in df_filtrado.iterrows():
    status       = cli["Status"]
    card_cls     = f"risco-{status.lower()}" if status != "ATENCAO" else "risco-atencao"
    badge_cls    = f"badge-{status.lower()}" if status != "ATENCAO" else "badge-atencao"
    status_emoji = {"CRITICO": "🔴", "ATENCAO": "🟡", "ATIVO": "🟢", "PERDIDO": "💀", "NOVO": "🔵"}.get(status, "")
    status_label = {"CRITICO": "CRÍTICO", "ATENCAO": "ATENÇÃO", "ATIVO": "ATIVO", "PERDIDO": "PERDIDO", "NOVO": "NOVO"}.get(status, "")

    # Pivot mini
    pivot   = gerar_pivot_cliente(df_hist, cli["CodCliFor"], 6)
    pivot_html = ""
    if pivot:
        headers = "".join(f"<th>{m}</th>" for m in pivot.keys())
        cells   = "".join(
            f'<td class="pivot-cell {"pivot-zero" if v == 0 else "pivot-value"}">{fmt_brl(v)}</td>'
            for v in pivot.values()
        )
        pivot_html = f"<table><tr>{headers}</tr><tr>{cells}</tr></table>"

    # Ciclo
    ciclo_parts = []
    if cli["CicloMedioDias"] and cli["CicloMedioDias"] > 0:
        ciclo_parts.append(f"🔄 Ciclo médio: <strong>{int(cli['CicloMedioDias'])} dias</strong>")
        if cli["DiaHabitualCompra"]:
            ciclo_parts.append(f"dia habitual ~{cli['DiaHabitualCompra']}")
        if cli["AtrasoCiclo"] and cli["AtrasoCiclo"] > 0:
            ciclo_parts.append(f"<span style='color:#E74C3C;'>⚠️ {int(cli['AtrasoCiclo'])} dias atrasado</span>")
    ciclo_text = " · ".join(ciclo_parts)

    # Alerta
    alerta = ""
    if status == "CRITICO":
        alerta = f'<div class="cliente-alerta" style="color:#E74C3C;">⚠️ Sem compra há {fmt_dias(cli["DiasUltimaCompra"])} · Receita em risco: {fmt_brl(cli["ReceitaEmRisco"])}</div>'
    elif status == "ATENCAO":
        if cli.get("AtrasoCiclo") and cli["AtrasoCiclo"] > 0:
            alerta = f'<div class="cliente-alerta" style="color:#F39C12;">⚠️ Ciclo atrasado {int(cli["AtrasoCiclo"])} dias · Última compra: {fmt_dias(cli["DiasUltimaCompra"])} atrás</div>'
        else:
            alerta = f'<div class="cliente-alerta" style="color:#F39C12;">⚠️ Sem compra há {fmt_dias(cli["DiasUltimaCompra"])}</div>'
    elif status == "NOVO":
        alerta = '<div class="cliente-acao">🔵 Cliente novo — fidelizar com follow-up</div>'
    elif status == "ATIVO" and cli.get("AbaixoMedia", False):
        alerta = f'<div class="cliente-alerta" style="color:#E67E22;">📉 Comprou {abs(cli["VariacaoVsMedia"]):.0f}% abaixo da média este mês</div>'

    _wha_num     = _fmt_whatsapp(cli.get("Celular", ""))
    _wha_display = _fmt_phone_display(cli.get("Celular", ""))
    if _wha_num and _wha_display:
        tel_html = f'<a href="https://wa.me/{_wha_num}" target="_blank" style="color:#25D366; text-decoration:none;">📱 {_wha_display}</a>'
    else:
        tel_html = "📵 Sem WhatsApp"
    if pd.notna(cli["UltimaCompra"]):
        ult_compra = cli["UltimaCompra"].strftime("%d/%m/%Y")
        ultima_compra_texto = f"{ult_compra} ({fmt_dias(cli['DiasUltimaCompra'])} atras)"
    else:
        ult_compra = "Sem compra nos 12 meses analisados"
        ultima_compra_texto = ult_compra
    _rent_texto = (f"{cli['RentPerc']:.1f}%".replace(".", ",")
                   if pd.notna(cli["RentPerc"]) else "—")
    vendedor_line = f'👤 {cli["VendedorCarteira"]} · ' if n_sel > 1 and cli["VendedorCarteira"] else ""

    card_html = f"""
    {CARD_CSS}
    <div class="cliente-card {card_cls}">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div>
                <span class="cliente-nome">{cli['Cliente'][:50]}</span>
                <span class="cliente-badge {badge_cls}">{status_emoji} {status_label} · Curva {cli['CurvaABC']}</span>
            </div>
            <div style="text-align:right;">
                <div style="font-size:1.1rem; font-weight:700; color:#1B3A5C;">
                    {fmt_moeda(cli['MediaMensal'])}<span style="font-size:0.7rem; color:#95A5A6;">/mês</span>
                </div>
                <div style="font-size:0.78rem; color:#95A5A6;">
                <div style="font-size:0.78rem; color:#1B3A5C; line-height:1.6;">
                    No mês: <strong>{fmt_moeda(cli['FatMesAtual'])}</strong><br>
                    No período (12 meses): <strong>{fmt_moeda(cli['TotalPeriodo'])}</strong>
                </div>
                    Rent. 6 meses: {_rent_texto} · Ticket: {fmt_brl(cli['TicketMedio'])}
                </div>
            </div>
        </div>
        {alerta}
        <div class="cliente-meta">
            {vendedor_line}{tel_html} · 📅 Última compra: {ultima_compra_texto}<br>
            {ciclo_text}
        </div>
        {pivot_html}
    </div>
    """


    # Calcula altura estimando quebras de linha por comprimento de texto
    # ~40 chars por linha em mobile é o pior caso conservador
    CHARS_POR_LINHA = 40
    PX_POR_LINHA    = 22

    def linhas(texto):
        return max(1, (len(str(texto)) + CHARS_POR_LINHA - 1) // CHARS_POR_LINHA)

    altura = 144  # header + nome + valores + ticket
    altura += linhas(ult_compra) * PX_POR_LINHA
    if alerta:     altura += 30
    if ciclo_text: altura += linhas(ciclo_text) * PX_POR_LINHA + 6
    if pivot_html: altura += 62
    if n_sel > 1:  altura += 20

    components.html(card_html, height=altura, scrolling=False)


# ============================================================================
# RESUMO DE AÇÕES
# ============================================================================
st.markdown("---")

criticos = df_clientes[df_clientes["Status"] == "CRITICO"]
atencao  = df_clientes[df_clientes["Status"] == "ATENCAO"]
novos    = df_clientes[df_clientes["Status"] == "NOVO"]

if n_sel == 1:
    resumo_titulo = f"📋 RESUMO DE AÇÕES — {nome_vendedor_map.get(vendedores_sel[0], '')}"
else:
    resumo_titulo = f"📋 RESUMO DE AÇÕES — {titulo.replace('🎯 Radar de Risco — ', '')}"

st.markdown(f"""
<div style="background:#F0F5FA; border-radius:12px; padding:20px; margin-top:10px;">
    <div style="font-size:1.1rem; font-weight:700; color:#1B3A5C; margin-bottom:12px;">
        {resumo_titulo}
    </div>
    <div style="font-size:0.9rem; color:#5D6D7E; line-height:1.8;">
        🔴 <strong>{len(criticos)} clientes</strong> para ligar <strong>HOJE</strong>
        — Receita em risco: <strong style="color:#E74C3C;">{fmt_brl(criticos['ReceitaEmRisco'].sum())}</strong><br>
        🟡 <strong>{len(atencao)} clientes</strong> para ligar <strong>ESTA SEMANA</strong>
        — Receita em risco: <strong style="color:#F39C12;">{fmt_brl(atencao['ReceitaEmRisco'].sum())}</strong><br>
        🔵 <strong>{len(novos)} clientes NOVOS</strong> para fidelizar com follow-up<br>
        <br>
        💰 <strong>Receita total em risco:
        <span style="color:#E74C3C;">{fmt_brl(criticos['ReceitaEmRisco'].sum() + atencao['ReceitaEmRisco'].sum())}</span>
        </strong>
    </div>
</div>
""", unsafe_allow_html=True)


# ============================================================================
# RODAPÉ
# ============================================================================
st.markdown("---")
_ts_footer = _cache_ts()
_cache_info = f"Cache de {_ts_footer}" if _ts_footer else "⚠️ Dados ao vivo (ETL pendente)"
st.caption(f"GM Limpeza — Radar de Risco v2.0 · {titulo.replace('🎯 Radar de Risco — ', '')} · {HOJE.strftime('%d/%m/%Y')} · {_cache_info} · Desenvolvido por Victor Monteiro")
