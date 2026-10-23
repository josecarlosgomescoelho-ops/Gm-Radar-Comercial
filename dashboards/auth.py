"""
GM Limpeza — Módulo de Autenticação
Sessao persistida via cookie e SQLite local, com transacoes por operacao.
"""

import json
import logging
import sqlite3
import threading
import bcrypt
import pandas as pd
import streamlit as st
import extra_streamlit_components as stx
from datetime import date, datetime, time
from pathlib import Path
from radar_auth_store import AuthStore, AuthError, AuthConflict, SP
from radar_instalacao import informacao_instalacao, legenda_instalacao

CACHE_DIR = Path(__file__).parent.parent / "cache"
USUARIOS_FILE  = CACHE_DIR / "usuarios.parquet"
HISTORICO_FILE = CACHE_DIR / "login_historico.parquet"
SESSIONS_FILE  = CACHE_DIR / "sessions.parquet"

SESSION_COOKIE = "gm_radar_token_"+informacao_instalacao()['base']
ROLES_LIVRE = {"dev", "gestao"}


# ============================================================================
# COOKIE MANAGER
# ============================================================================

def _cookie_manager():
    if "_cm" not in st.session_state:
        st.session_state["_cm"] = stx.CookieManager(key="gm_auth_cookies_"+informacao_instalacao()['base']+'_'+str(st.session_state.get('auth_cookie_epoch',0)))
    return st.session_state["_cm"]


def _apagar_cookie(cm):
    try:
        cm.delete(SESSION_COOKIE,key='gm_auth_delete_'+informacao_instalacao()['base'])
    except KeyError:
        # O navegador pode ja ter expirado/apagado o cookie. A sessao e validada no banco.
        pass


# ============================================================================
# SESSOES TRANSACIONAIS
# ============================================================================

def _load_sessions() -> pd.DataFrame:
    """Consulta administrativa: tokens sao armazenados somente como hash."""
    with _store().connect() as conn:
        return pd.read_sql_query("SELECT TokenHash,CodVendedor,Expiry,LastFilters FROM auth_sessions",conn)


def _save_sessions(df: pd.DataFrame):
    raise AuthError("Regravacao integral de sessoes desativada. Use as operacoes transacionais.")


def _criar_session_token(row: pd.Series, filtros: list) -> str:
    return _store().create_session(row, filtros, _expiry_hoje())


def _buscar_session(token: str) -> pd.Series | None:
    return _store().get_session(token)


def _remover_session(token: str):
    _store().remove_session(token)


def _atualizar_last_filters_session(token: str, filtros: list):
    sessao = _buscar_session(token)
    if sessao is not None:
        _store().save_filters(sessao["CodVendedor"], filtros, token)


# ============================================================================
# PERSISTÊNCIA DE USUÁRIOS
# ============================================================================

def _load_usuarios() -> pd.DataFrame:
    return _store().users()

def _save_usuarios(df: pd.DataFrame):
    # Compatibilidade: a versao de cada conta impede sobrescrever uma leitura antiga.
    _store().save_snapshot(df)


def _registrar_historico(cod: str, nome: str, role: str, action: str):
    _store().history(cod, nome, role, action)


# ============================================================================
# SENHA
# ============================================================================

def _hash_senha(senha: str) -> str:
    if not senha or len(senha.encode('utf-8')) > 72:
        raise ValueError("A senha deve conter de 1 a 72 bytes em UTF-8.")
    return bcrypt.hashpw(senha.encode('utf-8'), bcrypt.gensalt()).decode()


def _checar_senha(senha: str, hash_str: str) -> bool:
    try:
        return bcrypt.checkpw(senha.encode(), hash_str.encode())
    except Exception:
        return False


def _senha_provisoria(cod: str) -> str:
    return f"gm@{cod}"


def _validar_nova_senha(nova: str, confirma: str, hash_atual: str, cod: str) -> str | None:
    if not nova or len(nova.encode("utf-8")) > 72:
        return "A senha deve conter de 1 a 72 bytes em UTF-8."
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
    return datetime.combine(datetime.now(SP).date(), time(23, 59, 59), tzinfo=SP)


