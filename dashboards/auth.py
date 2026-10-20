"""
GM Limpeza — Módulo de Autenticação
Sessão persistida via cookie (token) + sessions.parquet server-side.
"""

import json
import uuid
import bcrypt
import pandas as pd
import streamlit as st
import extra_streamlit_components as stx
from datetime import date, datetime, time
from pathlib import Path

CACHE_DIR = Path(__file__).parent.parent / "cache"
USUARIOS_FILE  = CACHE_DIR / "usuarios.parquet"
HISTORICO_FILE = CACHE_DIR / "login_historico.parquet"
SESSIONS_FILE  = CACHE_DIR / "sessions.parquet"

SESSION_COOKIE = "gm_radar_token"
ROLES_LIVRE = {"dev", "gestao"}


# ============================================================================
# COOKIE MANAGER
# ============================================================================

def _cookie_manager():
    if "_cm" not in st.session_state:
        st.session_state["_cm"] = stx.CookieManager(key="gm_auth_cookies")
    return st.session_state["_cm"]


# ============================================================================
# SESSIONS PARQUET
# ============================================================================

def _load_sessions() -> pd.DataFrame:
    if not SESSIONS_FILE.exists():
        return pd.DataFrame(columns=["token", "CodVendedor", "NomeVendedor", "Role", "Expiry", "LastFilters"])
    df = pd.read_parquet(SESSIONS_FILE)
    df["Expiry"] = pd.to_datetime(df["Expiry"])
    return df


def _save_sessions(df: pd.DataFrame):
    df.to_parquet(SESSIONS_FILE, index=False)


def _criar_session_token(row: pd.Series, filtros: list) -> str:
    token = str(uuid.uuid4())
    df = _load_sessions()
    # Remover tokens antigos do mesmo usuário
    df = df[df["CodVendedor"] != row["CodVendedor"]]
    novo = pd.DataFrame([{
        "token": token,
        "CodVendedor": row["CodVendedor"],
        "NomeVendedor": row["NomeVendedor"],
        "Role": row["Role"],
        "Expiry": _expiry_hoje(),
        "LastFilters": json.dumps(filtros),
    }])
    df = pd.concat([df, novo], ignore_index=True)
    _save_sessions(df)
    return token


def _buscar_session(token: str) -> pd.Series | None:
    """Retorna a linha da sessão se válida, ou None."""
    if not token:
        return None
    df = _load_sessions()
    linha = df[df["token"] == token]
    if linha.empty:
        return None
    row = linha.iloc[0]
    if datetime.now() > row["Expiry"]:
        # Sessão expirada — limpar
        _remover_session(token)
        return None
    return row


def _remover_session(token: str):
    df = _load_sessions()
    df = df[df["token"] != token]
    _save_sessions(df)


def _atualizar_last_filters_session(token: str, filtros: list):
    df = _load_sessions()
    df.loc[df["token"] == token, "LastFilters"] = json.dumps(filtros)
    _save_sessions(df)


# ============================================================================
# PERSISTÊNCIA DE USUÁRIOS
# ============================================================================

def _load_usuarios() -> pd.DataFrame:
    if not USUARIOS_FILE.exists():
        return pd.DataFrame(columns=[
            "CodVendedor", "NomeVendedor", "Role", "PasswordHash",
            "FirstLogin", "ResetRequired", "Active",
            "CreatedAt", "LastLogin", "LastFilters",
        ])

    df = pd.read_parquet(USUARIOS_FILE)

    df["LastLogin"] = pd.to_datetime(
        df["LastLogin"], errors="raise"
    ).astype("datetime64[ns]")

    return df

def _save_usuarios(df: pd.DataFrame):
    df.to_parquet(USUARIOS_FILE, index=False)


