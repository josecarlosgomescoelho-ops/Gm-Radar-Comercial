"""Lista identificadores e situacao das vendedoras na base local SQLite."""
from pathlib import Path
import sys
import sqlite3

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'dashboards'))
from radar_auth_store import AuthStore, AuthError

try:
    df=AuthStore().users(include_hash=False)
    df=df.loc[df.Role.isin(['vendedor','vendedora'])].sort_values('NomeVendedor')
    cols=['CodVendedor','NomeVendedor','Role','Active','FirstLogin','ResetRequired']
    print(df[cols].rename(columns={'CodVendedor':'Login','NomeVendedor':'Nome','Role':'Perfil','Active':'Ativa',
          'FirstLogin':'PrimeiroAcesso','ResetRequired':'TrocaPendente'}).to_string(index=False) if not df.empty else 'Nenhuma conta de vendedora encontrada.')
    print('\nO login e o codigo, incluindo zeros a esquerda. Senhas, hashes e tokens nao sao exibidos.')
except (AuthError,OSError,sqlite3.Error) as exc:
    raise SystemExit('Nao foi possivel consultar as contas: '+str(exc))
