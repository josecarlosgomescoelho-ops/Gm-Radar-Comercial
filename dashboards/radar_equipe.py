"""Equipe atual do Radar, escolhida pela gestao sem alterar o cadastro do ERP."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from radar_metas import GESTAO, caminho_banco


def candidatos(responsaveis):
    df=responsaveis.copy()
    if 'Inativo' in df:
        flag=df.Inativo.fillna('').astype(str).str.strip().str.upper()
        if not flag.isin(['N','S']).all():
            raise ValueError('Situacao de atividade desconhecida no cadastro de responsaveis.')
        df=df.loc[flag.eq('N')].copy()
    return df.loc[df.Tipo.eq('V') & ~df.CodVendedor.isin(['00002','01174'])].copy()


def ler_equipe(db_path=None):
    path=Path(db_path) if db_path is not None else caminho_banco()
    if not path.exists():
        return None
    with sqlite3.connect(str(path), timeout=10) as conn:
        if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='radar_equipe'").fetchone() is None:
            return None
        row=conn.execute('SELECT versao, codigos_json, autor, atualizado FROM radar_equipe WHERE empresa=1').fetchone()
    if row is None:
        return None
    codigos=json.loads(row[1])
    if (type(row[0]) is not int or row[0]<1 or not isinstance(codigos,list) or not codigos
            or any(not isinstance(c,str) or not c.strip() or c!=c.strip() for c in codigos)
            or len(set(codigos))!=len(codigos)):
        raise ValueError('Configuracao de equipe invalida. Confira o armazenamento local.')
    return dict(versao=row[0], codigos=codigos, autor=row[2], atualizado=row[3])


def aplicar_equipe(responsaveis, db_path=None):
    config=ler_equipe(db_path)
    if config is None:
        return responsaveis.copy()
    return responsaveis.loc[responsaveis.Tipo.ne('V') | responsaveis.CodVendedor.isin(config['codigos'])].copy()


def salvar_equipe(usuario, responsaveis, codigos, versao, db_path=None):
    if str(usuario.get('role','')).strip().lower() not in GESTAO or not str(usuario.get('cod','')).strip():
        raise PermissionError('Somente a gestao pode definir a equipe do Radar.')
    if type(versao) is not int or versao<0:
        raise ValueError('Versao da equipe invalida.')
    if (not isinstance(codigos,list) or not codigos or any(not isinstance(c,str) or c!=c.strip() or not c for c in codigos)
            or len(set(codigos))!=len(codigos)):
        raise ValueError('Selecione ao menos uma vendedora, sem codigos duplicados.')
    if responsaveis.IdEmpresa.ne(1).any() or responsaveis.CodVendedor.duplicated().any():
        raise ValueError('Cadastro de responsaveis inconsistente.')
    permitidos=set(candidatos(responsaveis).CodVendedor)
    if not set(codigos).issubset(permitidos):
        raise PermissionError('A selecao inclui responsavel ausente, inativo ou nao elegivel no cadastro local.')
    path=Path(db_path) if db_path is not None else caminho_banco()
    path.parent.mkdir(parents=True, exist_ok=True)
    novo=json.dumps(sorted(codigos),ensure_ascii=False)
    agora=datetime.now(timezone.utc).isoformat()
    autor=str(usuario['cod']).strip()
    with sqlite3.connect(str(path), timeout=10) as conn:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute('''CREATE TABLE IF NOT EXISTS radar_equipe (
            empresa INTEGER PRIMARY KEY CHECK(empresa=1), versao INTEGER NOT NULL,
            codigos_json TEXT NOT NULL, autor TEXT NOT NULL, atualizado TEXT NOT NULL)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS radar_equipe_auditoria (
            id INTEGER PRIMARY KEY, empresa INTEGER NOT NULL, versao INTEGER NOT NULL,
            anterior TEXT, novo TEXT NOT NULL, autor TEXT NOT NULL, atualizado TEXT NOT NULL)''')
        atual=conn.execute('SELECT versao,codigos_json FROM radar_equipe WHERE empresa=1').fetchone()
        if (atual[0] if atual else 0)!=versao:
            raise ValueError('Outra pessoa alterou a equipe. Recarregue e confira sua selecao.')
        if atual and atual[1]==novo:
            return 'A equipe ja estava com essa selecao.'
        proxima=versao+1
        conn.execute('INSERT OR REPLACE INTO radar_equipe VALUES(1,?,?,?,?)',(proxima,novo,autor,agora))
        conn.execute('INSERT INTO radar_equipe_auditoria(empresa,versao,anterior,novo,autor,atualizado) VALUES(1,?,?,?,?,?)',
                     (proxima,atual[1] if atual else None,novo,autor,agora))
    return 'Equipe atualizada. Listas, carteiras e metas usam a selecao salva.'
