"""Metas em centavos, com autorização, auditoria e controle de concorrência."""
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import os
import re
import sqlite3

GESTAO = {"dev", "gestao"}
SUPERVISAO = {"supervisor", "supervisao"}
ROLES = GESTAO | SUPERVISAO | {"vendedor", "vendedora"}


def autorizados(usuario, responsaveis):
    role, cod = str(usuario.get("role", "")).strip().lower(), str(usuario.get("cod", "")).strip()
    if role not in ROLES or not cod:
        raise PermissionError("Perfil sem autorização para o Radar.")
    r = responsaveis.copy()
    if r.IdEmpresa.ne(1).any() or r.CodVendedor.isna().any() or r.CodVendedor.duplicated().any():
        raise ValueError("Cadastro de responsáveis inconsistente.")
    if role in GESTAO:
        return r
    if role in SUPERVISAO:
        return r.loc[r.CodSupervisor.eq(cod) | r.CodVendedor.eq(cod)].copy()
    return r.loc[r.CodVendedor.eq(cod)].copy()


def centavos(texto):
    """Accept Brazilian format only. Reject ambiguous dots, infinity and overflow."""
    if not isinstance(texto, str) or not re.fullmatch(r"(?:\d+|\d{1,3}(?:\.\d{3})+)(?:,\d{1,2})?", texto.strip()):
        raise ValueError("Use reais no formato 35000,00 ou 35.000,00.")
    valor = Decimal(texto.strip().replace(".", "").replace(",", ".")) * 100
    if not 0 < valor <= 999999999999:
        raise ValueError("A meta deve ser positiva e de até R$ 9.999.999.999,99.")
    return int(valor)


def caminho_banco():
    pasta = Path(os.getenv("RADAR_DATA_DIR", str(Path(__file__).resolve().parent.parent / "data")))
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta / "radar_metas.sqlite3"


@contextmanager
def conexao(path=None):
    conn = sqlite3.connect(str(path or caminho_banco()), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript('''
    CREATE TABLE IF NOT EXISTS metas (
      empresa INTEGER NOT NULL, vendedor TEXT NOT NULL, competencia TEXT NOT NULL,
      centavos INTEGER NOT NULL CHECK(centavos>0), versao INTEGER NOT NULL,
      autor TEXT NOT NULL, atualizado TEXT NOT NULL,
      PRIMARY KEY(empresa,vendedor,competencia));
    CREATE TABLE IF NOT EXISTS metas_auditoria (
      id INTEGER PRIMARY KEY, evento TEXT NOT NULL UNIQUE,
      empresa INTEGER NOT NULL, vendedor TEXT NOT NULL, competencia TEXT NOT NULL,
      anterior INTEGER, novo INTEGER NOT NULL, autor TEXT NOT NULL, atualizado TEXT NOT NULL);
    ''')
    try:
        yield conn
    finally:
        conn.close()


def ler_metas(codigos, path=None):
    codigos = sorted(set(codigos))
    if not codigos:
        return {}
    with conexao(path) as c:
        rows = c.execute("SELECT * FROM metas WHERE empresa=1 AND vendedor IN (" + ",".join("?" for _ in codigos) + ")", codigos).fetchall()
    return {(r["vendedor"], r["competencia"]): dict(r) for r in rows}


def salvar_meta(usuario, responsaveis, evento, path=None):
    # Recompute scope in Python on every write. Never trust the browser's role/seller list.
    role = str(usuario.get("role", "")).strip().lower()
    if role not in GESTAO | SUPERVISAO:
        raise PermissionError("Somente supervisão e gestão podem alterar metas.")
    permitidos = autorizados(usuario, responsaveis)
    permitidos = permitidos.loc[permitidos.Tipo.eq("V") & ~permitidos.CodVendedor.isin(["00002", "01174"])]
    cod = str(evento.get("vendedor", "")).strip()
    if cod not in set(permitidos.CodVendedor):
        raise PermissionError("Vendedora fora da sua equipe ou não elegível para metas.")
    mes = evento.get("competencia", "")
    if not isinstance(mes, str) or not re.fullmatch(r"20\d{2}-(?:0[1-9]|1[0-2])", mes):
        raise ValueError("Mês inválido.")
    versao = evento.get("versao")
    if type(versao) is not int or versao < 0:
        raise ValueError("Versão inválida. Atualize a página.")
    valor = centavos(evento.get("valor"))
    eid = evento.get("id", "")
    if not isinstance(eid, str) or not re.fullmatch(r"[A-Za-z0-9_-]{16,80}", eid):
        raise ValueError("Identificador da alteração inválido.")
    autor = str(usuario["cod"])
    agora = datetime.now(timezone.utc).isoformat()
    with conexao(path) as c:
        c.execute("BEGIN IMMEDIATE")
        try:
            anterior_evento = c.execute("SELECT * FROM metas_auditoria WHERE evento=?", (eid,)).fetchone()
            if anterior_evento:
                if (anterior_evento['autor'], anterior_evento['vendedor'], anterior_evento['competencia'], anterior_evento['novo']) != (autor,cod,mes,valor):
                    raise ValueError("Identificador já utilizado em outra alteração.")
                c.rollback()
                return "Alteração já registrada."
            old = c.execute("SELECT * FROM metas WHERE empresa=1 AND vendedor=? AND competencia=?", (cod,mes)).fetchone()
            if (old['versao'] if old else 0) != versao:
                raise ValueError("Outra pessoa alterou esta meta. Os dados foram recarregados; confira e tente novamente.")
            c.execute('''INSERT INTO metas VALUES(1,?,?,?,?,?,?)
                         ON CONFLICT(empresa,vendedor,competencia) DO UPDATE SET
                         centavos=excluded.centavos,versao=excluded.versao,autor=excluded.autor,atualizado=excluded.atualizado''',
                      (cod,mes,valor,versao+1,autor,agora))
            c.execute("INSERT INTO metas_auditoria(evento,empresa,vendedor,competencia,anterior,novo,autor,atualizado) VALUES(?,1,?,?,?,?,?,?)",
                      (eid,cod,mes,old['centavos'] if old else None,valor,autor,agora))
            c.commit()
        except Exception:
            c.rollback()
            raise
    return "Meta salva no servidor com histórico de alteração."
