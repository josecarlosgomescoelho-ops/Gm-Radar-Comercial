"""Reaproveita somente a preparação local, isolada por sessão e identidade."""
from pathlib import Path
import pandas as pd
from radar_dados import construir_payload
from radar_metas import caminho_banco

ARQUIVOS = (
    'carteira_clientes.parquet', 'carteira_historico.parquet',
    'radar_responsaveis.parquet', 'rentabilidade_cronos.parquet',
    'radar_rent_cli.parquet', 'radar_produtos.parquet',
    'orcamentos_abertos.parquet', 'prevendas.parquet',
)
CHAVE = '_radar_preparacao_local_v4_equipe_paineis'


def disponivel_local(usuario, cache, estado, db_path=None):
    banco = Path(db_path) if db_path is not None else caminho_banco()
    anterior = estado.get(CHAVE)
    return anterior is not None and anterior[0] == assinatura(usuario, cache, banco)


def assinatura(usuario, cache, banco):
    arquivos = [Path(cache) / nome for nome in ARQUIVOS]
    arquivos += [Path(str(banco) + sufixo) for sufixo in ('', '-wal', '-journal')]
    versoes = []
    for p in arquivos:
        try:
            stat = p.stat()
            versoes.append((str(p.resolve()), stat.st_mtime_ns, stat.st_size, stat.st_ino))
        except FileNotFoundError:
            versoes.append((str(p.resolve()), None))
    identidade = tuple(str(usuario[k]).strip() for k in ('cod', 'role', 'nome'))
    return identidade, str(pd.Timestamp.now(tz='America/Sao_Paulo').date()), tuple(versoes)


def carregar_local(usuario, cache, estado, db_path=None):
    banco = Path(db_path) if db_path is not None else caminho_banco()
    chave = assinatura(usuario, cache, banco)
    anterior = estado.get(CHAVE)
    if anterior is not None and anterior[0] == chave:
        return anterior[1]
    # Auth and current role are checked by the entrypoint before every call.
    estado.pop(CHAVE, None)
    resultado = construir_payload(usuario, cache, banco)
    # A change while reading must not stamp mixed data as the newest snapshot.
    if assinatura(usuario, cache, banco) == chave:
        estado[CHAVE] = (chave, resultado)
    return resultado
