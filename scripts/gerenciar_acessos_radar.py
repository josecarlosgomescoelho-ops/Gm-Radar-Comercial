"""Gerenciamento local do Radar: contas e senhas provisorias, sem consultar o ERP."""
import argparse
from datetime import datetime
import getpass
from pathlib import Path
import sqlite3
import sys
import warnings

import bcrypt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'dashboards'))
from radar_auth_store import AuthStore, AuthError

PERFIS = {'vendedor', 'supervisor', 'gestao'}


def senha_provisoria():
    # Impede o fallback de getpass que poderia ecoar a senha em entrada redirecionada.
    with warnings.catch_warnings():
        warnings.simplefilter('error', getpass.GetPassWarning)
        try:
            senha = getpass.getpass('Senha provisoria (nao aparece ao digitar): ')
            confirma = getpass.getpass('Repita a senha provisoria: ')
        except getpass.GetPassWarning as exc:
            raise AuthError('Abra um terminal interativo para digitar a senha sem exibi-la.') from exc
    if senha != confirma:
        raise AuthError('As senhas nao coincidem. Nada foi alterado.')
    if len(senha) < 8 or len(senha.encode('utf-8')) > 72:
        raise AuthError('Use ao menos 8 caracteres e no maximo 72 bytes em UTF-8.')
    return bcrypt.hashpw(senha.encode('utf-8'), bcrypt.gensalt()).decode('ascii')


def listar(store):
    df = store.users(include_hash=False)
    if df.empty:
        print('Nenhuma conta cadastrada.')
        return
    cols = ['CodVendedor', 'NomeVendedor', 'Role', 'Active', 'FirstLogin', 'ResetRequired', 'LastLogin']
    df = df.sort_values(['NomeVendedor', 'CodVendedor'], kind='stable')[cols].copy()
    df = df.rename(columns={'CodVendedor': 'Login', 'NomeVendedor': 'Nome', 'Role': 'Perfil',
                            'Active': 'Acesso ativo', 'FirstLogin': 'Primeiro acesso',
                            'ResetRequired': 'Troca exigida', 'LastLogin': 'Ultimo login'})
    print(df.to_string(index=False))
    print('\nLogin e o codigo completo, incluindo os zeros. Senhas nao sao exibidas.')
    print('Acesso ativo refere-se a conta local, nao a situacao de trabalho no Cronos.')


def equipe_local():
    from radar_dados import ler_responsaveis
    try:
        df = ler_responsaveis(ROOT / 'cache')
    except (ValueError, FileNotFoundError) as exc:
        raise AuthError('Equipe local indisponivel ou incompleta. Confira os arquivos locais antes de cadastrar. Nenhuma extracao foi executada.') from exc
    return df.loc[~df.CodVendedor.isin(['00002', '01174']) & df.Tipo.isin(['V', 'S'])].copy()


def mostrar_equipe():
    df = equipe_local()
    cols = ['CodVendedor', 'Vendedor', 'Tipo', 'CodSupervisor', 'Supervisor']
    print(df.sort_values(['Vendedor', 'CodVendedor'], kind='stable')[cols].to_string(index=False))
    print('\nEquipe obtida dos arquivos locais e da selecao da gestao. Sem consulta ao Cronos.')


def cadastro_equivalente(df, cod):
    exato = df.loc[df.CodVendedor.eq(cod)]
    if not exato.empty:
        return exato
    if cod.isdigit():
        return df.loc[df.CodVendedor.map(lambda x: str(x).isdigit() and int(x) == int(cod))]
    return exato


