"""Identificacao publica da instalacao; nunca inclui credenciais ou caminhos no navegador."""
import hashlib
import os
from pathlib import Path
import socket

from radar_auth_store import caminho_auth

VERSAO='2026.10.22-r3'


def informacao_instalacao(db_path=None):
    path=Path(db_path or caminho_auth()).resolve()
    base=hashlib.sha256((socket.gethostname()+'|'+str(path)).encode('utf-8')).hexdigest()[:10]
    ambiente=os.getenv('RADAR_AMBIENTE','').strip() or ('Notebook Windows' if os.name=='nt' else 'Servidor Linux')
    return dict(versao=VERSAO,base=base,ambiente=ambiente[:80])


def legenda_instalacao():
    info=informacao_instalacao()
    return f"{info['ambiente']} | Base {info['base']} | Radar {info['versao']}"
