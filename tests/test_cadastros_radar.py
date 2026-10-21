"""Testes locais com dados sinteticos. Nao conectam ao Cronos."""
import ast
import logging
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'dashboards'))
from radar_dados import construir_payload, cadastros_fora_carteira


def funcoes_etl(cache):
    arvore = ast.parse((ROOT / 'scripts/etl_cache.py').read_text(encoding='utf-8-sig'))
    nomes = {'_campo_data_cadastro', 'etl_carteira_clientes'}
    modulo = ast.Module(body=[n for n in arvore.body if isinstance(n, ast.FunctionDef) and n.name in nomes], type_ignores=[])
    escopo = {'pd':pd, 'os':os, 'logging':logging, 'CACHE_DIR':cache}
    exec(compile(modulo, '<etl em teste sem conexao>', 'exec'), escopo)
    return escopo


class CursorFalso:
    def __init__(self, encontrado=True):
        self.encontrado = encontrado
        self.fechado = False
        self.sql = ''
    def execute(self, sql, parametros):
        self.sql = sql
        self.parametros = parametros
    def fetchone(self):
        return ('DataOperacao',) if self.encontrado else None
    def close(self):
        self.fechado = True


class ConexaoFalsa:
    def __init__(self, encontrado=True):
        self.c = CursorFalso(encontrado)
    def cursor(self):
        return self.c


def base_sintetica(ref):
    mes = ref.replace(day=1)
    itens = []
    def cliente(cod, vendedor, cadastro, movs):
        elegivel = vendedor in {'01','02'}
        base = dict(IdEmpresa=1, CodCliFor=cod, Cliente='Cliente '+cod,
            RazaoSocial='Razao '+cod, TipoCliente='C', ClienteInativo='N',
            Telefone='', Celular='', CodVendedorCarteira=vendedor,
            IdEmpresaResponsavel=1 if vendedor else None,
            VendedorCarteira={'01':'Ana','02':'Bia','00002':'Empresa'}.get(vendedor,''),
            TipoResponsavel='V' if vendedor else None, ResponsavelInativo='N' if vendedor else None,
            CodSupervisor={'01':'S1','02':'S2'}.get(vendedor,''),
            CarteiraVAtiva=elegivel, DataCadastro=cadastro, LinhasCadastro=1)
        for mid, data, valor, mult in movs or [(None,pd.NaT,0 if elegivel else None,None)]:
            itens.append(dict(base, IdMov=mid, NumMov=str(mid) if mid else None,
                TipoMov='2.4' if mult == 1 else '2.8' if mult == -1 else None,
                DtMov=data, DataFaturamento=data, ItensSemValor=0 if mid else None,
                ValorLiquido=valor, MultiplicadorMov=mult))
    cliente('C1','01',pd.NaT,[(1,ref,100,1),(2,ref,-100,-1)])
    cliente('C2','01',mes,[(3,mes-pd.Timedelta(days=1),200,1),(4,ref,-30,-1)])
    cliente('C3','02',mes,[])
    cliente('C4',None,ref,[])
    cliente('C5','00002',ref,[])
    cliente('C6',None,mes-pd.Timedelta(days=1),[])
    cliente('C7',None,ref+pd.Timedelta(days=1),[])
    return pd.DataFrame(itens)