def _iniciar_sessao_state(session_row: pd.Series):
    filtros = []
    last = session_row.get("LastFilters", "")
    if last and isinstance(last, str) and last.strip():
        try:
            filtros = json.loads(last)
        except Exception:
            pass

    # Token validado primeiro: um rerun intermediario pode retomar a sessao pelo banco.
    st.session_state["auth_token"]         = session_row["token"]
    st.session_state["auth_user"]          = session_row["CodVendedor"]
    st.session_state["auth_nome"]          = session_row["NomeVendedor"]
    st.session_state["auth_role"]          = session_row["Role"]
    st.session_state["auth_expiry"]        = session_row["Expiry"]
    st.session_state["auth_authenticated"] = True
    st.session_state["multiselect_vendedores"] = filtros


def _limpar_sessao():
    epoca=int(st.session_state.get('auth_cookie_epoch',0))+1
    st.session_state['auth_cookie_epoch']=epoca
    for k in list(st.session_state.keys()):
        if k!='auth_cookie_epoch':del st.session_state[k]
    # A ponte de cookie precisa montar novamente depois de limpar os widgets.
    # Reusar a mesma chave com valor apagado pode manter a tela esperando para sempre.


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
        st.markdown('<div class="login-title">GM Limpezas — Radar Comercial</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-sub">Digite suas credenciais para acessar</div>', unsafe_allow_html=True)
        st.caption(legenda_instalacao())
        st.caption('Use o mesmo endereço em que a conta foi criada ou a senha foi redefinida. Notebook e VPS têm bases separadas.')

        with st.form("form_login"):
            st.text_input("Usuário", placeholder="Código do vendedor",key="auth_login_codigo")
            st.text_input("Senha",type="password",key="auth_login_senha")
            st.form_submit_button("Entrar",use_container_width=True,on_click=_solicitar_login)
        resultado=_fluxo_auth().get('resultado',{})
        if resultado.get('formulario')=='login' and resultado.get('erro'):
            st.error(resultado['erro'])

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


def _fluxo_auth():
    if '_auth_fluxo' not in st.session_state:
        st.session_state['_auth_fluxo']={'lock':threading.Lock()}
    return st.session_state['_auth_fluxo']


def _solicitar_login():
    # O callback captura apenas a solicitacao. O resultado fica no mesmo objeto
    # durante a verificacao, sem pontos de rerun entre o commit e o registro do token.
    fluxo=_fluxo_auth()
    pedido=dict(tipo='login',cod=str(st.session_state.get('auth_login_codigo','')).strip(),
                senha=st.session_state.get('auth_login_senha',''))
    with fluxo['lock']:
        fluxo.update(pedido=pedido,resultado={})


def _solicitar_troca_senha():
    fluxo=_fluxo_auth()
    pedido=dict(tipo='troca',cod=st.session_state.get('auth_pending_user',''),
        hash_atual=st.session_state.get('auth_pending_hash',''),
        versao=st.session_state.get('auth_pending_security'),
        nova=st.session_state.get('auth_nova_senha',''),
        confirma=st.session_state.get('auth_confirma_senha',''))
    with fluxo['lock']:
        fluxo.update(pedido=pedido,resultado={})


def _resultado_sessao(row):
    token=_criar_session_token(row,_filtros_iniciais(row))
    return dict(tipo='sessao',token=token)