def _registrar_historico(cod: str, nome: str, role: str, action: str):
    novo = pd.DataFrame([{
        "CodVendedor": cod,
        "NomeVendedor": nome,
        "Role": role,
        "Action": action,
        "Timestamp": datetime.now(),
    }])
    if HISTORICO_FILE.exists():
        hist = pd.concat([pd.read_parquet(HISTORICO_FILE), novo], ignore_index=True)
    else:
        hist = novo
    hist.to_parquet(HISTORICO_FILE, index=False)


# ============================================================================
# SENHA
# ============================================================================

def _hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()


def _checar_senha(senha: str, hash_str: str) -> bool:
    try:
        return bcrypt.checkpw(senha.encode(), hash_str.encode())
    except Exception:
        return False


def _senha_provisoria(cod: str) -> str:
    return f"gm@{cod}"


def _validar_nova_senha(nova: str, confirma: str, hash_atual: str, cod: str) -> str | None:
    if nova != confirma:
        return "As senhas não coincidem."
    if _checar_senha(nova, hash_atual):
        return "A nova senha não pode ser igual à senha atual."
    if nova == _senha_provisoria(cod):
        return "A nova senha não pode ser igual à senha provisória."
    return None


# ============================================================================
# SESSÃO IN-MEMORY
# ============================================================================

def _expiry_hoje() -> datetime:
    return datetime.combine(date.today(), time(23, 59, 59))


def _iniciar_sessao_state(session_row: pd.Series):
    filtros = []
    last = session_row.get("LastFilters", "")
    if last and isinstance(last, str) and last.strip():
        try:
            filtros = json.loads(last)
        except Exception:
            pass

    st.session_state["auth_user"]          = session_row["CodVendedor"]
    st.session_state["auth_nome"]          = session_row["NomeVendedor"]
    st.session_state["auth_role"]          = session_row["Role"]
    st.session_state["auth_token"]         = session_row["token"]
    st.session_state["auth_expiry"]        = session_row["Expiry"]
    st.session_state["auth_authenticated"] = True
    st.session_state["multiselect_vendedores"] = filtros


def _limpar_sessao():
    preserve = {k: v for k, v in st.session_state.items() if k.startswith("_cm")}
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.session_state.update(preserve)


def _filtros_iniciais(row: pd.Series) -> list:
    if row["Role"] in ROLES_LIVRE:
        last = row.get("LastFilters", None)
        if last and isinstance(last, str) and last.strip():
            try:
                return json.loads(last)
            except Exception:
                pass
        return []
    return [row["CodVendedor"]]


# ============================================================================
# CSS
# ============================================================================

_LOGIN_CSS = """
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .login-title { font-size: 1.4rem; font-weight: 700; color: #1B3A5C;
                   text-align: center; margin-bottom: 4px; }
    .login-sub { font-size: 0.82rem; color: #95A5A6; text-align: center;
                 margin-bottom: 24px; }
    [data-testid="stTextInput"] input {
        border: 1.5px solid #2E6BA6 !important;
        border-radius: 6px !important;
        padding: 8px 12px !important;
    }
    [data-testid="stTextInput"] input:focus {
        border-color: #1B3A5C !important;
        box-shadow: 0 0 0 2px rgba(46,107,166,0.2) !important;
    }
</style>
"""


# ============================================================================
# FORMULÁRIOS
# ============================================================================

def _render_login():
    cm = _cookie_manager()
    st.markdown(_LOGIN_CSS, unsafe_allow_html=True)

    col = st.columns([1, 2, 1])[1]
    with col:
        logo = Path(__file__).parent / "assets" / "logo.jpg"
        if logo.exists():
            st.image(str(logo), width=110)
        st.markdown('<div class="login-title">GM Limpeza — Radar de Risco</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-sub">Digite suas credenciais para acessar</div>', unsafe_allow_html=True)

        with st.form("form_login"):
            cod   = st.text_input("Usuário", placeholder="Código do vendedor")
            senha = st.text_input("Senha", type="password")
            submit = st.form_submit_button("Entrar", use_container_width=True)

        if submit:
            _processar_login(cod.strip(), senha, cm)

    st.stop()