class TesteCadastrosRadar(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='radar-cadastro-')
        self.root = Path(self.temp.name)
        self.cache = self.root / 'cache'
        self.cache.mkdir()
        self.ref = pd.Timestamp.now(tz='America/Sao_Paulo').normalize().tz_localize(None)
        self.etl = funcoes_etl(self.cache)

    def tearDown(self):
        self.temp.cleanup()

    def extrair_falso(self):
        bruto = base_sintetica(self.ref)
        self.sql = []
        def executar(nome, sql, conn):
            self.sql.append(sql)
            return bruto.copy()
        self.etl['_run'] = executar
        with patch.dict(os.environ, RADAR_CAMPO_DATA_CADASTRO='DataOperacao'):
            self.etl['etl_carteira_clientes'](ConexaoFalsa(), self.ref)
        resp = pd.DataFrame([[1,'01','Ana','V','S1','Supervisor 1'],
            [1,'02','Bia','V','S2','Supervisor 2'],[1,'S1','Supervisor 1','S','',''],
            [1,'00002','Empresa','V','','']],
            columns=['IdEmpresa','CodVendedor','Vendedor','Tipo','CodSupervisor','Supervisor'])
        resp.to_parquet(self.cache/'radar_responsaveis.parquet', index=False)
        return pd.read_parquet(self.cache/'carteira_clientes.parquet')

    def payload(self, role='gestao', cod='G'):
        return construir_payload(dict(cod=cod, role=role, nome='Teste '+role), self.cache, self.root/'metas.sqlite3')[0]

    def test_tipo_alias_usa_tipo_base_e_fecha_cursor(self):
        conn = ConexaoFalsa()
        with patch.dict(os.environ, RADAR_CAMPO_DATA_CADASTRO='DataOperacao'):
            self.assertEqual(self.etl['_campo_data_cadastro'](conn), 'DataOperacao')
        self.assertIn('ty.user_type_id=c.system_type_id', conn.c.sql)
        self.assertEqual(conn.c.parametros, ('DataOperacao',))
        self.assertTrue(conn.c.fechado)

    def test_campo_invalido_recusa_e_fecha_cursor(self):
        conn = ConexaoFalsa(False)
        with patch.dict(os.environ, RADAR_CAMPO_DATA_CADASTRO='DataOperacao'):
            with self.assertRaises(ValueError): self.etl['_campo_data_cadastro'](conn)
        self.assertTrue(conn.c.fechado)
        with patch.dict(os.environ, RADAR_CAMPO_DATA_CADASTRO='DataOperacao]; DROP TABLE'):
            with self.assertRaises(ValueError): self.etl['_campo_data_cadastro'](ConexaoFalsa())

    def test_carteira_curva_e_novos_sem_compras(self):
        df = self.extrair_falso().set_index('CodCliFor')
        self.assertEqual(df.loc['C2','TotalPeriodo'],170)
        self.assertAlmostEqual(df.loc['C2','MediaMensal'],170/12)
        self.assertEqual(df.loc[['C2','C1','C3'],'CurvaABC'].tolist(),['A','B','C'])
        self.assertEqual(df.loc['C4','RazaoSocial'],'Razao C4')
        self.assertFalse(df.loc['C4','CarteiraVAtiva'])
        p = self.payload()
        self.assertEqual({c['CodCliFor'] for c in p['clientes']},{'C1','C2'})
        self.assertEqual({c['CodCliFor'] for c in p['cadastrosMes']},{'C2','C3'})
        self.assertEqual({c['CodCliFor'] for c in p['cadastrosSemCarteiraAtiva']},{'C4','C5'})
        self.assertFalse(p['cadastroDisponivel']) # C1 nao tem data
        self.assertTrue(p['cadastroListagemDisponivel'])
        self.assertEqual(p['cadastroCompletoPorVendedor'],{'01':False,'02':True})
        self.assertFalse(next(c for c in p['cadastrosMes'] if c['CodCliFor']=='C3')['ComprouNoMes'])
        self.assertEqual(len(self.sql),1) # nenhuma consulta extra de cadastros

    def test_perfis_nao_recebem_clientes_de_outros(self):
        self.extrair_falso()
        for role,cod in [('vendedor','01'),('supervisor','S1')]:
            p = self.payload(role,cod)
            self.assertEqual(p['cadastrosSemCarteiraAtiva'],[])
            self.assertEqual({c['CodCliFor'] for c in p['cadastrosMes']},{'C2'})
            self.assertEqual({c['CodVendedorCarteira'] for c in p['clientes']},{'01'})
        p = self.payload('vendedor','02')
        self.assertEqual({c['CodCliFor'] for c in p['cadastrosMes']},{'C3'})
        self.assertEqual(p['clientes'],[])

    def test_campo_desconfigurado_nao_inventa_cadastro(self):
        self.extrair_falso()
        for nome in ['carteira_clientes','carteira_historico']:
            path = self.cache/(nome+'.parquet')
            df=pd.read_parquet(path)
            df['CampoDataCadastro']=''
            df.to_parquet(path,index=False)
        p=self.payload()
        self.assertFalse(p['cadastroListagemDisponivel'])
        self.assertEqual(p['cadastrosMes'],[])
        self.assertEqual(p['cadastrosSemCarteiraAtiva'],[])

    def test_sem_responsavel_nao_inventa_situacao_compra(self):
        df=self.extrair_falso()
        itens=cadastros_fora_carteira(df,self.ref,dict(role='gestao'))
        sem=next(i for i in itens if i['CodCliFor']=='C4')
        self.assertEqual(sem['CodVendedorCarteira'],'')
        self.assertEqual(sem['SituacaoResponsavel'],'Sem responsavel cadastrado')
        self.assertNotIn('ComprouNoMes',sem)
        self.assertEqual(cadastros_fora_carteira(df,self.ref,dict(role='vendedor')),[])

    def test_falha_receita_preserva_dois_caches_anteriores(self):
        self.extrair_falso()
        paths=[self.cache/(n+'.parquet') for n in ['carteira_clientes','carteira_historico']]
        anteriores=[p.read_bytes() for p in paths]
        bruto=base_sintetica(self.ref)
        bruto.loc[bruto.IdMov.eq(1),'ItensSemValor']=1
        self.etl['_run']=lambda *args:bruto.copy()
        with patch.dict(os.environ,RADAR_CAMPO_DATA_CADASTRO='DataOperacao'):
            with self.assertRaises(ValueError): self.etl['etl_carteira_clientes'](ConexaoFalsa(),self.ref)
        self.assertEqual(anteriores,[p.read_bytes() for p in paths])


if __name__=='__main__':
    unittest.main(verbosity=2)
