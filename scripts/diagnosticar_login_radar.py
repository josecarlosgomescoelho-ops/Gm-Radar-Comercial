"""Diagnostico local de acesso. Nao altera senhas, contas nem consulta o ERP."""
import argparse
import getpass
from pathlib import Path
import sys
import warnings

import bcrypt

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'dashboards'))
from radar_auth_store import AuthStore
from radar_instalacao import informacao_instalacao


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--codigo',required=True)
    p.add_argument('--verificar-senha',action='store_true')
    a=p.parse_args();store=AuthStore()
    info=informacao_instalacao(store.path)
    print('Versao: '+info['versao']+' | Ambiente: '+info['ambiente']+' | Base: '+info['base'])
    print('Python: '+sys.executable)
    print('Projeto: '+str(ROOT))
    print('Base local: '+str(store.path))
    print('Integridade: '+store.status()['integridade'])
    row=store.find_user(a.codigo.strip())
    if row is None:
        print('Login NAO encontrado nesta base. Confirme o endereco e a instalacao em que a conta foi criada.')
        return
    print('Login: '+str(row.CodVendedor)+' | Perfil: '+str(row.Role))
    print('Ativo: '+str(bool(row.Active))+' | Primeiro acesso: '+str(bool(row.FirstLogin))+' | Troca obrigatoria: '+str(bool(row.ResetRequired)))
    with store.connect() as conn:
        history=conn.execute('SELECT Action,Timestamp FROM auth_history WHERE CodVendedor=? ORDER BY Id DESC LIMIT 5',(str(row.CodVendedor),)).fetchall()
    for action,when in history:print('Evento: '+str(action)+' | '+str(when))
    if a.verificar_senha:
        with warnings.catch_warnings():
            warnings.simplefilter('error',getpass.GetPassWarning)
            try:senha=getpass.getpass('Digite a senha para conferir (nao aparece): ')
            except getpass.GetPassWarning:raise ValueError('Use um terminal interativo para nao exibir a senha.')
        try:confere=bcrypt.checkpw(senha.encode('utf-8'),str(row.PasswordHash).encode('ascii'))
        except (ValueError,TypeError):confere=False
        senha=None
        print('Senha confere nesta base: '+('SIM' if confere else 'NAO'))
    print('Senhas, hashes e tokens nao sao exibidos. Sem alteracoes e sem consulta ao Cronos.')


if __name__=='__main__':
    try:main()
    except (KeyboardInterrupt,EOFError):raise SystemExit('Diagnostico encerrado.')
    except Exception as exc:raise SystemExit('Nao foi possivel conferir o acesso: '+str(exc))