def criar(store, cod, nome, perfil):
    cod, nome = cod.strip(), nome.strip()
    if not cod or not nome or perfil not in PERFIS:
        raise AuthError('Informe codigo, nome e perfil valido.')
    if store.find_user(cod) is not None:
        raise AuthError('Essa conta ja existe. Para recuperar o acesso, use redefinir senha.')
    if perfil in {'vendedor', 'supervisor'}:
        linhas = cadastro_equivalente(equipe_local(), cod)
        if len(linhas) != 1:
            raise AuthError('Codigo ausente ou ambiguo na equipe local validada. Confira a opcao Equipe.')
        row = linhas.iloc[0]
        esperado = 'V' if perfil == 'vendedor' else 'S'
        if row.Tipo != esperado:
            raise AuthError('O perfil informado difere do tipo do responsavel na equipe local.')
        cod = str(row.CodVendedor)
    hashed = senha_provisoria()
    store.add_user(dict(CodVendedor=cod, NomeVendedor=nome, Role=perfil, PasswordHash=hashed,
        FirstLogin=True, ResetRequired=True, Active=True, CreatedAt=datetime.now(),
        LastLogin=pd.NaT, LastFilters='[]'))
    print('Conta criada: ' + cod + ' | ' + nome + ' | ' + perfil)
    print('A pessoa entra com a senha provisoria e escolhe sua senha pessoal antes de acessar os dados.')


def redefinir(store, cod):
    row = store.find_user(cod.strip())
    if row is None:
        raise AuthError('Conta nao encontrada. Liste os logins antes de continuar.')
    print('Redefinir acesso de: ' + str(row.CodVendedor) + ' | ' + str(row.NomeVendedor))
    novo = senha_provisoria()
    # Apenas esta conta; a versao lida impede sobrescrever uma alteracao concorrente.
    df = row.to_frame().T.copy()
    df.loc[:, 'PasswordHash'] = novo
    df.loc[:, 'ResetRequired'] = True
    store.save_snapshot(df)
    print('Senha provisoria definida. Sessoes anteriores encerradas; troca obrigatoria no proximo login.')
    if not bool(row.Active):
        print('A conta continua desativada. Redefinir senha nao reativa o acesso.')


def situacao(store, cod, ativo):
    row = store.find_user(cod.strip())
    if row is None:
        raise AuthError('Conta nao encontrada.')
    store.set_flag(str(row.CodVendedor), 'Active', ativo)
    print('Acesso local ' + ('ativado' if ativo else 'desativado') + ': ' + str(row.CodVendedor))


def menu(store):
    while True:
        print('\nRADAR - GESTAO LOCAL DE ACESSOS\n1 Listar logins\n2 Consultar equipe local\n3 Criar conta\n4 Redefinir senha esquecida\n5 Desativar acesso\n6 Reativar acesso\n0 Sair')
        opcao = input('Opcao: ').strip()
        try:
            if opcao == '0': return
            if opcao == '1': listar(store)
            elif opcao == '2': mostrar_equipe()
            elif opcao == '3':
                cod = input('Codigo do responsavel (com zeros): ')
                nome = input('Nome: ')
                perfil = input('Perfil [vendedor/supervisor/gestao]: ').strip().lower()
                criar(store, cod, nome, perfil)
            elif opcao == '4': redefinir(store, input('Login a redefinir: '))
            elif opcao in {'5', '6'}: situacao(store, input('Login: '), opcao == '6')
            else: print('Opcao invalida.')
        except (AuthError, OSError, sqlite3.Error) as exc:
            print('Nao foi possivel concluir: ' + str(exc))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument('--listar', action='store_true')
    grupo.add_argument('--equipe', action='store_true')
    grupo.add_argument('--criar', metavar='COD')
    grupo.add_argument('--redefinir', metavar='COD')
    grupo.add_argument('--desativar', metavar='COD')
    grupo.add_argument('--ativar', metavar='COD')
    parser.add_argument('--nome')
    parser.add_argument('--perfil', choices=sorted(PERFIS))
    args = parser.parse_args()
    store = AuthStore()
    if args.listar: listar(store)
    elif args.equipe: mostrar_equipe()
    elif args.criar:
        if not args.nome or not args.perfil: parser.error('--criar requer --nome e --perfil.')
        criar(store, args.criar, args.nome, args.perfil)
    elif args.redefinir: redefinir(store, args.redefinir)
    elif args.desativar: situacao(store, args.desativar, False)
    elif args.ativar: situacao(store, args.ativar, True)
    else: menu(store)


if __name__ == '__main__':
    try:
        main()
    except (AuthError, OSError, sqlite3.Error) as exc:
        raise SystemExit('Nao foi possivel concluir: ' + str(exc))
    except (KeyboardInterrupt, EOFError):
        raise SystemExit('\nOperacao encerrada.')
