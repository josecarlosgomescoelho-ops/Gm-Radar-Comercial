"""Run: python -m unittest discover -s tests -v (synthetic data only)."""
from pathlib import Path
import sys, tempfile, unittest, ast, json
from unittest.mock import patch
from decimal import Decimal
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'dashboards'))
from radar_metas import autorizados, centavos, salvar_meta, ler_metas
from radar_dados import preparar_clientes, construir_payload
import radar_validado as v


def dados():
    ref=pd.Timestamp.now(tz='America/Sao_Paulo').normalize().tz_localize(None)
    mes=ref.replace(day=1)
    anterior=mes-pd.Timedelta(days=1)
    carteira=pd.DataFrame([
        dict(IdEmpresa=1,CodCliFor='C1',Cliente='Cliente A',CodVendedorCarteira='01',VendedorCarteira='Ana',CodSupervisor='S1',CurvaABC='A',MediaMensal=100,TotalPeriodo=1200,Telefone='',Celular='83999990101',DataCadastro=pd.NaT),
        dict(IdEmpresa=1,CodCliFor='C2',Cliente='Cliente B',CodVendedorCarteira='01',VendedorCarteira='Ana',CodSupervisor='S1',CurvaABC='B',MediaMensal=50,TotalPeriodo=600,Telefone='',Celular='',DataCadastro=mes),
        dict(IdEmpresa=1,CodCliFor='C3',Cliente='Cliente C',CodVendedorCarteira='02',VendedorCarteira='Bia',CodSupervisor='S2',CurvaABC='C',MediaMensal=0,TotalPeriodo=0,Telefone='',Celular='',DataCadastro=mes),
    ])
    hist=pd.DataFrame([
        ['C1',1,'2.4',ref,100,1],['C1',2,'2.8',ref,-100,-1],
        ['C2',3,'2.8',ref,-30,-1],['C2',4,'2.4',anterior,200,1],
        ['C3',None,None,pd.NaT,0,None]
    ],columns=['CodCliFor','IdMov','TipoMov','DataFaturamento','ValorLiquido','MultiplicadorMov'])
    resp=pd.DataFrame([
        [1,'01','Ana','V','S1','Supervisor 1'],[1,'02','Bia','V','S2','Supervisor 2'],
        [1,'S1','Supervisor 1','S','',''],[1,'00002','Empresa','V','','']
    ],columns=['IdEmpresa','CodVendedor','Vendedor','Tipo','CodSupervisor','Supervisor'])
    return ref,carteira,hist,resp


