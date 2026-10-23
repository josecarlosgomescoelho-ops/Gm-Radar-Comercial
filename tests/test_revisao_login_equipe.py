"""Regressoes da revisao: equipe manual, instalacoes distintas e recuperacao de acesso."""
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'dashboards'))
from radar_instalacao import informacao_instalacao
from radar_auth_store import AuthConflict
from radar_equipe import filtrar_vinculos
from radar_acessos import carregar_equipe_gestao,processar_equipe_gestao
import test_gestao_acessos_radar as fixture_acessos


class TestRevisaoEquipe(unittest.TestCase):
    setUp=fixture_acessos.TestGestaoAcessos.setUp
    tearDown=fixture_acessos.TestGestaoAcessos.tearDown
    evento=fixture_acessos.TestGestaoAcessos.evento
    executar=fixture_acessos.TestGestaoAcessos.executar
    def test_catalogo_completo_excluir_reincluir_e_todos(self):
        db=Path(self.tmp.name)/'equipe.sqlite3'
        dados=carregar_equipe_gestao(self.actor,self.resp,self.store,db)
        porcodigo={p['codigo']:p for p in dados['pessoas']}
        self.assertIn('99',porcodigo)
        self.assertEqual(porcodigo['99']['supervisor'],'Sem supervisor')
        self.assertEqual(porcodigo['97']['inativo'],'S')
        processar_equipe_gestao(self.actor,self.resp,dict(acao='excluir',codigo='99',versao=0),self.store,db)
        dados=carregar_equipe_gestao(self.actor,self.resp,self.store,db)
        self.assertFalse(next(p for p in dados['pessoas'] if p['codigo']=='99')['incluida'])
        processar_equipe_gestao(self.actor,self.resp,dict(acao='incluir',codigo='99',versao=1),self.store,db)
        dados=carregar_equipe_gestao(self.actor,self.resp,self.store,db)
        self.assertTrue(next(p for p in dados['pessoas'] if p['codigo']=='99')['incluida'])
        processar_equipe_gestao(self.actor,self.resp,dict(acao='todos',versao=2),self.store,db)

    def test_equipes_nao_podem_ser_alteradas_por_outros_perfis(self):
        for cod in ['S1','01']:
            with self.assertRaises(PermissionError):
                carregar_equipe_gestao(dict(self.usuarios[cod],role='gestao'),self.resp,self.store,Path(self.tmp.name)/'equipe.sqlite3')

    def test_versao_da_equipe_impede_sobrescrita(self):
        db=Path(self.tmp.name)/'equipe.sqlite3'
        processar_equipe_gestao(self.actor,self.resp,dict(acao='excluir',codigo='99',versao=0),self.store,db)
        with self.assertRaises(AuthConflict):
            processar_equipe_gestao(self.actor,self.resp,dict(acao='incluir',codigo='99',versao=0),self.store,db)

    def test_mesma_conta_em_duas_instalacoes_tem_senhas_independentes(self):
        from radar_auth_store import AuthStore
        outro=AuthStore.inicializar(Path(self.tmp.name)/'outra.sqlite3')
        row=self.store.find_user('01').to_dict()
        outro.add_user(row)
        antes=outro.find_user('01').PasswordHash
        self.executar(self.evento())
        self.assertNotEqual(self.store.find_user('01').PasswordHash,antes)
        self.assertEqual(outro.find_user('01').PasswordHash,antes)
        self.assertNotEqual(informacao_instalacao(self.store.path)['base'],informacao_instalacao(outro.path)['base'])


class TestIdentificacao(unittest.TestCase):
    def test_id_estavel_sem_expor_caminhos(self):
        a=informacao_instalacao('/tmp/ficticio-A.sqlite3')
        b=informacao_instalacao('/tmp/ficticio-A.sqlite3')
        c=informacao_instalacao('/tmp/ficticio-B.sqlite3')
        self.assertEqual(a,b);self.assertNotEqual(a['base'],c['base'])
        self.assertEqual(len(a['base']),10)
        self.assertNotIn('/tmp',str(a))



class _Interrupcao(BaseException):pass

class _EstadoInterrompido(dict):
    interromper=True
    def __setitem__(self,chave,valor):
        if chave=='auth_user' and self.interromper:
            self.interromper=False
            raise _Interrupcao()
        super().__setitem__(chave,valor)