def _buscar_usuario(df: pd.DataFrame, cod: str) -> pd.DataFrame:
    """Aceita código exato ('00026') ou numérico sem zeros ('26')."""
    linha = df[df["CodVendedor"] == cod]
    if not linha.empty:
        return linha
    if cod.isdigit():
        val = int(cod)
        mask = df["CodVendedor"].apply(lambda x: x.isdigit() and int(x) == val)
        return df[mask]
    return pd.DataFrame()


def _processar_login(cod: str, senha: str, cm):
    if not cod or not senha:
        st.error("Preencha usuário e senha.")
        return

    df = _load_usuarios()
    linha = _buscar_usuario(df, cod)

    if linha.empty:
        _registrar_historico(cod, "", "", "login_failed")
        st.error("Usuário ou senha incorretos.")
        return

    row = linha.iloc[0]

    if not row["Active"]:
        st.error("Conta inativa. Entre em contato com o administrador.")
        return

    if not _checar_senha(senha, row["PasswordHash"]):
        _registrar_historico(cod, row["NomeVendedor"], row["Role"], "login_failed")
        st.error("Usuário ou senha incorretos.")
        return

    df.loc[df["CodVendedor"] == cod, "LastLogin"] = datetime.now()
    _save_usuarios(df)

    if row["FirstLogin"] or row["ResetRequired"]:
        st.session_state["auth_pending_user"]   = row["CodVendedor"]  # usa o código canônico do banco, não o input
        st.session_state["auth_pending_nome"]   = row["NomeVendedor"]
        st.session_state["auth_pending_role"]   = row["Role"]
        st.session_state["auth_pending_hash"]   = row["PasswordHash"]
        st.session_state["auth_pending_reason"] = "first" if row["FirstLogin"] else "reset"
        _registrar_historico(cod, row["NomeVendedor"], row["Role"], "login_pending_password_change")
        st.rerun()

    filtros = _filtros_iniciais(row)
    token   = _criar_session_token(row, filtros)
    cm.set(SESSION_COOKIE, token, expires_at=_expiry_hoje())

    session_row = pd.Series({
        "token": token, "CodVendedor": row["CodVendedor"],
        "NomeVendedor": row["NomeVendedor"], "Role": row["Role"],
        "Expiry": _expiry_hoje(), "LastFilters": json.dumps(filtros),
    })
    _iniciar_sessao_state(session_row)
    _registrar_historico(cod, row["NomeVendedor"], row["Role"], "login_success")
    st.rerun()


def _render_troca_senha():
    cod      = st.session_state.get("auth_pending_user", "")
    nome     = st.session_state.get("auth_pending_nome", "")
    role     = st.session_state.get("auth_pending_role", "")
    hash_atual = st.session_state.get("auth_pending_hash", "")
    reason   = st.session_state.get("auth_pending_reason", "first")

    cm = _cookie_manager()
    st.markdown(_LOGIN_CSS, unsafe_allow_html=True)

    col = st.columns([1, 2, 1])[1]
    with col:
        if reason == "first":
            st.markdown('<div class="login-title">Primeiro Acesso</div>', unsafe_allow_html=True)
            st.markdown('<div class="login-sub">Crie sua senha pessoal para ativar a conta.</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="login-title">Redefinição de Senha</div>', unsafe_allow_html=True)
            st.markdown('<div class="login-sub">Sua senha foi redefinida pelo administrador. Crie uma nova senha.</div>', unsafe_allow_html=True)

        with st.form("form_troca_senha"):
            nova     = st.text_input("Nova senha", type="password")
            confirma = st.text_input("Confirme a nova senha", type="password")
            submit   = st.form_submit_button("Confirmar", use_container_width=True)

        if submit:
            erro = _validar_nova_senha(nova, confirma, hash_atual, cod)
            if erro:
                st.error(erro)
            else:
                df = _load_usuarios()
                df.loc[df["CodVendedor"] == cod, "PasswordHash"]   = _hash_senha(nova)
                df.loc[df["CodVendedor"] == cod, "FirstLogin"]     = False
                df.loc[df["CodVendedor"] == cod, "ResetRequired"]  = False
                _save_usuarios(df)

                for k in ["auth_pending_user", "auth_pending_nome", "auth_pending_role",
                           "auth_pending_hash", "auth_pending_reason"]:
                    st.session_state.pop(k, None)

                row     = _buscar_usuario(df, cod).iloc[0]
                filtros = _filtros_iniciais(row)
                token   = _criar_session_token(row, filtros)
                cm.set(SESSION_COOKIE, token, expires_at=_expiry_hoje())

                session_row = pd.Series({
                    "token": token, "CodVendedor": row["CodVendedor"],
                    "NomeVendedor": row["NomeVendedor"], "Role": row["Role"],
                    "Expiry": _expiry_hoje(), "LastFilters": json.dumps(filtros),
                })
                _iniciar_sessao_state(session_row)
                _registrar_historico(cod, nome, role, "password_changed")
                st.rerun()

    st.stop()


