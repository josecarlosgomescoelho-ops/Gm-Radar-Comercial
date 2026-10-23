"""Conexões devem fechar sem depender do coletor de lixo, inclusive no Windows."""
from contextlib import closing
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'dashboards'))
import radar_equipe as equipe
import radar_metas as metas

CONNECT_REAL = sqlite3.connect


class FechamentoSQLite(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='radar-conexoes-teste-')
        self.path = Path(self.tmp.name) / 'metas.sqlite3'
        self.abertas = []
        self.falhar_schema = False
        teste = self

        class ConexaoObservada(sqlite3.Connection):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.fechada = False
                teste.abertas.append(self)  # Mantém referência: GC não pode ocultar vazamentos.

            def close(self):
                super().close()
                self.fechada = True

            def executescript(self, sql):
                if teste.falhar_schema:
                    raise sqlite3.OperationalError('Falha de esquema simulada')
                return super().executescript(sql)

        def conectar(*args, **kwargs):
            return CONNECT_REAL(*args, factory=ConexaoObservada, **kwargs)

        self.patch = patch('sqlite3.connect', side_effect=conectar)
        self.patch.start()
        self.user = dict(role='gestao', cod='G')
        self.resp = pd.DataFrame([
            [1, '01', 'Ana', 'V', '', ''],
            [1, '02', 'Bia', 'V', '', ''],
        ], columns=['IdEmpresa', 'CodVendedor', 'Vendedor', 'Tipo', 'CodSupervisor', 'Supervisor'])

    def tearDown(self):
        self.patch.stop()
        for conn in self.abertas:
            if not conn.fechada:
                conn.close()
        self.tmp.cleanup()

    def conferir_fechadas(self):
        self.assertTrue(self.abertas, 'O teste precisa observar uma conexão real.')
        self.assertTrue(all(c.fechada for c in self.abertas), 'Uma conexão SQLite permaneceu aberta.')

    def test_equipe_fecha_leitura_sem_tabela(self):
        self.path.touch()
        self.assertIsNone(equipe.ler_equipe(self.path))
        self.conferir_fechadas()

    def test_equipe_fecha_gravacao_leitura_idempotencia_e_conflito(self):
        equipe.salvar_equipe(self.user, self.resp, ['01'], 0, self.path)
        self.conferir_fechadas()
        self.assertEqual(equipe.ler_equipe(self.path)['codigos'], ['01'])
        self.conferir_fechadas()
        equipe.salvar_equipe(self.user, self.resp, ['01'], 1, self.path)
        self.conferir_fechadas()
        with self.assertRaisesRegex(ValueError, 'Outra pessoa'):
            equipe.salvar_equipe(self.user, self.resp, ['02'], 0, self.path)
        self.conferir_fechadas()
        with closing(CONNECT_REAL(self.path)) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM radar_equipe_auditoria').fetchone()[0], 1)

    def test_equipe_reverte_e_fecha_quando_auditoria_falha(self):
        equipe.salvar_equipe(self.user, self.resp, ['01'], 0, self.path)
        with closing(CONNECT_REAL(self.path)) as conn, conn:
            conn.execute("""CREATE TRIGGER impedir_auditoria BEFORE INSERT ON radar_equipe_auditoria
                            BEGIN SELECT RAISE(ABORT, 'auditoria indisponivel'); END""")
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'auditoria indisponivel'):
            equipe.salvar_equipe(self.user, self.resp, ['02'], 1, self.path)
        self.conferir_fechadas()
        config = equipe.ler_equipe(self.path)
        self.assertEqual((config['codigos'], config['versao']), (['01'], 1))
        self.conferir_fechadas()

    def test_metas_fecha_conexao_se_inicializacao_do_schema_falhar(self):
        self.falhar_schema = True
        with self.assertRaisesRegex(sqlite3.OperationalError, 'Falha de esquema'):
            metas.ler_metas(['01'], self.path)
        self.conferir_fechadas()

    def test_metas_fecha_leitura_e_reverte_transacao_interrompida(self):
        self.assertEqual(metas.ler_metas(['01'], self.path), {})
        self.conferir_fechadas()
        with self.assertRaisesRegex(RuntimeError, 'interrompida'):
            with metas.conexao(self.path) as conn:
                conn.execute("INSERT INTO metas VALUES(1,'01','2026-10',100,1,'G','teste')")
                raise RuntimeError('transacao interrompida')
        self.conferir_fechadas()
        self.assertEqual(metas.ler_metas(['01'], self.path), {})
        self.conferir_fechadas()


if __name__ == '__main__':
    unittest.main(verbosity=2)
