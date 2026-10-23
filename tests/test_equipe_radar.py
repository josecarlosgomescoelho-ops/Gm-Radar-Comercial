"""Testes sinteticos da selecao de equipe. Sem consulta ao Cronos."""
from contextlib import closing
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'dashboards'))
from radar_equipe import ler_equipe, salvar_equipe, candidatos
from radar_dados import construir_payload, ler_responsaveis
from radar_cache_local import carregar_local, disponivel_local
from radar_metas import salvar_meta
from radar_pdf import selecionar_pendentes


def fixture(cache):
    ref=pd.Timestamp.now(tz='America/Sao_Paulo').normalize().tz_localize(None)
    mes=ref.replace(day=1)
    hist=pd.DataFrame([['C1',1,ref,100,1],['C1',2,ref,-100,-1],
                      ['C2',3,ref,-30,-1],['C2',4,mes-pd.Timedelta(days=1),200,1],
                      ['C3',None,pd.NaT,0,None]],
                     columns=['CodCliFor','IdMov','DataFaturamento','ValorLiquido','MultiplicadorMov'])
    hist['IdEmpresa']=1;hist['DtMov']=hist.DataFaturamento
    hist['TipoMov']=hist.MultiplicadorMov.map({1:'2.4',-1:'2.8'})
    cli=pd.DataFrame([
        dict(CodCliFor='C1',CodVendedorCarteira='01',VendedorCarteira='Ana',CodSupervisor='S1',CurvaABC='B',TotalPeriodo=0,QuantidadeMovimentos=2,PosicaoCurva=2),
        dict(CodCliFor='C2',CodVendedorCarteira='01',VendedorCarteira='Ana',CodSupervisor='S1',CurvaABC='A',TotalPeriodo=170,QuantidadeMovimentos=2,PosicaoCurva=1),
        dict(CodCliFor='C3',CodVendedorCarteira='02',VendedorCarteira='Bia',CodSupervisor='S2',CurvaABC='C',TotalPeriodo=0,QuantidadeMovimentos=0,PosicaoCurva=3)])
    cli['MediaMensal']=cli.TotalPeriodo/12;cli['IdEmpresa']=1
    cli['Cliente']=cli.CodCliFor;cli['Telefone']='';cli['Celular']=''
    cli['CarteiraVAtiva']=True;cli['QtdClientesCurva']=3
    cli['DataCadastro']=mes;cli['CampoDataCadastro']='DataOperacao'
    for df in [cli,hist]:
        df['DataReferencia']=ref;df['PeriodoInicio']=mes-pd.DateOffset(months=11)
        df['PeriodoFimExclusivo']=ref+pd.Timedelta(days=1);df['SnapshotCarteira']='teste_sintetico'
        df['AtualizadoEmUTC']=pd.Timestamp.now(tz='UTC');df['VersaoInterfaceCarteira']=2
    cli.to_parquet(cache/'carteira_clientes.parquet',index=False)
    hist.to_parquet(cache/'carteira_historico.parquet',index=False)
    resp=pd.DataFrame([[1,'01','Ana','V','S1','Sup 1'],[1,'02','Bia','V','S2','Sup 2'],
                       [1,'S1','Sup 1','S','',''],[1,'00002','Empresa','V','','']],
                      columns=['IdEmpresa','CodVendedor','Vendedor','Tipo','CodSupervisor','Supervisor'])
    resp.to_parquet(cache/'radar_responsaveis.parquet',index=False)
    fin=pd.DataFrame([dict(CodVendedor='01',NomeVendedor='Ana',NomeFilial='GM',IdImagem=1,
        Qtd=2,ReceitaUnidades=1000000,CustoUnidades=700000,LucroUnidades=300000,
        PercRetabilidadeItem=30.,LinhaFinanceira=True)])
    fin['VersaoFinanceiroCronos']=1;fin['PeriodoInicio']=mes;fin['PeriodoFimInclusivo']=ref
    fin['DataReferencia']=ref;fin['AtualizadoEmUTC']=pd.Timestamp.now(tz='UTC')
    fin.to_parquet(cache/'rentabilidade_cronos.parquet',index=False)
    return resp


