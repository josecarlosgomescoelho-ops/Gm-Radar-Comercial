"""Radar Comercial: interface aprovada integrada ao Streamlit, sem dados fictícios."""
import base64
import logging
from pathlib import Path
import re
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / '.env')
st.set_page_config(page_title='Radar Comercial — GM Limpezas',page_icon='🎯',layout='wide',initial_sidebar_state='collapsed')
from auth import check_session, render_logout_sidebar, _load_usuarios
from radar_dados import ler_responsaveis
from radar_cache_local import carregar_local, disponivel_local, CHAVE
from radar_metas import salvar_meta, GESTAO, SUPERVISAO
from radar_pdf import selecionar_pendentes, gerar_pdf
import radar_validado

st.markdown('''<style>
header[data-testid="stHeader"]{height:0 !important;min-height:0 !important;background:transparent !important;}
.block-container,[data-testid="stMainBlockContainer"]{padding-top:0 !important;padding-bottom:1rem !important;padding-left:.35rem !important;padding-right:.35rem !important;max-width:100%;}
[data-testid="stSidebarCollapsedControl"]{top:6px;left:6px;z-index:999;}
div[data-testid="stElementContainer"]:has(iframe[title*="cookie_manager"]),div.element-container:has(iframe[title*="cookie_manager"]){display:none !important;}
div[data-testid="stElementContainer"]:has(iframe[title*="CookieManager"]),div.element-container:has(iframe[title*="CookieManager"]){display:none !important;}
footer{visibility:hidden;}
.radar-loading{font-family:Arial,sans-serif;background:#f3f6fa;padding:24px;color:#1b3a5c;}
.radar-loading-card{padding:32px;border:1px dashed #c4d9ec;border-radius:16px;background:white;text-align:center;}
.radar-skeleton{height:110px;margin-top:14px;border-radius:12px;background:linear-gradient(90deg,#e2e8f0 25%,#f1f5f9 50%,#e2e8f0 75%);background-size:200% 100%;animation:radarPulse 1.4s infinite;}
@keyframes radarPulse{0%{background-position:200% 0}100%{background-position:-200% 0}}
@media(prefers-reduced-motion:reduce){.radar-skeleton{animation:none;}}
</style>''',unsafe_allow_html=True)
usuario = check_session()
# Revalidate active account and current role on every rerun, including writes.
usuarios = _load_usuarios()
linhas = usuarios.loc[usuarios.CodVendedor.astype('string').str.strip().eq(str(usuario['cod']).strip())]
if len(linhas)!=1 or not bool(linhas.iloc[0].Active) or bool(linhas.iloc[0].ResetRequired) or bool(linhas.iloc[0].FirstLogin):
    st.error('Seu acesso precisa ser revalidado. Saia e entre novamente ou contate a gestão.')
    render_logout_sidebar(usuario)
    st.stop()
usuario=dict(usuario,role=str(linhas.iloc[0].Role).strip().lower(),nome=str(linhas.iloc[0].NomeVendedor))
render_logout_sidebar(usuario)
with st.sidebar:
    st.caption('Radar Comercial • versão enxuta 19/10/2026')
    if st.button('Reler arquivos locais'):
        st.session_state.pop(CHAVE, None)
        st.rerun()

carregando=st.empty()
if not disponivel_local(usuario, ROOT/'cache', st.session_state):
    carregando.markdown('''<section class="radar-loading"><div class="radar-loading-card" role="status" aria-live="polite"><h3>Carregando informações comerciais...</h3><p>Aguarde enquanto preparamos os indicadores da carteira e das metas do mês.</p><div class="radar-skeleton"></div><div class="radar-skeleton"></div></div></section>''',unsafe_allow_html=True)
try:
    payload,responsaveis,financeiro=carregar_local(usuario,ROOT/'cache',st.session_state)
except Exception as e:
    carregando.empty()
    logging.exception('Falha ao carregar o Radar')
    st.error('Não foi possível carregar a base da nova interface.')
    if isinstance(e,(ValueError,FileNotFoundError,PermissionError)):
        st.info(str(e))
    st.caption('Extrações pausadas. Confira os arquivos locais; esta tela não consulta o Cronos.')
    st.stop()

logo=ROOT/'dashboards/assets/logo.jpg'
if logo.exists():
    payload['logo']='data:image/jpeg;base64,'+base64.b64encode(logo.read_bytes()).decode('ascii')

interface=components.declare_component('gm_radar_comercial',path=str(ROOT/'dashboards/radar_component'))
carregando.empty()
feedback_key='radar_feedback_'+str(usuario['cod'])
pdf_key='radar_pdf_'+str(usuario['cod'])
base_atual=st.session_state.get(CHAVE, (None,))[0]
pdf_salvo=st.session_state.get(pdf_key)
arquivo_pdf=pdf_salvo['arquivo'] if pdf_salvo and pdf_salvo['base']==base_atual and base_atual is not None else None
event=interface(payload=payload,feedback=st.session_state.get(feedback_key),arquivoPdf=arquivo_pdf,key='radar_interface_'+str(usuario['cod']),default=None)
if isinstance(event,dict) and event.get('id')!=st.session_state.get('radar_ultimo_evento'):
    st.session_state['radar_ultimo_evento']=event.get('id')
    try:
        if not isinstance(event.get('id'), str) or not re.fullmatch(r'[A-Za-z0-9_-]{16,80}',event['id']):
            raise ValueError('Identificador da ação inválido.')
        if event.get('tipo')=='pdf_pendentes':
            itens,nomes,curva=selecionar_pendentes(payload,usuario,ler_responsaveis(ROOT/'cache'),event)
            dados_pdf=gerar_pdf(payload,itens,nomes,curva)
            st.session_state[pdf_key]={'base':base_atual, 'arquivo':{'id':event['id'],'nome':'clientes_pendentes_'+curva+'_'+payload['competencia']+'.pdf','base64':base64.b64encode(dados_pdf).decode('ascii')}}
            st.session_state[feedback_key]={'tipo':'ok','texto':f'PDF preparado: {len(itens)} clientes pendentes. Se o download não iniciar, use o link acima.'}
        elif event.get('tipo')=='salvar_meta':
            message=salvar_meta(usuario,ler_responsaveis(ROOT/'cache'),event)
            st.session_state.pop(CHAVE, None)
            st.session_state[feedback_key]={'tipo':'ok','texto':message}
        else:
            raise ValueError('Ação não reconhecida.')
    except (ValueError,PermissionError) as e:
        st.session_state[feedback_key]={'tipo':'err','texto':str(e)}
    except Exception:
        logging.exception('Falha ao processar ação do Radar')
        st.session_state[feedback_key]={'tipo':'err','texto':'Não foi possível concluir. Confira o armazenamento local e tente novamente.'}
    st.rerun()

# Keep the exact four-decimal report available to management, outside the component.
if str(usuario['role']).lower() in GESTAO and financeiro is not None:
    with st.expander('Conferência com o Cronos — relatório completo'):
        linhas=financeiro.loc[financeiro.LinhaFinanceira].copy()
        export=radar_validado._exportar_financeiro_cronos(linhas)
        st.caption('Valores preservados com quatro casas decimais. Quantidade usa DtMov; receita usa DataFaturamento, conforme o relatório Cronos.')
        st.dataframe(export,use_container_width=True,hide_index=True)
        st.download_button('Baixar conferência CSV',export.to_csv(index=False,sep=';').encode('utf-8-sig'),'conferencia_cronos.csv','text/csv')
