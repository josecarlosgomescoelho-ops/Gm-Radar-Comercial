"""Gestao local de contas. Senhas solicitadas sem eco; nenhuma consulta ao Cronos."""
import argparse
from datetime import datetime
import getpass
from pathlib import Path
import sys
import sqlite3

import bcrypt
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'dashboards'))
from radar_auth_store import AuthStore, AuthError, ROLES


def senha_nova():
    senha=getpass.getpass('Senha inicial (nao sera exibida): ')
    confirma=getpass.getpass('Repita a senha inicial: ')
    if senha!=confirma:raise AuthError('As senhas nao coincidem.')
    if not senha or len(senha.encode('utf-8'))>72:raise AuthError('A senha deve conter de 1 a 72 bytes em UTF-8.')
    return senha


def criar(cod,nome,perfil,primeiro=True):
    if perfil not in ROLES:raise AuthError('Perfil invalido.')
    store=AuthStore()
    if store.find_user(cod) is not None:raise AuthError('Conta existente preservada. Nenhuma senha foi alterada.')
    senha=senha_nova()
    hashed=bcrypt.hashpw(senha.encode('utf-8'),bcrypt.gensalt()).decode()
    store.add_user(dict(CodVendedor=cod,NomeVendedor=nome,Role=perfil,PasswordHash=hashed,
        FirstLogin=primeiro,ResetRequired=False,Active=True,CreatedAt=datetime.now(),LastLogin=pd.NaT,LastFilters='[]'))
    print('Conta criada: '+cod+' | '+nome+' | '+perfil)
    if primeiro:print('A pessoa devera escolher sua senha pessoal no primeiro acesso.')


def listar():
    df=AuthStore().users(include_hash=False)
    cols=['CodVendedor','NomeVendedor','Role','Active','FirstLogin','ResetRequired','LastLogin']
    print(df.sort_values('NomeVendedor')[cols].to_string(index=False) if not df.empty else 'Nenhuma conta cadastrada.')
    print('\nSenhas, hashes e tokens nao sao exibidos.')


def seed():
    # Somente a equipe validada no cache local. Nao cria contas privilegiadas padrao.
    from radar_dados import ler_responsaveis
    resp=ler_responsaveis(ROOT/'cache')
    resp=resp.loc[~resp.CodVendedor.isin(['00002','01174']) & resp.Tipo.isin(['V','S'])]
    store=AuthStore()
    for r in resp.sort_values(['Tipo','Vendedor']).itertuples():
        if store.find_user(r.CodVendedor) is not None:
            print('Conta existente preservada: '+r.CodVendedor)
            continue
        print('\nNova conta: '+r.Vendedor+' ('+r.CodVendedor+')')
        criar(r.CodVendedor,r.Vendedor,'supervisor' if r.Tipo=='S' else 'vendedor')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    g=parser.add_mutually_exclusive_group(required=True)
    g.add_argument('--list',action='store_true',help='Lista identificadores e situacao, sem credenciais.')
    g.add_argument('--seed',action='store_true',help='Cadastra ausentes da equipe local, pedindo uma senha para cada nova conta.')
    g.add_argument('--reset',metavar='COD',help='Exige troca no proximo login; preserva a senha atual e encerra sessoes.')
    g.add_argument('--deactivate',metavar='COD',help='Desativa a conta e revoga suas sessoes.')
    g.add_argument('--activate',metavar='COD',help='Reativa a conta; e necessario entrar novamente.')
    g.add_argument('--create',metavar='COD',help='Cria uma conta com senha digitada no terminal.')
    parser.add_argument('--nome',help='Nome da nova conta.')
    parser.add_argument('--perfil',choices=sorted(ROLES),help='Perfil da nova conta.')
    args=parser.parse_args()
    if args.list:listar()
    elif args.seed:seed()
    elif args.create:
        if not args.nome or not args.perfil:parser.error('--create requer --nome e --perfil.')
        criar(args.create.strip(),args.nome.strip(),args.perfil)
    else:
        cod=(args.reset or args.deactivate or args.activate).strip()
        AuthStore().set_flag(cod,'ResetRequired' if args.reset else 'Active',bool(args.reset or args.activate))
        print('Conta atualizada. Sessoes anteriores revogadas: '+cod)


if __name__=='__main__':
    try:main()
    except (AuthError,OSError,sqlite3.Error) as exc:raise SystemExit('Nao foi possivel concluir: '+str(exc))
