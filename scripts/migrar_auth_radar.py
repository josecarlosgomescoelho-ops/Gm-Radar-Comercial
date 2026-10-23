"""Migracao, conferencia e backup locais da autenticacao. Sem conexao ao Cronos."""
import argparse
from datetime import datetime
from pathlib import Path
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'dashboards'))
from radar_auth_store import AuthStore, AuthError, caminho_auth, migrar_parquets


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    g=parser.add_mutually_exclusive_group(required=True)
    g.add_argument('--migrar',action='store_true',help='Migra uma vez; nao reimporta nem substitui uma base ja existente.')
    g.add_argument('--conferir',action='store_true',help='Confere contagens e integridade sem exibir credenciais.')
    g.add_argument('--backup',type=Path,metavar='ARQUIVO',help='Cria um backup consistente do SQLite em um novo arquivo.')
    parser.add_argument('--projeto',type=Path,default=ROOT)
    parser.add_argument('--banco',type=Path,help='Caminho explicito; normalmente use a configuracao do projeto.')
    args=parser.parse_args()
    projeto=args.projeto.resolve();banco=args.banco or caminho_auth(projeto)
    if args.migrar:
        backup=projeto/'backups'/('auth-dados-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
        status,novo=migrar_parquets(projeto,banco,backup)
        print('Migracao concluida.' if novo else 'Base existente preservada; nenhum dado foi reimportado.')
        if novo:print('Backup dos arquivos anteriores: '+str(backup))
    elif args.backup:
        AuthStore(banco).backup(args.backup)
        print('Backup criado e conferido: '+str(args.backup.resolve()))
        return
    else:status=AuthStore(banco).status()
    print('Base local: '+str(banco))
    print('Usuarios: {usuarios} | Sessoes registradas: {sessoes} | Historico: {historico} | Integridade: {integridade}'.format(**status))
    print('Senhas, hashes e tokens nao sao exibidos. Nenhuma consulta ao Cronos foi executada.')


if __name__=='__main__':
    try:main()
    except (AuthError,OSError,sqlite3.Error) as exc:raise SystemExit('OPERACAO INTERROMPIDA: '+str(exc))
