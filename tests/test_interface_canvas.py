"""Leitura local, snapshots e gravações concorrentes, sem conexão ao ERP."""
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os
import sqlite3
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'dashboards'))
import radar_cache_local as local
import radar_leitura as leitura
import radar_validado as validado
from radar_metas import salvar_meta,ler_metas


class LeituraConcorrente(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='radar-canvas-teste-')
        self.root=Path(self.tmp.name);leitura.limpar_leitura();local.limpar_preparacao()

    def tearDown(self):
        leitura.limpar_leitura();local.limpar_preparacao();self.tmp.cleanup()

    def test_gestao_reusa_base_comercial_sem_reusar_identidade_ou_acessos(self):
        chave=(('G1','gestao','Ana'),'2026-10-22',(('arquivo',1),))
        resultado=({'usuario':{'cod':'G1','role':'gestao','nome':'Ana'},'clientes':[{'codigo':'C1'}]},'resp','fin')
        with patch('radar_cache_local.construir_payload',return_value=resultado) as construir:
            a=local._preparar(dict(cod='G1',role='gestao',nome='Ana'),self.root,self.root/'m.sqlite3',chave)
            b=local._preparar(dict(cod='G2',role='gestao',nome='Bia'),self.root,self.root/'m.sqlite3',chave)
        self.assertEqual(construir.call_count,1)
        self.assertEqual(a[0]['usuario']['cod'],'G1');self.assertEqual(b[0]['usuario']['cod'],'G2')
        a[0]['acessos']={'contas':['admin-da-primeira-sessao']}
        self.assertNotIn('acessos',b[0])

    def test_vendedoras_nao_reusam_base_global_da_gestao(self):
        with patch('radar_cache_local.construir_payload',return_value=({},None,None)) as construir:
            for cod in ['01','02']:
                local._preparar(dict(cod=cod,role='vendedor',nome='Teste'),self.root,self.root/'m.sqlite3',((),))
        self.assertEqual(construir.call_count,2)

    def test_pdf_identico_e_deduplicado_sem_misturar_escopos(self):
        import radar_pdf as pdf
        pdf._PDF_CACHE.clear()
        base=dict(competencia='2026-10',referenciaCarteira='22/10/2026',periodoCarteiraInicio='01/11/2025')
        item=dict(CodCliFor='C1',Cliente='A',MediaMensal=100)
        with patch('radar_pdf._gerar_pdf',return_value=b'%PDF-teste') as gerar:
            with ThreadPoolExecutor(20) as pool:
                dados=list(pool.map(lambda _:pdf.gerar_pdf(base,[item],['Ana'],'A'),range(20)))
            self.assertEqual(len(dados),20);self.assertEqual(gerar.call_count,1)
            pdf.gerar_pdf(base,[dict(item,CodCliFor='C2')],['Bia'],'A')
            self.assertEqual(gerar.call_count,2)
        pdf._PDF_CACHE.clear()

    def test_leitura_compartilhada_devolve_copias_isoladas(self):
        path=self.root/'dados.parquet';pd.DataFrame({'codigo':['01'],'valor':[10]}).to_parquet(path,index=False)
        real=pd.read_parquet
        with patch('radar_leitura.pd.read_parquet',wraps=real) as read:
            with ThreadPoolExecutor(20) as pool:frames=list(pool.map(lambda _:leitura.ler_parquet(path),range(20)))
            self.assertEqual(read.call_count,1)
        frames[0].loc[0,'valor']=999
        self.assertEqual(frames[1].loc[0,'valor'],10)
        self.assertEqual(leitura.ler_parquet(path).loc[0,'valor'],10)

    def test_troca_atomica_invalida_e_arquivo_ausente_nao_reusa_antigo(self):
        path=self.root/'dados.parquet';pd.DataFrame({'valor':[1]}).to_parquet(path)
        self.assertEqual(leitura.ler_parquet(path).valor.iloc[0],1)
        stat=path.stat()
        novo=self.root/'novo.parquet';pd.DataFrame({'valor':[2]}).to_parquet(novo)
        os.utime(novo,ns=(stat.st_atime_ns,stat.st_mtime_ns));novo.replace(path)
        self.assertEqual(leitura.ler_parquet(path).valor.iloc[0],2)
        path.unlink()
        with self.assertRaises(FileNotFoundError):leitura.ler_parquet(path)

    def test_limite_de_arquivos_em_memoria(self):
        for i in range(20):
            path=self.root/f'{i}.parquet';pd.DataFrame({'v':[i]}).to_parquet(path);leitura.ler_parquet(path)
        self.assertLessEqual(len(leitura._FRAMES),12)

    def test_snapshot_muda_e_uma_nova_leitura_consistente_e_exigida(self):
        user=dict(cod='01',role='vendedor',nome='Ana');estado={}
        with patch('radar_cache_local.assinatura',side_effect=['antiga','nova','nova','nova']),patch('radar_cache_local.construir_payload',side_effect=[('misturado',),('consistente',)]):
            r=local.carregar_local(user,self.root,estado,self.root/'m.sqlite3')
        self.assertEqual(r,('consistente',));self.assertEqual(estado[local.CHAVE][0],'nova')

    def test_atualizacao_continua_nao_publica_snapshot_misturado(self):
        with patch('radar_cache_local.assinatura',side_effect=['a','b','c','d']),patch('radar_cache_local.construir_payload',return_value=('misturado',)):
            with self.assertRaisesRegex(ValueError,'consistente'):
                local.carregar_local(dict(cod='01',role='vendedor',nome='Ana'),self.root,{},self.root/'m.sqlite3')

    def test_duas_pastas_em_threads_nao_trocam_de_base(self):
        barreira=threading.Barrier(2)
        @validado.contexto_cache
        def consultar(user,cache):
            barreira.wait(timeout=5)
            return str(validado.pasta_cache())
        with ThreadPoolExecutor(2) as pool:
            a=pool.submit(consultar,{},self.root/'a');b=pool.submit(consultar,{},self.root/'b')
            self.assertEqual(a.result(),str(self.root/'a'));self.assertEqual(b.result(),str(self.root/'b'))


