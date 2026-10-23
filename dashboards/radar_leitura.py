"""Reutiliza Parquets comerciais em memória, com limite e invalidação por arquivo.

Não armazena autenticação, permissões, metas ou payloads de outras sessões.
Cada consumidor recebe sua cópia antes de aplicar o recorte autorizado.
"""
from collections import OrderedDict
from pathlib import Path
from threading import RLock

import pandas as pd

_LOCK = RLock()
_FRAMES = OrderedDict()
_VALIDADOS = OrderedDict()
_LIMITE_BYTES = 96 * 1024 * 1024
_LIMITE_ARQUIVOS = 12


def _versao(path):
    s = path.stat()
    return (str(path), s.st_mtime_ns, s.st_size, s.st_ino)


def ler_parquet(path):
    path = Path(path).resolve()
    with _LOCK:
        chave = _versao(path)  # Não devolve dados antigos se o arquivo sumir.
        item = _FRAMES.get(chave)
        if item is None:
            frame = pd.read_parquet(path)
            if _versao(path) != chave:
                raise ValueError('Arquivo local em atualização; releia os arquivos em instantes.')
            tamanho = int(frame.memory_usage(deep=True).sum())
            for antiga in list(_FRAMES):
                if antiga[0] == str(path):
                    del _FRAMES[antiga]
            if tamanho <= _LIMITE_BYTES:
                while _FRAMES and (len(_FRAMES) >= _LIMITE_ARQUIVOS or sum(v[1] for v in _FRAMES.values()) + tamanho > _LIMITE_BYTES):
                    _FRAMES.popitem(last=False)
                _FRAMES[chave] = (frame, tamanho)
        else:
            frame = item[0]
            _FRAMES.move_to_end(chave)
        return frame.copy(deep=True)


def limpar_leitura():
    with _LOCK:
        _FRAMES.clear()
        _VALIDADOS.clear()


def leitura_validada(chave, carregar):
    """Uma validação por snapshot, inclusive quando várias sessões chegam juntas."""
    with _LOCK:
        item = _VALIDADOS.get(chave)
        if item is None:
            resultado = carregar()
            frames = resultado if isinstance(resultado, tuple) else (resultado,)
            tamanho = sum(int(f.memory_usage(deep=True).sum()) for f in frames)
            # Guarda somente versões atuais por pasta e tipo de leitura.
            for antiga in list(_VALIDADOS):
                if antiga[:2] == chave[:2]:
                    del _VALIDADOS[antiga]
            if tamanho <= 64 * 1024 * 1024:
                while _VALIDADOS and (len(_VALIDADOS) >= 4 or sum(v[1] for v in _VALIDADOS.values()) + tamanho > 64 * 1024 * 1024):
                    _VALIDADOS.popitem(last=False)
                _VALIDADOS[chave] = (resultado, tamanho)
        else:
            resultado = item[0]
            _VALIDADOS.move_to_end(chave)
        if isinstance(resultado, tuple):
            return tuple(f.copy(deep=True) for f in resultado)
        return resultado.copy(deep=True)
