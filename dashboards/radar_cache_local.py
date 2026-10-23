"""Reaproveita somente a preparação local, isolada por sessão e identidade."""
from pathlib import Path
from threading import BoundedSemaphore, RLock
import pandas as pd
from radar_dados import construir_payload
from radar_metas import caminho_banco, GESTAO

ARQUIVOS = (
    'carteira_clientes.parquet', 'carteira_historico.parquet',
    'radar_responsaveis.parquet', 'rentabilidade_cronos.parquet',
    'radar_rent_cli.parquet', 'radar_produtos.parquet',
    'orcamentos_abertos.parquet', 'prevendas.parquet',
)
CHAVE = '_radar_preparacao_local_v7_canvas_20261022'
_PREPARACAO = BoundedSemaphore(2)
_NUCLEO_LOCK = RLock()
_NUCLEO_GESTAO = None


def limpar_preparacao():
    global _NUCLEO_GESTAO
    with _NUCLEO_LOCK:
        _NUCLEO_GESTAO = None


def _preparar(usuario, cache, banco, chave):
    """Compartilha só a leitura comercial global, nunca contas, tokens ou permissões.

    A gestão tem o mesmo escopo global; a identidade é reaplicada em novo dict.
    Supervisão e vendedoras continuam preparadas por identidade e autorização.
    Os consumidores não alteram as listas internas; PDFs ordenam sua própria lista.
    """
    global _NUCLEO_GESTAO
    if str(usuario['role']).lower().strip() not in GESTAO:
        return construir_payload(usuario, cache, banco)
    chave_global=(str(Path(cache).resolve()), str(banco.resolve()), chave[1:])
    with _NUCLEO_LOCK:
        if _NUCLEO_GESTAO is None or _NUCLEO_GESTAO[0] != chave_global:
            resultado=construir_payload(usuario, cache, banco)
            # A base não inclui os dados administrativos adicionados pelo entrypoint.
            base=dict(resultado[0]);base.pop('usuario',None)
            _NUCLEO_GESTAO=(chave_global,(base,resultado[1],resultado[2]))
        payload,resp,financeiro=_NUCLEO_GESTAO[1]
        identidade={k:str(usuario[k]).strip() for k in ('cod','nome','role')}
        return dict(payload,usuario=identidade),resp,financeiro


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
    for tentativa in range(2):
        chave = assinatura(usuario, cache, banco)
        anterior = estado.get(CHAVE)
        if anterior is not None and anterior[0] == chave:
            return anterior[1]
        estado.pop(CHAVE, None)
        # Evita picos de RAM quando várias carteiras frias chegam juntas.
        # Navegação e filtros no navegador não passam por esta fila.
        with _PREPARACAO:
            resultado = _preparar(usuario, cache, banco, chave)
        if assinatura(usuario, cache, banco) == chave:
            estado[CHAVE] = (chave, resultado)
            return resultado
    raise ValueError('Arquivos locais mudaram durante a leitura. Aguarde e releia a base para obter uma versão consistente.')