def _autenticar_pedido(pedido):
    # Somente codigo Python/SQLite: nao renderizar widgets nem escrever em
    # st.session_state aqui. Um evento de cookie nao pode perder o resultado.
    cod=pedido.get('cod','')
    if pedido['tipo']=='login':
        senha=pedido.get('senha','')
        if not cod or not senha or len(cod)>64:
            return dict(erro='Preencha usuario e senha validos.')
        linha=_buscar_usuario(_load_usuarios(),cod)
        if len(linha)!=1:
            _registrar_historico(cod,'','','login_failed')
            return dict(erro='Usuario ou senha incorretos nesta instalacao.')
        row=linha.iloc[0]
        if not row['Active']:
            return dict(erro='Conta inativa. Entre em contato com o administrador.')
        if not _checar_senha(senha,row['PasswordHash']):
            _registrar_historico(row['CodVendedor'],row['NomeVendedor'],row['Role'],'login_failed')
            return dict(erro='Usuario ou senha incorretos nesta instalacao.')
        if row['FirstLogin'] or row['ResetRequired']:
            _store().login_pending(row)
            return dict(tipo='troca',row=row.to_dict())
        return _resultado_sessao(row)
    if pedido['tipo']=='troca':
        erro=_validar_nova_senha(pedido['nova'],pedido['confirma'],pedido['hash_atual'],cod)
        if erro:return dict(erro=erro)
        atual=_store().find_user(cod)
        if atual is None or pedido.get('versao') is None:
            return dict(erro='Entre novamente antes de alterar a senha.')
        esperado=atual.copy()
        esperado['PasswordHash']=pedido['hash_atual']
        esperado['_AuthVersion']=pedido['versao']
        row=_store().change_password(esperado,_hash_senha(pedido['nova']))
        return _resultado_sessao(row)
    raise ValueError('Operacao de autenticacao invalida.')


def _retomar_operacao_auth():
    fluxo=_fluxo_auth()
    with fluxo['lock']:
        pedido=fluxo.get('pedido')
        if pedido:
            formulario='login' if pedido['tipo']=='login' else 'troca'
            try:
                resultado=_autenticar_pedido(pedido)
            except (AuthError,sqlite3.Error,OSError,ValueError):
                logging.exception('Falha na operacao de autenticacao local')
                resultado=dict(erro='Nao foi possivel concluir. Confira o armazenamento local e entre novamente.')
            resultado['formulario']=formulario
            # Atualizacao sem widgets; o lock tambem cobre execucoes antigas ainda
            # terminando durante um fast rerun do Streamlit.
            fluxo.update(pedido=None,resultado=resultado)
            pedido.clear()
    resultado=fluxo.get('resultado',{})
    if resultado.get('tipo')=='sessao':
        token=resultado['token']
        row=_buscar_session(token)
        if row is None:
            fluxo['resultado']=dict(formulario='login',erro='Sua conta mudou. Entre novamente.')
            return
        _iniciar_sessao_state(row)
        for chave in list(st.session_state):
            if chave.startswith('auth_pending_'):st.session_state.pop(chave,None)
        fluxo.update(pedido=None,resultado={})
        st.rerun()
    if resultado.get('tipo')=='troca':
        row=resultado['row']
        campos=dict(auth_pending_user=row['CodVendedor'],auth_pending_nome=row['NomeVendedor'],
            auth_pending_role=row['Role'],auth_pending_hash=row['PasswordHash'],
            auth_pending_security=int(row['_AuthVersion']),
            auth_pending_reason='first' if row['FirstLogin'] else 'reset')
        for chave,valor in campos.items():st.session_state[chave]=valor
        fluxo.update(pedido=None,resultado={})
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
        st.caption(legenda_instalacao())
        if reason == "first":
            st.markdown('<div class="login-title">Primeiro Acesso</div>', unsafe_allow_html=True)
            st.markdown('<div class="login-sub">Crie sua senha pessoal para ativar a conta.</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="login-title">Redefinição de Senha</div>', unsafe_allow_html=True)
            st.markdown('<div class="login-sub">Sua senha foi redefinida pelo administrador. Crie uma nova senha.</div>', unsafe_allow_html=True)

        with st.form("form_troca_senha"):
            st.text_input("Nova senha",type="password",key="auth_nova_senha")
            st.text_input("Confirme a nova senha",type="password",key="auth_confirma_senha")
            st.form_submit_button("Confirmar",use_container_width=True,on_click=_solicitar_troca_senha)
        resultado=_fluxo_auth().get('resultado',{})
        if resultado.get('formulario')=='troca' and resultado.get('erro'):
            st.error(resultado['erro'])

        if st.button('Voltar ao login', key='radar_cancelar_troca'):
            _limpar_sessao()
            st.rerun()

    st.stop()


