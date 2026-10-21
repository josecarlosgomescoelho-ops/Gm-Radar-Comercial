"""Confere somente os arquivos locais. Nao abre conexao com o Cronos."""
from pathlib import Path
import sys
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'dashboards'))
import radar_validado as validado


def main():
    validado.CACHE_DIR=ROOT/'cache'
    df,hist=validado._load_carteira_abc(validado._versao_cache_carteira())
    if not {'DataCadastro','CampoDataCadastro','RazaoSocial'}.issubset(df.columns):
        raise ValueError('Base anterior a esta atualizacao. Confira a saida do ETL de hoje.')
    if set(df.CampoDataCadastro.dropna().astype(str).str.strip())!={'DataOperacao'}:
        raise ValueError('O cache ainda nao foi gerado com DataOperacao. Confira a configuracao e a saida do ETL.')
    ref=pd.Timestamp(df.DataReferencia.iloc[0])
    datas=pd.to_datetime(df.DataCadastro).dt.normalize()
    mes=datas.between(ref.replace(day=1),ref)
    print('Conferencia LOCAL: carteira e historico pertencem ao mesmo snapshot.')
    print('Referencia: '+ref.strftime('%d/%m/%Y'))
    print('Campo de cadastro: DataOperacao (criterio operacional conferido no Cronos).')
    print('Cadastros do mes com vendedora elegivel:',int((mes & df.CarteiraVAtiva).sum()))
    print('Cadastros do mes fora das carteiras ativas:',int((mes & ~df.CarteiraVAtiva).sum()))
    print('Cadastros ativos com data ausente:',int(datas.isna().sum()))
    print('\nAmostras escolhidas na conferencia:')
    for cod in ['C66635','C66636']:
        linhas=df.loc[df.CodCliFor.eq(cod)]
        if linhas.empty:
            print(cod+': nao encontrado na base ativa da empresa 1.')
            continue
        r=linhas.iloc[0]
        data='ausente' if pd.isna(r.DataCadastro) else pd.Timestamp(r.DataCadastro).strftime('%d/%m/%Y %H:%M:%S')
        dono='' if pd.isna(r.CodVendedorCarteira) else str(r.CodVendedorCarteira).strip()
        print(cod+' | '+str(r.Cliente)+' | '+str(r.RazaoSocial)+' | '+data+' | Responsavel: '+(dono or 'sem responsavel'))
    print('\nEsta verificacao nao executou extracoes.')


if __name__=='__main__':
    try:main()
    except (ValueError,FileNotFoundError,KeyError) as exc:
        print('CONFERENCIA INTERROMPIDA: '+str(exc),file=sys.stderr)
        sys.exit(1)