class TesteEquipeRadar(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='radar-equipe-')
        self.root=Path(self.temp.name);self.cache=self.root/'cache';self.cache.mkdir()
        self.db=self.root/'metas.sqlite3'
        self.resp=fixture(self.cache)
        self.user=dict(cod='G',role='gestao',nome='Gestao')
    def tearDown(self):self.temp.cleanup()
    def payload(self,user=None):return construir_payload(user or self.user,self.cache,self.db)[0]
    def salvar(self,codigos,versao=0,user=None):return salvar_equipe(user or self.user,self.resp,codigos,versao,self.db)

    def test_padrao_mantem_ativa_com_faturamento_zero(self):
        self.assertIsNone(ler_equipe(self.db))
        p=self.payload()
        self.assertEqual({v['CodVendedor'] for v in p['vendedoras']},{'01','02'})
        self.assertEqual(p['financeiro']['1|02|'+p['competencia']]['RealizadoMeta'],0)

    def test_selecao_remove_das_listas_sem_mudar_financeiro_global_ou_curva(self):
        anterior=self.payload()
        self.salvar(['01'])
        atual=self.payload()
        self.assertEqual([v['CodVendedor'] for v in atual['vendedoras']],['01'])
        self.assertNotIn('C3',{c['CodCliFor'] for c in atual['cadastrosMes']})
        self.assertEqual(atual['financeiroGeral'],anterior['financeiroGeral'])
        self.assertEqual(atual['clientes'],anterior['clientes'])
        self.assertEqual({c['CodCliFor']:c['CurvaABC'] for c in atual['clientes']},{'C1':'B','C2':'A'})
        self.assertEqual(ler_equipe(self.db)['autor'],'G')

    def test_apenas_gestao_pode_selecionar(self):
        for role in ['vendedor','supervisor','desconhecido']:
            with self.assertRaises(PermissionError):self.salvar(['01'],user=dict(role=role,cod='01'))
        self.assertIsNone(ler_equipe(self.db))

    def test_recusa_codigos_invalidos(self):
        for codigos in [['01','01'],[' 01'],[1],['desconhecido'],['S1'],['00002']]:
            with self.assertRaises((ValueError,PermissionError)):self.salvar(codigos)
        self.assertIsNone(ler_equipe(self.db))

    def test_mostra_cadastro_inativo_e_a_gestao_decide(self):
        df=self.resp.copy();df['Inativo']='N';df.loc[df.CodVendedor.eq('02'),'Inativo']='S'
        self.assertEqual(set(candidatos(df).CodVendedor),{'01','02'})
        salvar_equipe(self.user,df,['02'],0,self.db)
        df.to_parquet(self.cache/'radar_responsaveis.parquet',index=False)
        self.assertIn('02',set(ler_responsaveis(self.cache,self.db).CodVendedor))
        self.assertIn('02',set(ler_responsaveis(self.cache,self.db,equipe_atual=False).CodVendedor))

    def test_equipe_vazia_e_legitima_e_pode_ser_reaberta(self):
        self.salvar([])
        self.assertEqual(ler_equipe(self.db)['codigos'],[])
        self.assertEqual(self.payload()['vendedoras'],[])
        self.salvar(['01'],1)
        self.assertEqual([v['CodVendedor'] for v in self.payload()['vendedoras']],['01'])

    def test_concorrencia_e_auditoria(self):
        self.salvar(['01'])
        with self.assertRaises(ValueError):self.salvar(['02'],0)
        self.assertEqual(ler_equipe(self.db)['codigos'],['01'])
        self.salvar(['01'],1) # idempotente
        with closing(sqlite3.connect(self.db)) as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM radar_equipe_auditoria').fetchone()[0],1)
        self.salvar(['01','02'],1)
        self.assertEqual(ler_equipe(self.db)['versao'],2)
        with closing(sqlite3.connect(self.db)) as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM radar_equipe_auditoria').fetchone()[0],2)

    def test_selecao_invalida_cache_e_abrange_todas_as_sessoes(self):
        estado={}
        carregar_local(self.user,self.cache,estado,self.db)
        carregar_local(self.user,self.cache,estado,self.db)
        self.assertTrue(disponivel_local(self.user,self.cache,estado,self.db))
        self.salvar(['01'])
        self.assertFalse(disponivel_local(self.user,self.cache,estado,self.db))
        p,_,_=carregar_local(self.user,self.cache,estado,self.db)
        self.assertEqual([v['CodVendedor'] for v in p['vendedoras']],['01'])
        p2=self.payload(dict(cod='01',nome='Ana',role='vendedor'))
        self.assertEqual([v['CodVendedor'] for v in p2['vendedoras']],['01'])

    def test_exportacao_e_meta_recusam_excluido_mesmo_com_payload_antigo(self):
        antigo=self.payload()
        self.salvar(['01'])
        resp=ler_responsaveis(self.cache,self.db)
        with self.assertRaises(PermissionError):
            selecionar_pendentes(antigo,self.user,resp,dict(curva='TODAS',vendedores=['02']))
        evento=dict(id='equipe_teste_0123456789',vendedor='02',competencia=antigo['competencia'],valor='1000,00',versao=0)
        with self.assertRaises(PermissionError):salvar_meta(self.user,resp,evento,self.db)
        with self.assertRaises(PermissionError):self.payload(dict(cod='02',nome='Bia',role='vendedor'))


if __name__=='__main__':unittest.main(verbosity=2)