# ============================================================================
# GATE PRINCIPAL
# ============================================================================

def check_session() -> dict:
    """Valida a sessao persistida a cada rerun, inclusive revogacoes administrativas."""
    try:
        _retomar_operacao_auth()
        cm=_cookie_manager()
        cookies=cm.cookie_manager(method='getAll',key='gm_auth_read_'+informacao_instalacao()['base']+'_'+str(st.session_state.get('auth_cookie_epoch',0)),default=None)
        if not isinstance(cookies,dict):
            st.caption('Preparando acesso ao Radar...')
            st.stop()
        cm.cookies=cookies
        return _check_session_persistida()
    except (AuthError, sqlite3.Error, OSError):
        logging.exception("Falha no armazenamento local da autenticacao")
        _limpar_sessao()
        st.error("Nao foi possivel validar seu acesso no armazenamento local.")
        st.caption("Confira a migracao e a disponibilidade do arquivo de autenticacao. Nenhuma conta nova foi criada automaticamente.")
        st.stop()


def salvar_filtros_usuario(cod: str, filtros: list, token: str = ""):
    _store().save_filters(cod, filtros, token)


def render_logout_sidebar(user: dict):
    cm = _cookie_manager()
    st.sidebar.markdown("---")
    st.sidebar.caption(f"Logado como **{user['nome']}**")
    if st.sidebar.button("Sair", use_container_width=True):
        try:
            encerrar_sessao(user)
        except (AuthError, sqlite3.Error, OSError):
            logging.exception("Falha ao encerrar sessao persistida")
            st.sidebar.error("Nao foi possivel encerrar a sessao. Tente novamente.")
            st.stop()


def encerrar_sessao(user):
    token=user.get('token','')
    if token:_remover_session(token)
    # Revogar no servidor e renovar a ponte antes de renderizar outro componente.
    # O cookie revogado sera removido na proxima execucao completa do login.
    _limpar_sessao()
    st.rerun()


def _store():
    return AuthStore()


def _check_session_persistida():
    cm = _cookie_manager()
    if st.session_state.get("auth_pending_user"):
        _render_troca_senha()
    if st.session_state.get("auth_authenticated") or st.session_state.get('auth_token'):
        token = st.session_state.get("auth_token", "")
        row = _buscar_session(token)
        if row is not None:
            if not st.session_state.get('auth_authenticated'):
                _iniciar_sessao_state(row)
            # A escrita iniciada antes de st.rerun pode nao ter chegado ao navegador.
            # Renderize a operacao novamente numa execucao completa, sem forcar rerun aqui.
            if cm.get(SESSION_COOKIE)!=token:
                try:cm.set(SESSION_COOKIE,token,expires_at=row['Expiry'],key='gm_auth_set_'+informacao_instalacao()['base'])
                except Exception:logging.warning('Cookie indisponivel; acesso mantido apenas na aba autenticada.')
            # Do not reset filter widgets when only refreshing the authorization.
            st.session_state["auth_nome"] = row["NomeVendedor"]
            st.session_state["auth_role"] = row["Role"]
            st.session_state["auth_expiry"] = row["Expiry"]
            return {"cod":row["CodVendedor"],"nome":row["NomeVendedor"],"role":row["Role"],"token":token}
        _limpar_sessao()
        st.rerun()
    token = cm.get(SESSION_COOKIE)
    if token:
        row = _buscar_session(token)
        if row is not None:
            _iniciar_sessao_state(row)
            return {"cod":row["CodVendedor"],"nome":row["NomeVendedor"],"role":row["Role"],"token":token}
        _apagar_cookie(cm)
    _render_login()
