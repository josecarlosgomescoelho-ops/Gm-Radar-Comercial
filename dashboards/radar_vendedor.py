"""Radar Comercial: interface aprovada integrada ao Streamlit, sem dados fictícios."""
import base64
import hashlib
import json
import logging
from pathlib import Path
import re
import sqlite3
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / '.env')
st.set_page_config(page_title='Radar Comercial — GM Limpezas',page_icon='🎯',layout='wide',initial_sidebar_state='collapsed')
from auth import check_session, render_logout_sidebar, _load_usuarios, encerrar_sessao
from radar_dados import ler_responsaveis
from radar_cache_local import carregar_local, disponivel_local, limpar_preparacao, CHAVE
from radar_metas import salvar_meta, GESTAO, SUPERVISAO
from radar_pdf import selecionar_pendentes, gerar_pdf
from radar_equipe import candidatos, ler_equipe, salvar_equipe
from radar_acessos import carregar_acessos, processar_acesso, carregar_equipe_gestao, processar_equipe_gestao
from radar_ordem import ordenar_dataframe
from radar_instalacao import informacao_instalacao, legenda_instalacao
import radar_validado

st.markdown('''<style>
header[data-testid="stHeader"]{display:none !important;height:0 !important;min-height:0 !important;background:transparent !important;}
.block-container,[data-testid="stMainBlockContainer"]{padding-top:0 !important;padding-bottom:1rem !important;padding-left:.35rem !important;padding-right:.35rem !important;max-width:100%;}
[data-testid="stSidebarCollapsedControl"]{top:6px;left:6px;z-index:999;}
div[data-testid="stElementContainer"]:has(iframe[title*="cookie_manager"]),div.element-container:has(iframe[title*="cookie_manager"]){display:none !important;}
div[data-testid="stElementContainer"]:has(iframe[title*="CookieManager"]),div.element-container:has(iframe[title*="CookieManager"]){display:none !important;}
footer{visibility:hidden;}
[data-testid="stToolbar"]{display:none;}
[data-testid="stElementContainer"]:has(style),[data-testid="stElementContainer"]:has([data-testid="stEmpty"]){display:none;}
[data-testid="stAppViewContainer"],.stApp{background:#f3f6fa;color:#18344f;}
[data-testid="stMainBlockContainer"]{gap:.3rem;}
[data-testid="stExpander"]{background:white;color:#18344f;border-color:#dce4ee;}
[data-testid="stForm"]{background:#fff;color:#18344f;border:1px solid #dce4ee;border-radius:12px;padding:24px;}
[data-testid="stForm"] label,[data-testid="stForm"] p,[data-testid="stExpander"] summary p{color:#18344f;}

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
    st.caption(legenda_instalacao())
    if st.button('Reler arquivos locais'):
        from radar_leitura import limpar_leitura
        limpar_leitura()
        limpar_preparacao()
        st.session_state.pop(CHAVE, None)
        st.session_state.pop('radar_base_enviada_'+str(usuario['cod']),None)
        st.rerun()
    if str(usuario['role']).lower() in GESTAO:
        with st.expander('Equipe comercial do Radar'):
            st.caption('Todos os nomes da base local ficam disponíveis. A gestão escolhe quem participa do Radar, inclusive pessoas sem supervisor.')
            try:
                catalogo=ler_responsaveis(ROOT/'cache', equipe_atual=False)
                pessoas=candidatos(catalogo)
                nomes={r.CodVendedor:f'{r.Vendedor} ({r.CodVendedor})' for r in pessoas.itertuples()}
                config=ler_equipe()
                versao=config['versao'] if config else 0
                marcados=set(config['codigos'] if config else nomes)
                atuais=[c for c in nomes if c in marcados]
                if 'radar_equipe_mensagem' in st.session_state:
                    st.success(st.session_state.pop('radar_equipe_mensagem'))
                with st.form('radar_equipe_form_'+str(versao)):
                    selecionadas=st.multiselect('Participantes da equipe atual', list(nomes), default=atuais,
                        format_func=lambda c:nomes[c], key='radar_equipe_selecao_'+str(versao))
                    aplicar=st.form_submit_button('Salvar equipe')
                st.caption('Esta seleção vale para todas as sessões do Radar. O cadastro do Cronos e o relatório financeiro completo são preservados.')
                if aplicar:
                    st.session_state['radar_equipe_mensagem']=salvar_equipe(usuario,catalogo,selecionadas,versao)
                    st.session_state.pop(CHAVE,None)
                    st.rerun()
            except (ValueError, PermissionError, OSError, sqlite3.DatabaseError) as exc:
                st.error(str(exc))

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
    st.caption('Confira os arquivos locais; esta tela não consulta o Cronos.')
    st.stop()

payload=dict(payload,instalacao=informacao_instalacao())
if str(usuario['role']).lower() in GESTAO:
    payload=dict(payload)
    try:
        catalogo_completo=ler_responsaveis(ROOT/'cache',equipe_atual=False)
        payload['acessos']=carregar_acessos(usuario,catalogo_completo)
        payload['equipe']=carregar_equipe_gestao(usuario,catalogo_completo)
    except (ValueError,PermissionError,OSError,sqlite3.Error):
        logging.exception('Falha ao carregar a gestao local de acessos')
        payload['acessos']={'contas':[],'catalogo':[], 'erro':'Não foi possível ler os acessos. Confira o armazenamento local e entre novamente.'}

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
# Envia a carteira completa uma vez por versão. Respostas de PDF/acessos são pequenas.
# O iframe pode pedir novamente a base se for remontado sem uma nova sessão Python.
revisao=hashlib.sha256(json.dumps(base_atual,ensure_ascii=True,default=str).encode()).hexdigest()
enviado_key='radar_base_enviada_'+str(usuario['cod'])
enviar_base=st.session_state.get(enviado_key)!=revisao
atualizacoes={k:payload[k] for k in ('acessos','equipe','instalacao') if k in payload}
st.session_state[enviado_key]=revisao
event=interface(payload=payload if enviar_base else None,revisao=revisao,atualizacoes=atualizacoes,
    feedback=st.session_state.get(feedback_key),arquivoPdf=arquivo_pdf,key='radar_interface_'+str(usuario['cod']),default=None)
if isinstance(event,dict) and event.get('tipo')!='confirmar_acesso' and event.get('id')!=st.session_state.get('radar_ultimo_evento'):
    st.session_state['radar_ultimo_evento']=event.get('id')
    try:
        if not isinstance(event.get('id'), str) or not re.fullmatch(r'[A-Za-z0-9_-]{16,80}',event['id']):
            raise ValueError('Identificador da ação inválido.')
        if event.get('tipo')=='solicitar_base':
            st.session_state.pop(enviado_key,None)
        elif event.get('tipo')=='pdf_pendentes':
            itens,nomes,curva=selecionar_pendentes(payload,usuario,ler_responsaveis(ROOT/'cache'),event)
            dados_pdf=gerar_pdf(payload,itens,nomes,curva)
            st.session_state[pdf_key]={'base':base_atual, 'arquivo':{'id':event['id'],'nome':'clientes_pendentes_'+curva+'_'+payload['competencia']+'.pdf','base64':base64.b64encode(dados_pdf).decode('ascii')}}
            st.session_state[feedback_key]={'tipo':'ok','texto':f'PDF preparado: {len(itens)} clientes pendentes. Se o download não iniciar, use o link acima.'}
        elif event.get('tipo')=='sair_radar':
            encerrar_sessao(usuario)
        elif event.get('tipo')=='salvar_meta':
            message=salvar_meta(usuario,ler_responsaveis(ROOT/'cache'),event)
            st.session_state.pop(CHAVE, None)
            st.session_state[feedback_key]={'tipo':'ok','texto':message}
        elif event.get('tipo')=='gerir_acesso':
            message=processar_acesso(usuario,ler_responsaveis(ROOT/'cache',equipe_atual=False),event)
            st.session_state[feedback_key]={'tipo':'ok','texto':message}
        elif event.get('tipo')=='gerir_equipe':
            message=processar_equipe_gestao(usuario,ler_responsaveis(ROOT/'cache',equipe_atual=False),event)
            st.session_state.pop(CHAVE,None)
            st.session_state[feedback_key]={'tipo':'ok','texto':message}
        elif event.get('tipo')=='reler_arquivos':
            from radar_leitura import limpar_leitura
            limpar_leitura()
            limpar_preparacao()
            st.session_state.pop(CHAVE,None)
            st.session_state.pop(enviado_key,None)
            st.session_state.pop(pdf_key,None)
            st.session_state[feedback_key]={'tipo':'ok','texto':'Arquivos locais relidos. Nenhuma consulta ao Cronos foi executada.'}
        elif event.get('tipo')=='reler_acessos':
            carregar_acessos(usuario,ler_responsaveis(ROOT/'cache',equipe_atual=False))
            st.session_state[feedback_key]={'tipo':'ok','texto':'Lista de acessos atualizada.'}
        else:
            raise ValueError('Ação não reconhecida.')
    except (ValueError,PermissionError) as e:
        st.session_state[feedback_key]={'tipo':'err','texto':str(e)}
    except Exception:
        logging.exception('Falha ao processar ação do Radar')
        st.session_state[feedback_key]={'tipo':'err','texto':'Não foi possível concluir. Confira o armazenamento local e tente novamente.'}
    finally:
        # Nao devolva a senha provisoria no payload, no feedback ou nos registros.
        event.pop('senha',None)
        if feedback_key in st.session_state and event.get('tipo')!='solicitar_base':
            st.session_state[feedback_key]['evento']=event.get('id')
            st.session_state[feedback_key]['acao']=event.get('acao',event.get('tipo'))
            st.session_state[feedback_key]['codigo']=event.get('codigo','')
    st.rerun()

# Keep the exact four-decimal report available to management, outside the component.
if str(usuario['role']).lower() in GESTAO and financeiro is not None:
    with st.expander('Conferência com o Cronos — relatório completo'):
        linhas=financeiro.loc[financeiro.LinhaFinanceira].copy()
        export=radar_validado._exportar_financeiro_cronos(linhas)
        if 'NomeVendedor' in export.columns:
            export=ordenar_dataframe(export,'NomeVendedor','CodVendedor')
        st.caption('Valores preservados com quatro casas decimais. Quantidade usa DtMov; receita usa DataFaturamento, conforme o relatório Cronos.')
        st.dataframe(export,use_container_width=True,hide_index=True)
        st.download_button('Baixar conferência CSV',export.to_csv(index=False,sep=';').encode('utf-8-sig'),'conferencia_cronos.csv','text/csv')
