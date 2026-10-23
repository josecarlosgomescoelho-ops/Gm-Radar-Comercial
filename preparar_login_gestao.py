"""Consulta contas de gestao na base local SQLite; nao consulta o Cronos."""
import argparse
from pathlib import Path
import sys
import sqlite3

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'dashboards'))
from radar_auth_store import AuthStore, AuthError


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--criar-local',action='store_true',help='Permite criar gestao_teste somente quando a base inicializada nao tem contas.')
    args=parser.parse_args()
    store=AuthStore()
    df=store.users(include_hash=False)
    gestao=df.loc[df.Role.isin(['gestao','dev'])]
    cols=['CodVendedor','NomeVendedor','Role','Active','FirstLogin','ResetRequired']
    if not df.empty:
        print(gestao[cols].to_string(index=False) if not gestao.empty else 'Nenhuma conta de gestao encontrada. Use o comando de gestao de usuarios para cadastrar explicitamente.')
        return
    if not args.criar_local:
        print('Base inicializada sem contas. Use --criar-local para cadastrar a gestao de teste.')
        return
    sys.path.insert(0,str(ROOT/'scripts'))
    from criar_usuario import criar
    criar('gestao_teste','Gestao (teste local)','gestao',primeiro=False)


if __name__=='__main__':
    try:main()
    except (AuthError,OSError,sqlite3.Error) as exc:raise SystemExit('Nao foi possivel concluir: '+str(exc))