class TestRetomadaAuth(unittest.TestCase):
    setUp=fixture_acessos.TestGestaoAcessos.setUp
    tearDown=fixture_acessos.TestGestaoAcessos.tearDown

    def interface(self,estado):
        from types import SimpleNamespace
        def rerun():raise _Interrupcao()
        return SimpleNamespace(session_state=estado,rerun=rerun)

    def test_login_interrompido_retoma_sem_recriar_sessao(self):
        import auth
        pedido=dict(tipo='login',cod='01',senha='sintetica_original')
        estado=_EstadoInterrompido(_auth_fluxo={'lock':threading.Lock(),'pedido':pedido,'resultado':{}})
        with patch.object(auth,'st',self.interface(estado)),patch.object(auth,'_store',return_value=self.store):
            antes=self.store.status()['sessoes']
            with self.assertRaises(_Interrupcao):auth._retomar_operacao_auth()
            self.assertEqual(pedido,{})
            self.assertEqual(self.store.status()['sessoes'],antes)
            self.assertEqual(estado['_auth_fluxo']['resultado']['tipo'],'sessao')
            with self.assertRaises(_Interrupcao):auth._retomar_operacao_auth()
            self.assertTrue(estado['auth_authenticated'])
            self.assertEqual(estado['auth_user'],'01')
            self.assertEqual(self.store.status()['sessoes'],antes)
            self.assertEqual(estado['_auth_fluxo']['resultado'],{})

    def test_resultado_guardado_nao_restaura_token_revogado(self):
        import auth
        token=self.usuarios['01']['token']
        estado={'_auth_fluxo':{'lock':threading.Lock(),'resultado':dict(tipo='sessao',token=token)}}
        self.store.remove_session(token)
        with patch.object(auth,'st',self.interface(estado)),patch.object(auth,'_store',return_value=self.store):
            auth._retomar_operacao_auth()
        self.assertNotIn('auth_authenticated',estado)
        self.assertIn('erro',estado['_auth_fluxo']['resultado'])

    def test_troca_interrompida_nao_reaplica_senha_no_rerun(self):
        import auth,bcrypt
        self.store.set_flag('01','ResetRequired',True)
        row=self.store.find_user('01')
        pedido=dict(tipo='troca',cod='01',hash_atual=row.PasswordHash,versao=int(row._AuthVersion),
            nova='pessoal_sintetica_final',confirma='pessoal_sintetica_final')
        estado=_EstadoInterrompido(_auth_fluxo={'lock':threading.Lock(),'pedido':pedido,'resultado':{}})
        with patch.object(auth,'st',self.interface(estado)),patch.object(auth,'_store',return_value=self.store):
            with self.assertRaises(_Interrupcao):auth._retomar_operacao_auth()
            alterado=self.store.find_user('01')
            self.assertFalse(alterado.ResetRequired)
            self.assertTrue(bcrypt.checkpw(b'pessoal_sintetica_final',alterado.PasswordHash.encode()))
            self.assertEqual(pedido,{})
            with self.assertRaises(_Interrupcao):auth._retomar_operacao_auth()
            self.assertEqual(self.store.find_user('01')._AuthVersion,alterado._AuthVersion)
            self.assertTrue(estado['auth_authenticated'])

    def test_reruns_sobrepostos_processam_o_login_uma_vez(self):
        from concurrent.futures import ThreadPoolExecutor
        import auth,time
        pedido=dict(tipo='login',cod='01',senha='sintetica_original')
        estado={'_auth_fluxo':{'lock':threading.Lock(),'pedido':pedido,'resultado':{}}}
        original=auth._autenticar_pedido
        def demorado(p):
            time.sleep(.02)
            return original(p)
        def tentar(_):
            try:auth._retomar_operacao_auth()
            except _Interrupcao:return True
        with patch.object(auth,'st',self.interface(estado)),patch.object(auth,'_store',return_value=self.store), \
             patch.object(auth,'_autenticar_pedido',side_effect=demorado) as executar, \
             patch.object(auth,'_iniciar_sessao_state',side_effect=_Interrupcao):
            with ThreadPoolExecutor(4) as pool:
                self.assertTrue(all(pool.map(tentar,range(4))))
            self.assertEqual(executar.call_count,1)
        self.assertEqual(pedido,{})
        self.assertEqual(estado['_auth_fluxo']['resultado']['tipo'],'sessao')

    def test_logout_renova_ponte_cookie_e_remove_estado_antigo(self):
        import auth
        estado=dict(auth_cookie_epoch=3,_cm=object(),auth_token='somente_token_sintetico',
            auth_authenticated=True,gm_auth_read_antigo={'cookie':'antigo'})
        with patch.object(auth,'st',self.interface(estado)):
            auth._limpar_sessao()
        self.assertEqual(estado,{'auth_cookie_epoch':4})

if __name__=='__main__':unittest.main()
