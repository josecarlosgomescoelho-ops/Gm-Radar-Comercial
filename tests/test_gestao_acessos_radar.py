"""Contas ficticias, sem ERP: autorizacao, concorrencia, equipe e ordenacao."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import uuid

import bcrypt
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'dashboards'))
from radar_auth_store import AuthStore,AuthError,AuthConflict,SP
from radar_acessos import carregar_acessos,processar_acesso
from radar_equipe import candidatos,aplicar_equipe,salvar_equipe
from radar_ordem import chave_nome,ordenar_registros

HASH=bcrypt.hashpw(b'sintetica_original',bcrypt.gensalt(rounds=4)).decode()


def equipe():
    return pd.DataFrame([
        [1,'03','Zelia','V','S1','Sup Z','N'],[1,'02','Álvaro','V','S1','Sup Z','N'],
        [1,'01','Ana','V','S1','Sup Z','N'],[1,'04','Bia','V','S2','Sup A','N'],
        [1,'99','Sem vinculo','V','','Sem supervisor','N'],
        [1,'98','Supervisor inexistente','V','X','Nome antigo','N'],
        [1,'97','Inativa','V','S1','Sup Z','S'],
        [1,'96','Sup inativo','V','S9','Sup inativo','N'],
        [1,'00002','Empresa','V','S1','Sup Z','N'],
        [1,'S1','Supervisor Z','S','','','N'],[1,'S2','Supervisor A','S','','','N'],
        [1,'S9','Supervisor inativo','S','','','S'],
    ],columns=['IdEmpresa','CodVendedor','Vendedor','Tipo','CodSupervisor','Supervisor','Inativo'])


class TestGestaoAcessos(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='radar-gestao-test-')
        self.store=AuthStore.inicializar(Path(self.tmp.name)/'auth.sqlite3')
        self.resp=aplicar_equipe(equipe(),Path(self.tmp.name)/'metas.sqlite3')
        self.usuarios={}
        for cod,role in [('G','gestao'),('G2','gestao'),('S1','supervisor'),('01','vendedor')]:
            self.store.add_user(dict(CodVendedor=cod,NomeVendedor='Teste '+cod,Role=role,PasswordHash=HASH,
                FirstLogin=False,ResetRequired=False,Active=True,CreatedAt=datetime.now(),LastLogin=pd.NaT,LastFilters='[]'))
            token=self.store.create_session(self.store.find_user(cod),[],datetime.now(SP)+timedelta(hours=1))
            self.usuarios[cod]=dict(cod=cod,role=role,nome='Teste '+cod,token=token)
        self.actor=self.usuarios['G']
        self.salt=bcrypt.gensalt(rounds=4)
        self.patch=patch('radar_acessos.bcrypt.gensalt',return_value=self.salt)
        self.patch.start()

    def tearDown(self):
        self.patch.stop();self.tmp.cleanup()

    def evento(self,acao='redefinir',cod='01',**campos):
        row=self.store.find_user(cod)
        return dict(tipo='gerir_acesso',id=uuid.uuid4().hex,acao=acao,codigo=cod,
            versao=int(row._AuthVersion) if row is not None else 0,senha='provisoria_sintetica',**campos)

    def executar(self,event,actor=None):
        return processar_acesso(actor or self.actor,self.resp,event,self.store)

    def test_lista_sem_credenciais_e_ordem_alfabetica(self):
        data=carregar_acessos(self.actor,self.resp,self.store)
        text=json.dumps(data)
        self.assertNotIn(HASH,text);self.assertNotIn('PasswordHash',text);self.assertNotIn(self.actor['token'],text)
        self.assertEqual([r['nome'] for r in data['catalogo']],sorted([r['nome'] for r in data['catalogo']],key=chave_nome))

    def test_supervisor_vendedora_e_papel_forjado_recusados(self):
        for cod in ['S1','01']:
            falso=dict(self.usuarios[cod],role='gestao')
            with self.assertRaises(PermissionError):carregar_acessos(falso,self.resp,self.store)
            with self.assertRaises(PermissionError):self.executar(self.evento(),falso)

    def test_sessao_revogada_recusada_na_escrita(self):
        self.store.set_flag('G','Active',False)
        with self.assertRaises(PermissionError):self.executar(self.evento())
        self.assertEqual(self.store.find_user('01').PasswordHash,HASH)

    def test_criar_vendedora_exige_vinculo_e_nome_canonico(self):
        ev=self.evento('criar','02',perfil='vendedor',nome='Nome enviado pelo navegador')
        self.executar(ev)
        row=self.store.find_user('02')
        self.assertEqual(row.NomeVendedor,'Álvaro')
        self.assertTrue(row.FirstLogin and row.ResetRequired and row.Active)
        self.assertTrue(bcrypt.checkpw(ev['senha'].encode(),row.PasswordHash.encode()))
        self.assertEqual(self.store.find_user('G').PasswordHash,HASH)

    def test_recusa_criacao_ausente_e_perfil_incompativel(self):
        for cod,perfil in [('99999','vendedor'),('02','supervisor'),('S1','vendedor')]:
            with self.assertRaises(PermissionError):self.executar(self.evento('criar',cod,perfil=perfil,nome='Teste'))

    def test_cria_supervisao_e_gestao_sem_alterar_existentes(self):
        self.executar(self.evento('criar','S2',perfil='supervisor',nome='Texto do navegador'))
        self.executar(self.evento('criar','G3',perfil='gestao',nome='Coordenadora'))
        self.assertEqual(self.store.find_user('S2').Role,'supervisor')
        self.assertEqual(self.store.find_user('G3').Role,'gestao')

    def test_recusa_conta_duplicada_e_codigo_equivalente(self):
        for cod in ['01','1']:
            with self.assertRaises(AuthConflict):self.executar(self.evento('criar',cod,perfil='gestao',nome='Outra'))
        self.assertEqual(self.store.find_user('01').PasswordHash,HASH)

    def test_senha_esquecida_revoga_sessao_e_exige_troca(self):
        antiga=self.store.find_user('01')
        self.executar(self.evento())
        row=self.store.find_user('01')
        self.assertTrue(row.ResetRequired)
        self.assertIsNone(self.store.get_session(self.usuarios['01']['token']))
        with self.assertRaises(AuthConflict):self.store.login_pending(antiga)
        self.store.login_pending(row)
        self.store.change_password(row,HASH)
        self.assertFalse(self.store.find_user('01').ResetRequired)

    def test_senha_invalida_nao_altera_conta(self):
        for senha in ['curta','a'*73,None]:
            e=self.evento();e['senha']=senha
            with self.assertRaises(ValueError):self.executar(e)
        self.assertEqual(self.store.find_user('01').PasswordHash,HASH)

    def test_reset_nao_reativa_conta_e_preserva_perfil(self):
        self.store.set_flag('01','Active',False)
        self.executar(self.evento())
        row=self.store.find_user('01')
        self.assertFalse(row.Active);self.assertEqual(row.Role,'vendedor')

    def test_auditoria_identifica_autor_sem_guardar_senha_provisoria(self):
        ev=self.evento();self.executar(ev)
        with self.store.connect() as c:
            row=c.execute('SELECT Autor,Alvo,Acao FROM auth_admin_events WHERE Evento=?',(ev['id'],)).fetchone()
            self.assertEqual(tuple(row),('G','01','redefinir'))
            self.assertNotIn(ev['senha'],'\n'.join(c.iterdump()))

    def test_desativar_revoga_sessao_sem_alterar_senha(self):
        self.executar(self.evento('atualizar','01',perfil='vendedor',nome='Ana',ativo=False))
        self.assertFalse(self.store.find_user('01').Active)
        self.assertEqual(self.store.find_user('01').PasswordHash,HASH)
        self.assertIsNone(self.store.get_session(self.usuarios['01']['token']))

    def test_perfil_muda_e_sessao_antiga_nao_herda_permissao(self):
        self.executar(self.evento('atualizar','01',perfil='gestao',nome='Ana',ativo=True))
        self.assertEqual(self.store.find_user('01').Role,'gestao')
        self.assertIsNone(self.store.get_session(self.usuarios['01']['token']))

    def test_edicao_antiga_e_evento_repetido_recusados(self):
        e=self.evento();outro=self.evento()
        self.executar(e)
        with self.assertRaises(AuthConflict):self.executar(outro)
        with self.assertRaises(AuthConflict):self.executar(e)

    def test_protege_proprio_acesso_e_perfil_tecnico(self):
        for perfil,ativo in [('vendedor',True),('gestao',False)]:
            with self.assertRaises(PermissionError):self.executar(self.evento('atualizar','G',perfil=perfil,nome='Gestao',ativo=ativo))
        with self.assertRaises(PermissionError):self.executar(self.evento('redefinir','G'))
        with self.assertRaises(PermissionError):self.executar(self.evento('atualizar','01',perfil='dev',nome='Ana',ativo=True))

    def test_dois_coordenadores_mesma_versao_so_um_vence(self):
        eventos=[self.evento(),self.evento()]
        def run(pair):
            e,actor=pair
            try:self.executar(e,actor);return 'ok'
            except AuthConflict:return 'conflito'
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(run,zip(eventos,[self.actor,self.usuarios['G2']])))
        self.assertCountEqual(results,['ok','conflito'])
        self.assertEqual(self.store.status()['integridade'],'ok')


class TestEquipeOrdenacao(unittest.TestCase):
    def test_catalogo_completo_sem_filtrar_por_supervisor_ou_faturamento(self):
        df=candidatos(equipe())
        self.assertEqual(set(df.CodVendedor),{'01','02','03','04','99','98','97','96'})
        self.assertEqual(df.loc[df.CodVendedor.eq('01'),'Supervisor'].iloc[0],'Supervisor Z')

    def test_selecao_manual_controla_participacao(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'metas.sqlite3'
            with self.assertRaises(PermissionError):salvar_equipe(dict(role='gestao',cod='G'),equipe(),['INEXISTENTE'],0,p)
            salvar_equipe(dict(role='gestao',cod='G'),equipe(),['01','02'],0,p)
            df=aplicar_equipe(equipe(),p)
            self.assertEqual(df.loc[df.Tipo.eq('V'),'CodVendedor'].tolist(),['02','01'])

    def test_nome_com_acento_e_empate_por_codigo(self):
        rows=[dict(nome='Zelia',cod='1'),dict(nome='Álvaro',cod='2'),dict(nome='ana',cod='3'),dict(nome='Ana',cod='1')]
        self.assertEqual([r['cod'] for r in ordenar_registros(rows,'nome','cod')],['2','1','3','1'])


if __name__=='__main__':unittest.main()
