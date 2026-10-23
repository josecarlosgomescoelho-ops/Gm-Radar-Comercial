"""Testes sinteticos da autenticacao: nao usam contas reais nem consultam o Cronos."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta
import hashlib
import json
import multiprocessing
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import unittest

import bcrypt
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'dashboards'))
from radar_auth_store import AuthStore,AuthError,AuthConflict,USER_COLUMNS,SP,migrar_parquets

TEST_PASSWORD='senha_sintetica_para_teste'
TEST_HASH=bcrypt.hashpw(TEST_PASSWORD.encode(),bcrypt.gensalt(rounds=4)).decode()


def fixture(root,total=3):
    cache=root/'cache';cache.mkdir(parents=True)
    usuarios=pd.DataFrame([dict(CodVendedor=f'{i:05}',NomeVendedor='Conta sintetica '+str(i),Role='gestao',
        PasswordHash=TEST_HASH,FirstLogin=False,ResetRequired=False,Active=True,
        CreatedAt=pd.Timestamp('2026-01-01 12:30:00'),LastLogin=pd.NaT,LastFilters='[]') for i in range(1,total+1)])
    usuarios.to_parquet(cache/'usuarios.parquet',index=False)
    pd.DataFrame([dict(CodVendedor='00001',NomeVendedor='Conta sintetica 1',Role='gestao',
        Action='login_success',Timestamp=pd.Timestamp('2026-01-02 09:10:00'))]).to_parquet(cache/'login_historico.parquet',index=False)
    pd.DataFrame([dict(token='legacy_session_synthetic_0123456789',CodVendedor='00001',NomeVendedor='Conta sintetica 1',
        Role='gestao',Expiry=datetime.now(SP).replace(tzinfo=None)+timedelta(hours=1),LastFilters='[]')]).to_parquet(cache/'sessions.parquet',index=False)
    return usuarios


def crash_writer(path):
    import os
    conn=sqlite3.connect(path,isolation_level=None)
    conn.execute('BEGIN IMMEDIATE')
    conn.execute("UPDATE auth_users SET NomeVendedor='NAO_DEVE_PERSISTIR' WHERE CodVendedor='00001'")
    os._exit(0)


def worker_process(path,index):
    store=AuthStore(path)
    for i in range(12):store.history(str(index),'Sintetico','gestao','process_test')


class TestAuthSQLite(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='radar-auth-unit-')
        self.root=Path(self.tmp.name)
        self.original=fixture(self.root)
        self.path=self.root/'data/auth.sqlite3'
        migrar_parquets(self.root,self.path,self.root/'backup')
        self.store=AuthStore(self.path)
    def tearDown(self):self.tmp.cleanup()
    def token(self,cod='00001'):
        return self.store.create_session(self.store.find_user(cod),[cod],datetime.now(SP)+timedelta(hours=1))

    def test_migracao_preserva_codigos_hashes_flags_e_arquivos(self):
        users=self.store.users()
        self.assertEqual(users.CodVendedor.tolist(),self.original.CodVendedor.tolist())
        self.assertEqual(users.PasswordHash.tolist(),self.original.PasswordHash.tolist())
        for name in ['usuarios.parquet','sessions.parquet','login_historico.parquet']:
            self.assertEqual((self.root/'cache'/name).read_bytes(),(self.root/'backup'/name).read_bytes())
        self.assertEqual(self.store.status(),dict(usuarios=3,sessoes=0,historico=1,integridade='ok'))
        self.assertIsNone(self.store.get_session('legacy_session_synthetic_0123456789'))
        self.assertEqual(str(users.LastLogin.dtype),'datetime64[ns]')

    def test_reexecucao_nao_reimporta_credenciais_antigas(self):
        self.store.set_flag('00001','ResetRequired',True)
        row=self.store.find_user('00001')
        novo=bcrypt.hashpw(b'novo_teste_sintetico',bcrypt.gensalt(rounds=4)).decode()
        self.store.change_password(row,novo)
        _,criado=migrar_parquets(self.root,self.path,self.root/'outro-backup')
        self.assertFalse(criado)
        self.assertEqual(self.store.find_user('00001').PasswordHash,novo)
        self.assertFalse((self.root/'outro-backup').exists())

    def test_login_canonico_atualiza_data_e_token_so_com_hash(self):
        row=self.store.find_user('1')
        self.assertEqual(row.CodVendedor,'00001')
        token=self.store.create_session(row,[],datetime.now(SP)+timedelta(hours=1))
        self.assertTrue(pd.notna(self.store.find_user('00001').LastLogin))
        self.assertEqual(self.store.get_session(token).CodVendedor,'00001')
        with self.store.connect() as c:
            valor=c.execute('SELECT TokenHash FROM auth_sessions').fetchone()[0]
            self.assertEqual(valor,hashlib.sha256(token.encode()).hexdigest())
            self.assertNotEqual(valor,token)

    def test_logout_e_desativacao_revogam_token(self):
        token=self.token();self.store.remove_session(token)
        self.assertIsNone(self.store.get_session(token))
        token=self.token();self.store.set_flag('00001','Active',False)
        self.assertIsNone(self.store.get_session(token))
        with self.assertRaises(AuthConflict):self.token()
        self.store.set_flag('00001','Active',True)
        self.assertIsNone(self.store.get_session(token))
        self.assertIsNotNone(self.store.get_session(self.token()))

    def test_reset_revoga_e_bloqueia_snapshot_autenticado_anterior(self):
        row=self.store.find_user('00001');token=self.token()
        self.store.set_flag('00001','ResetRequired',True)
        self.assertIsNone(self.store.get_session(token))
        with self.assertRaises(AuthConflict):self.store.create_session(row,[],datetime.now(SP)+timedelta(hours=1))

    def test_alteracao_de_senha_respeita_desafio_e_limpa_flags(self):
        self.store.set_flag('00001','ResetRequired',True)
        row=self.store.find_user('00001')
        self.store.login_pending(row)
        novo=bcrypt.hashpw(b'novo_sintetico',bcrypt.gensalt(rounds=4)).decode()
        atual=self.store.change_password(row,novo)
        self.assertFalse(atual.ResetRequired)
        self.assertFalse(atual.FirstLogin)
        self.assertTrue(bcrypt.checkpw(b'novo_sintetico',atual.PasswordHash.encode()))
        self.assertIsNotNone(self.store.get_session(self.token()))
        with self.assertRaises(AuthConflict):self.store.change_password(row,TEST_HASH)

    def test_troca_pendente_nao_reverte_reset_administrativo_posterior(self):
        self.store.set_flag('00001','ResetRequired',True)
        antigo=self.store.find_user('00001')
        self.store.set_flag('00001','ResetRequired',True)
        with self.assertRaises(AuthConflict):self.store.change_password(antigo,TEST_HASH)

    def test_filtros_isolados_e_revogacao_de_perfil(self):
        token=self.token();outro=self.token('00002')
        self.store.save_filters('00001',['A'],token)
        self.assertEqual(json.loads(self.store.get_session(token).LastFilters),['A'])
        with self.assertRaises(AuthConflict):self.store.save_filters('00001',['B'],outro)
        df=self.store.users();df.loc[df.CodVendedor.eq('00001'),'Role']='vendedor'
        self.store.save_snapshot(df)
        self.assertIsNone(self.store.get_session(token))
        novo=self.token()
        self.store.save_filters('00001',['B'],novo)
        self.assertEqual(json.loads(self.store.find_user('00001').LastFilters),['A'])

    def test_snapshot_antigo_nao_sobrescreve_gravacao_concorrente(self):
        antigo=self.store.users()
        token=self.token()
        antigo.loc[antigo.CodVendedor.eq('00001'),'NomeVendedor']='Alteracao de snapshot antigo'
        with self.assertRaises(AuthConflict):self.store.save_snapshot(antigo)
        self.assertIsNotNone(self.store.get_session(token))
        self.assertNotEqual(self.store.find_user('00001').NomeVendedor,'Alteracao de snapshot antigo')

    def test_snapshot_nao_apaga_outras_contas(self):
        df=self.store.users().iloc[:1].copy()
        df.loc[:,'NomeVendedor']='Nome novo sintetico'
        self.store.save_snapshot(df)
        self.assertEqual(len(self.store.users()),3)

    def test_mesma_conta_mantem_uma_sessao_por_vez(self):
        primeiro=self.token();segundo=self.token()
        self.assertIsNone(self.store.get_session(primeiro))
        self.assertIsNotNone(self.store.get_session(segundo))

    def test_expiracao_encerra_sessao(self):
        token=self.token()
        with self.store.connect(True) as c:c.execute("UPDATE auth_sessions SET Expiry='2000-01-01T00:00:00+00:00'")
        self.assertIsNone(self.store.get_session(token))
        self.assertEqual(self.store.status()['sessoes'],0)

    def test_reabertura_e_backup_preservam_dados(self):
        token=self.token()
        backup=self.store.backup(self.root/'backup-atual.sqlite3')
        clone=AuthStore(backup)
        self.assertEqual(clone.status(),self.store.status())
        self.assertIsNotNone(AuthStore(self.path).get_session(token))
        self.assertIsNotNone(clone.get_session(token))

    def test_exportacao_de_retorno_preserva_alteracoes_apos_migracao(self):
        self.store.set_flag('00001','ResetRequired',True)
        row=self.store.find_user('00001')
        novo=bcrypt.hashpw(b'senha_pos_migracao',bcrypt.gensalt(rounds=4)).decode()
        self.store.change_password(row,novo)
        self.store.set_flag('00002','Active',False)
        export=self.store.export_legacy(self.root/'export-legado')
        df=pd.read_parquet(export/'usuarios.parquet').set_index('CodVendedor')
        self.assertEqual(df.loc['00001','PasswordHash'],novo)
        self.assertFalse(df.loc['00002','Active'])
        self.assertTrue(pd.read_parquet(export/'sessions.parquet').empty)
        self.assertEqual(set(df.reset_index().columns),set(USER_COLUMNS))

    def test_gravacao_interrompida_nao_corrompe_base(self):
        antes=self.store.find_user('00001').NomeVendedor
        proc=multiprocessing.get_context('spawn').Process(target=crash_writer,args=(str(self.path),))
        proc.start();proc.join(timeout=20)
        self.assertEqual(proc.exitcode,0)
        self.assertEqual(self.store.find_user('00001').NomeVendedor,antes)
        self.assertEqual(self.store.status()['integridade'],'ok')

    def test_processos_distintos_gravam_sem_perda(self):
        antes=self.store.status()['historico']
        ctx=multiprocessing.get_context('spawn')
        processos=[ctx.Process(target=worker_process,args=(str(self.path),i)) for i in range(4)]
        for p in processos:p.start()
        for p in processos:
            p.join(timeout=30);self.assertEqual(p.exitcode,0)
        self.assertEqual(self.store.status()['historico'],antes+48)

    def test_migracao_invalida_nao_publica_base_nem_altera_origem(self):
        other=self.root/'outro';other.mkdir();df=fixture(other)
        df.loc[0,'PasswordHash']='HASH_INVALIDO_SINTETICO'
        df.to_parquet(other/'cache/usuarios.parquet',index=False)
        original=(other/'cache/usuarios.parquet').read_bytes()
        destino=other/'auth.sqlite3'
        with self.assertRaises(AuthError):migrar_parquets(other,destino,other/'backup')
        self.assertFalse(destino.exists())
        self.assertEqual((other/'cache/usuarios.parquet').read_bytes(),original)

    def test_trinta_conexoes_concorrentes_sem_perda_de_eventos(self):
        other=self.root/'carga';other.mkdir();fixture(other,total=30)
        path=other/'auth.sqlite3';migrar_parquets(other,path,other/'backup')
        store=AuthStore(path);antes=store.status()['historico'];barreira=threading.Barrier(30)
        def trabalho(i):
            db=AuthStore(path);cod=f'{i:05}';row=db.find_user(cod)
            barreira.wait(timeout=20)
            self.assertTrue(bcrypt.checkpw(TEST_PASSWORD.encode(),row.PasswordHash.encode()))
            token=db.create_session(row,[cod],datetime.now(SP)+timedelta(hours=1))
            for passo in range(6):
                db.save_filters(cod,[cod,str(passo)],token)
                db.history(cod,'Sintetico','gestao','carga_sintetica')
                self.assertEqual(db.get_session(token).CodVendedor,cod)
            return cod,token
        with ThreadPoolExecutor(max_workers=30) as pool:retornos=list(pool.map(trabalho,range(1,31)))
        self.assertEqual(store.status()['historico'],antes+30*7)
        self.assertEqual(store.status()['sessoes'],30)
        self.assertEqual(store.status()['integridade'],'ok')
        for cod,token in retornos:
            self.assertEqual(json.loads(store.get_session(token).LastFilters),[cod,'5'])
            self.assertTrue(pd.notna(store.find_user(cod).LastLogin))
            self.assertEqual(store.find_user(cod).PasswordHash,TEST_HASH)


if __name__=='__main__':unittest.main(verbosity=2)
