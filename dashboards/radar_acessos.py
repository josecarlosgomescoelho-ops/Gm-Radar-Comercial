"""Gestao web de acessos: autorizacao na sessao persistida e alteracoes transacionais."""
import hashlib
import re

import bcrypt
import pandas as pd

from radar_auth_store import AuthStore, AuthConflict, utc_now
from radar_metas import GESTAO
from radar_ordem import ordenar_registros
from radar_equipe import candidatos, ler_equipe, salvar_equipe
from radar_instalacao import informacao_instalacao

PERFIS={'vendedor','supervisor','gestao'}


def _autorizar(conn, usuario):
    token=usuario.get('token','')
    cod=usuario.get('cod','')
    if not isinstance(token,str) or not token or not isinstance(cod,str):
        raise PermissionError('Entre novamente para gerenciar acessos.')
    row=conn.execute('''SELECT u.* FROM auth_users u JOIN auth_sessions s ON u.CodVendedor=s.CodVendedor
        WHERE s.TokenHash=? AND u.CodVendedor=? AND u.Active=1 AND u.FirstLogin=0 AND u.ResetRequired=0
        AND s.AuthVersion=u._AuthVersion AND s.Expiry>?''',
        (hashlib.sha256(token.encode()).hexdigest(),cod,utc_now().isoformat())).fetchone()
    if row is None or row['Role'] not in GESTAO:
        raise PermissionError('Somente a gestao com sessao ativa pode gerenciar acessos.')
    return row


def _catalogo(responsaveis):
    df=responsaveis.loc[responsaveis.Tipo.isin(['V','S']) & ~responsaveis.CodVendedor.isin(['00002','01174'])]
    itens=[dict(codigo=r.CodVendedor,nome=r.Vendedor,perfil='vendedor' if r.Tipo=='V' else 'supervisor',
                supervisor=r.Supervisor if r.Tipo=='V' else '') for r in df.itertuples()]
    return ordenar_registros(itens,'nome','codigo')


def carregar_acessos(usuario,responsaveis,store=None):
    store=store or AuthStore()
    with store.connect() as conn:
        conn.execute('BEGIN')
        actor=_autorizar(conn,usuario)
        # Nenhum hash, token ou filtro pessoal e serializado para o navegador.
        rows=conn.execute('''SELECT CodVendedor,NomeVendedor,Role,Active,FirstLogin,ResetRequired,
                            LastLogin,_AuthVersion FROM auth_users''').fetchall()
        conn.commit()
    contas=[]
    for r in rows:
        last=None if r['LastLogin'] is None else pd.Timestamp(r['LastLogin']).tz_convert('America/Sao_Paulo').strftime('%d/%m/%Y %H:%M')
        contas.append(dict(codigo=r['CodVendedor'],nome=r['NomeVendedor'],perfil=r['Role'],ativo=bool(r['Active']),
            primeiro=bool(r['FirstLogin']),troca=bool(r['ResetRequired']),ultimoLogin=last,versao=int(r['_AuthVersion']),
            editavel=r['Role']!='dev' or actor['Role']=='dev'))
    return dict(contas=ordenar_registros(contas,'nome','codigo'),catalogo=_catalogo(responsaveis),instalacao=informacao_instalacao(store.path))


def _senha_hash(senha):
    if not isinstance(senha,str) or len(senha)<8 or len(senha.encode('utf-8'))>72:
        raise ValueError('A senha provisoria deve ter ao menos 8 caracteres e ate 72 bytes em UTF-8.')
    return bcrypt.hashpw(senha.encode('utf-8'),bcrypt.gensalt()).decode('ascii')