class MetasConcorrentes(unittest.TestCase):
    def test_20_gravacoes_distintas_e_disputa_da_mesma_meta(self):
        with tempfile.TemporaryDirectory(prefix='radar-metas-carga-') as td:
            path=Path(td)/'metas.sqlite3'
            resp=pd.DataFrame([dict(IdEmpresa=1,CodVendedor=f'{i+100:05}',Tipo='V',CodSupervisor='S') for i in range(20)])
            user=dict(cod='G',role='gestao')
            # Inicializa o esquema antes da barreira, como faz a leitura da tela.
            ler_metas(['00100'],path)
            barreira=threading.Barrier(20)
            def gravar(i):
                barreira.wait(timeout=10)
                return salvar_meta(user,resp,dict(id='carga_distinta_'+str(i).zfill(20),vendedor=f'{i+100:05}',competencia='2026-10',valor='1000,55',versao=0),path)
            with ThreadPoolExecutor(20) as pool:result=list(pool.map(gravar,range(20)))
            self.assertEqual(len(result),20)
            self.assertEqual(len(ler_metas(resp.CodVendedor,path)),20)
            barreira2=threading.Barrier(4)
            def disputar(i):
                barreira2.wait(timeout=10)
                try:
                    salvar_meta(user,resp,dict(id='carga_disputa_'+str(i).zfill(20),vendedor='00100',competencia='2026-10',valor='2000,00',versao=1),path)
                    return 'salva'
                except ValueError:return 'conflito'
            with ThreadPoolExecutor(4) as pool:r=list(pool.map(disputar,range(4)))
            self.assertEqual(r.count('salva'),1);self.assertEqual(r.count('conflito'),3)
            with closing(sqlite3.connect(path)) as db:
                self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
                self.assertEqual(db.execute('SELECT COUNT(*) FROM metas_auditoria').fetchone()[0],21)


if __name__=='__main__':unittest.main()