class Regras(unittest.TestCase):
    def test_compra_compensada_por_devolucao(self):
        ref,c,h,_=dados(); r=preparar_clientes(c,h,ref)
        self.assertTrue(r[0]['ComprouNoMes']);self.assertEqual(r[0]['FatMesAtual'],0)
        self.assertFalse(r[1]['ComprouNoMes']);self.assertEqual(r[1]['UltimaCompra'],(ref.replace(day=1)-pd.Timedelta(days=1)).strftime('%d/%m/%Y'))
        self.assertTrue(r[1]['AtivoUltimos2Meses']);self.assertEqual(r[1]['MesesUltimaCompra'],1)
        self.assertIsNone(r[2]['UltimaCompra']);self.assertEqual(r[2]['DiasUltimaCompra'],999)
        self.assertIsNone(r[1]['PrimeiraCompraData']) # pre-registration purchase is never presented as first

    def test_cadastro_nao_e_primeira_compra(self):
        ref,c,h,_=dados();r=preparar_clientes(c,h,ref)
        self.assertFalse(r[0]['CadastradoNoMes']);self.assertTrue(r[1]['CadastradoNoMes'])
        self.assertTrue(r[2]['CadastradoNoMes'])

    def test_valor_brasileiro(self):
        self.assertEqual(centavos('35.000,00'),3500000)
        self.assertEqual(centavos('35000,00'),3500000)
        for value in ['35000.00','nan','inf','1e3','-1','0','1,222','9.99,00','1;DROP TABLE metas',None,'999999999999999999999']:
            with self.assertRaises(ValueError,msg=str(value)):centavos(value)

    def test_escopos(self):
        *_,r=dados()
        self.assertEqual(set(autorizados({'cod':'01','role':'vendedor'},r).CodVendedor),{'01'})
        self.assertEqual(set(autorizados({'cod':'S1','role':'supervisor'},r).CodVendedor),{'01','S1'})
        with self.assertRaises(PermissionError):autorizados({'cod':'01','role':'admin_inventado'},r)

    def test_metas_persistencia_permissoes_e_concorrencia(self):
        *_,r=dados()
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'metas.db'; user={'cod':'S1','role':'supervisor'}
            ev=dict(id='a'*32,vendedor='01',competencia='2026-10',valor='10.000,00',versao=0)
            salvar_meta(user,r,ev,path)
            self.assertEqual(ler_metas(['01'],path)[('01','2026-10')]['centavos'],1000000)
            salvar_meta(user,r,ev,path) # idempotent repeat
            with self.assertRaises(ValueError):salvar_meta(user,r,dict(ev,id='b'*32),path)
            with self.assertRaises(PermissionError):salvar_meta(user,r,dict(ev,id='c'*32,vendedor='02'),path)
            with self.assertRaises(PermissionError):salvar_meta({'cod':'01','role':'vendedor'},r,dict(ev,id='d'*32),path)
            salvar_meta(user,r,dict(ev,id='e'*32,competencia='2026-11'),path)
            self.assertEqual(len(ler_metas(['01'],path)),2)
            self.assertEqual(ler_metas(['02'],path),{})

    def test_financeiro_precisao_e_margem_individual(self):
        f=pd.DataFrame([dict(LinhaFinanceira=True,CodVendedor='01',ReceitaUnidades=140000,CustoUnidades=122310,LucroUnidades=17690,Qtd=1,PercRetabilidadeItem=12.63),
                        dict(LinhaFinanceira=True,CodVendedor='00002',ReceitaUnidades=100000,CustoUnidades=50000,LucroUnidades=50000,Qtd=1,PercRetabilidadeItem=50)])
        r=v._resumo_financeiro_cronos(f,['01'])
        self.assertEqual(r['margem'],Decimal('12.63'));self.assertEqual(r['custo'],Decimal('12.231'))
        self.assertEqual(v._resumo_financeiro_cronos(f,[],True)['receita'],Decimal(24))

    def test_payload_nao_vaza_outra_equipe(self):
        ref,c,h,r=dados()
        for df in [c,h]:
            df['DataReferencia']=ref
        c['VersaoInterfaceCarteira']=2;c['CampoDataCadastro']='';c['AtualizadoEmUTC']=pd.Timestamp.now(tz='UTC')
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)
            with patch('radar_dados.ler_responsaveis',return_value=r),patch.object(v,'q_base_carteira',side_effect=lambda codes:(c[c.CodVendedorCarteira.isin(codes)],h[h.CodCliFor.isin(c[c.CodVendedorCarteira.isin(codes)].CodCliFor)])),patch.object(v,'_load_carteira_abc',return_value=(c,h)),patch.object(v,'_versao_cache_carteira',return_value=()),patch.object(v,'_versao_cache_financeiro',side_effect=FileNotFoundError('Financeiro indisponível')):
                payload,_,_=construir_payload({'cod':'S1','nome':'Supervisor 1','role':'supervisor'},p,p/'meta.db')
                self.assertEqual([x['CodVendedor'] for x in payload['vendedoras']],['01'])
                self.assertEqual({x['CodCliFor'] for x in payload['clientes']},{'C1','C2'})
                self.assertNotIn('Bia',json.dumps(payload))
                self.assertIsNone(payload['financeiroGeral'])
                self.assertIsNone(payload['resumos']['01']['somaRealizado'])
                self.assertFalse(payload['cadastroDisponivel'])

if __name__=='__main__':unittest.main()