def processar_acesso(usuario,responsaveis,evento,store=None):
    store=store or AuthStore()
    with store.connect() as conn:
        _autorizar(conn,usuario)
    eid=evento.get('id')
    if not isinstance(eid,str) or not re.fullmatch(r'[A-Za-z0-9_-]{16,80}',eid):
        raise ValueError('Identificador da acao invalido.')
    acao=evento.get('acao')
    if acao not in {'criar','atualizar','redefinir'}:
        raise ValueError('Acao de acesso desconhecida.')
    cod=evento.get('codigo')
    if not isinstance(cod,str) or not cod.strip() or cod!=cod.strip() or len(cod)>64:
        raise ValueError('Codigo de login invalido.')
    perfil=evento.get('perfil')
    nome=evento.get('nome')
    if acao in {'criar','atualizar'}:
        if perfil not in PERFIS and not (acao=='atualizar' and perfil=='dev'):
            raise ValueError('Perfil de acesso invalido.')
        if not isinstance(nome,str) or not nome.strip() or len(nome)>256:
            raise ValueError('Informe um nome valido.')
        nome=nome.strip()
    if acao=='criar' and perfil in {'vendedor','supervisor'}:
        registros=[r for r in _catalogo(responsaveis) if r['codigo']==cod and r['perfil']==perfil]
        if len(registros)!=1:
            raise PermissionError('Responsavel fora da equipe atual ou sem vinculo valido para o perfil.')
        nome=registros[0]['nome']
    versao=evento.get('versao')
    if acao!='criar' and (type(versao) is not int or versao<1):
        raise ValueError('Versao da conta invalida. Releia os acessos.')
    if acao=='atualizar' and type(evento.get('ativo')) is not bool:
        raise ValueError('Situacao da conta invalida.')
    hashed=_senha_hash(evento.get('senha')) if acao in {'criar','redefinir'} else None
    with store.connect(True) as conn:
        actor=_autorizar(conn,usuario)
        autor=actor['CodVendedor']
        conn.execute('''CREATE TABLE IF NOT EXISTS auth_admin_events (
            Evento TEXT PRIMARY KEY, Autor TEXT NOT NULL, Alvo TEXT NOT NULL,
            Acao TEXT NOT NULL, Timestamp TEXT NOT NULL)''')
        if conn.execute('SELECT 1 FROM auth_admin_events WHERE Evento=?',(eid,)).fetchone():
            raise AuthConflict('Essa acao ja foi processada. Confira a lista atualizada.')
        alvo=conn.execute('SELECT * FROM auth_users WHERE CodVendedor=?',(cod,)).fetchone()
        if acao=='criar':
            existentes=[r[0] for r in conn.execute('SELECT CodVendedor FROM auth_users')]
            if any(c==cod or (c.isdigit() and cod.isdigit() and int(c)==int(cod)) for c in existentes):
                raise AuthConflict('Esse login ja existe. Use redefinir senha para recuperar o acesso.')
            agora=utc_now().isoformat()
            conn.execute('''INSERT INTO auth_users(CodVendedor,NomeVendedor,Role,PasswordHash,FirstLogin,
                ResetRequired,Active,CreatedAt,LastLogin,LastFilters) VALUES(?,?,?,?,1,1,1,?,NULL,'[]')''',
                (cod,nome,perfil,hashed,agora))
            mensagem='Conta criada. Entregue a senha provisoria a pessoa; ela devera escolher sua senha pessoal ao entrar.'
        else:
            if alvo is None:
                raise ValueError('Conta nao encontrada. Releia a lista de acessos.')
            if alvo['_AuthVersion']!=versao:
                raise AuthConflict('Outra pessoa alterou o acesso. Confira os dados atualizados e tente novamente.')
            if alvo['Role']=='dev' and actor['Role']!='dev':
                raise PermissionError('Esse perfil exige administracao tecnica.')
            if perfil=='dev' and alvo['Role']!='dev':
                raise PermissionError('Esse perfil exige administracao tecnica.')
            if acao=='redefinir':
                if cod==autor:
                    raise PermissionError('Solicite a outro coordenador a redefinicao do seu proprio acesso.')
                conn.execute('''UPDATE auth_users SET PasswordHash=?,ResetRequired=1,
                    _AuthVersion=_AuthVersion+1,_Version=_Version+1 WHERE CodVendedor=?''',(hashed,cod))
                conn.execute('DELETE FROM auth_sessions WHERE CodVendedor=?',(cod,))
                mensagem='Senha provisoria confirmada para o login '+cod+' na base '+informacao_instalacao(store.path)['base']+'. Sessoes encerradas e troca obrigatoria no proximo acesso.'
                if not alvo['Active']:
                    mensagem+=' A conta continua desativada.'
                nome,perfil=alvo['NomeVendedor'],alvo['Role']
            else:
                ativo=evento['ativo']
                if cod==autor and (perfil!=alvo['Role'] or not ativo):
                    raise PermissionError('Voce nao pode retirar seu proprio acesso de gestao nesta tela.')
                if perfil in {'vendedor','supervisor'}:
                    esperados={r['codigo'] for r in _catalogo(responsaveis) if r['perfil']==perfil}
                    # Uma conta antiga fora da equipe ainda pode ser desativada, sem mudar seu perfil.
                    if (ativo or perfil!=alvo['Role']) and cod not in esperados:
                        raise PermissionError('O codigo nao corresponde a equipe atual para esse perfil.')
                if alvo['Role'] in GESTAO and (perfil not in GESTAO or not ativo):
                    outros=conn.execute("SELECT COUNT(*) FROM auth_users WHERE Role IN ('dev','gestao') AND Active=1 AND CodVendedor<>?",(cod,)).fetchone()[0]
                    if outros==0:
                        raise PermissionError('Mantenha ao menos uma conta de gestao ativa.')
                security=int(perfil!=alvo['Role'] or int(ativo)!=alvo['Active'])
                conn.execute('''UPDATE auth_users SET NomeVendedor=?,Role=?,Active=?,
                    _AuthVersion=_AuthVersion+?,_Version=_Version+1 WHERE CodVendedor=?''',
                    (nome,perfil,int(ativo),security,cod))
                if security:conn.execute('DELETE FROM auth_sessions WHERE CodVendedor=?',(cod,))
                mensagem='Perfil e situacao atualizados.'
        store._history(conn,cod,nome,perfil,'web_admin_'+acao+':'+autor)
        conn.execute('INSERT INTO auth_admin_events VALUES(?,?,?,?,?)',(eid,autor,cod,acao,utc_now().isoformat()))
    return mensagem


