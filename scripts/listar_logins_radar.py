"""Lista somente identificadores e situação de contas locais; não altera acessos."""
from pathlib import Path
import pandas as pd

root = Path(__file__).resolve().parents[1]
arquivo = root / 'cache' / 'usuarios.parquet'
if not arquivo.exists():
    raise SystemExit('Cadastro local não encontrado: ' + str(arquivo))
colunas = ['CodVendedor', 'NomeVendedor', 'Role', 'Active', 'FirstLogin', 'ResetRequired']
df = pd.read_parquet(arquivo, columns=colunas)
df = df.loc[df.Role.astype('string').str.strip().str.lower().isin(['vendedor', 'vendedora'])].copy()
df = df.sort_values('NomeVendedor')
df = df.rename(columns={'CodVendedor':'Login', 'NomeVendedor':'Nome', 'Role':'Perfil',
                        'Active':'Ativa', 'FirstLogin':'PrimeiroAcesso', 'ResetRequired':'TrocaPendente'})
print(df.to_string(index=False) if not df.empty else 'Nenhuma conta de vendedora encontrada neste cache local.')
print('\nO login é o código, incluindo zeros à esquerda. Senhas e tokens não são exibidos.')