# ============================================================================
# GATE PRINCIPAL
# ============================================================================

def check_session() -> dict:
    """
    Chama no topo do radar_vendedor.py (após set_page_config).
    Tenta restaurar sessão via cookie antes de exibir login.
    """
    cm = _cookie_manager()

    # Troca de senha pendente
    if st.session_state.get("auth_pending_user"):
        _render_troca_senha()

    # Sessão já ativa em memória
    if st.session_state.get("auth_authenticated"):
        expiry = st.session_state.get("auth_expiry")
        if expiry and datetime.now() <= expiry:
            return {
                "cod":   st.session_state["auth_user"],
                "nome":  st.session_state["auth_nome"],
                "role":  st.session_state["auth_role"],
                "token": st.session_state["auth_token"],
            }
        # Expirou
        token = st.session_state.get("auth_token", "")
        _registrar_historico(
            st.session_state.get("auth_user", ""),
            st.session_state.get("auth_nome", ""),
            st.session_state.get("auth_role", ""),
            "session_expired",
        )
        if token:
            _remover_session(token)
            cm.delete(SESSION_COOKIE)
        _limpar_sessao()

    # Tentar restaurar via cookie
    token = cm.get(SESSION_COOKIE)
    if token:
        session_row = _buscar_session(token)
        if session_row is not None:
            _iniciar_sessao_state(session_row)
            return {
                "cod":   session_row["CodVendedor"],
                "nome":  session_row["NomeVendedor"],
                "role":  session_row["Role"],
                "token": token,
            }
        # Cookie inválido/expirado — limpar
        cm.delete(SESSION_COOKIE)

    _render_login()


def salvar_filtros_usuario(cod: str, filtros: list, token: str = ""):
    """Persiste a última seleção de filtros para roles dev/gestao."""
    df = _load_usuarios()
    mask = df["CodVendedor"] == cod
    if not mask.any():
        return
    role = df.loc[mask, "Role"].iloc[0]
    if role in ROLES_LIVRE:
        df.loc[mask, "LastFilters"] = json.dumps(filtros)
        _save_usuarios(df)
        if token:
            _atualizar_last_filters_session(token, filtros)


def render_logout_sidebar(user: dict):
    """Renderiza botão de logout na sidebar."""
    cm = _cookie_manager()
    st.sidebar.markdown("---")
    st.sidebar.caption(f"Logado como **{user['nome']}**")
    if st.sidebar.button("Sair", use_container_width=True):
        _registrar_historico(user["cod"], user["nome"], user["role"], "logout")
        token = user.get("token", "")
        if token:
            _remover_session(token)
            cm.delete(SESSION_COOKIE)
        _limpar_sessao()
        st.rerun()