def carregar_equipe_gestao(usuario,responsaveis,store=None,db_path=None):
    store=store or AuthStore()
    with store.connect() as conn:_autorizar(conn,usuario)
    df=candidatos(responsaveis)
    config=ler_equipe(db_path)
    selecionados=set(config['codigos'] if config else df.CodVendedor)
    pessoas=[dict(codigo=r.CodVendedor,nome=r.Vendedor,supervisor=r.Supervisor or 'Sem supervisor',
        inativo=str(r.Inativo),incluida=r.CodVendedor in selecionados) for r in df.itertuples()]
    return dict(pessoas=ordenar_registros(pessoas,'nome','codigo'),versao=config['versao'] if config else 0)


def processar_equipe_gestao(usuario,responsaveis,evento,store=None,db_path=None):
    store=store or AuthStore()
    with store.connect() as conn:actor=dict(_autorizar(conn,usuario))
    atual=carregar_equipe_gestao(usuario,responsaveis,store,db_path)
    if type(evento.get('versao')) is not int or evento['versao']!=atual['versao']:
        raise AuthConflict('A equipe foi alterada. Confira a lista atualizada.')
    permitidos={p['codigo'] for p in atual['pessoas']}
    cod=evento.get('codigo');acao=evento.get('acao')
    selecionados={p['codigo'] for p in atual['pessoas'] if p['incluida']}
    if acao=='todos':selecionados=permitidos
    elif acao in {'incluir','excluir'} and isinstance(cod,str) and cod in permitidos:
        if acao=='incluir':selecionados.add(cod)
        else:selecionados.discard(cod)
    else:raise ValueError('Acao de equipe invalida.')
    return salvar_equipe(dict(role=actor['Role'],cod=actor['CodVendedor']),responsaveis,sorted(selecionados),atual['versao'],db_path)
