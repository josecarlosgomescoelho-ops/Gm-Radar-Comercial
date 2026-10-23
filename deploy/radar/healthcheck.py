"""Verificação HTTP do processo. Não abre sessão nem consulta o ERP."""
from urllib.request import urlopen

with urlopen('http://127.0.0.1:8504/_stcore/health',timeout=3) as resposta:
    if resposta.status!=200 or resposta.read().strip()!=b'ok':
        raise SystemExit(1)
