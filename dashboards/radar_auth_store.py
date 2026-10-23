"""Persistencia local de autenticacao. Uma conexao por operacao; escrita transacional."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
from zoneinfo import ZoneInfo

import pandas as pd
from dotenv import dotenv_values

ROOT=Path(__file__).resolve().parents[1]
SP=ZoneInfo('America/Sao_Paulo')
SCHEMA_VERSION=1
APPLICATION_ID=0x474D4131
ROLES={'dev','gestao','supervisor','supervisao','vendedor','vendedora'}
USER_COLUMNS=['CodVendedor','NomeVendedor','Role','PasswordHash','FirstLogin',
              'ResetRequired','Active','CreatedAt','LastLogin','LastFilters']
HISTORY_COLUMNS=['CodVendedor','NomeVendedor','Role','Action','Timestamp']


class AuthError(ValueError):
    pass


class AuthConflict(AuthError):
    pass


def caminho_auth(root=None):
    root=Path(root or ROOT).resolve()
    cfg=dotenv_values(root/'.env',encoding='utf-8-sig')
    explicito=os.getenv('RADAR_AUTH_DB') or cfg.get('RADAR_AUTH_DB')
    if explicito:
        path=Path(explicito).expanduser()
        return (path if path.is_absolute() else root/path).resolve()
    pasta=os.getenv('RADAR_DATA_DIR') or cfg.get('RADAR_DATA_DIR')
    if pasta:
        path=Path(pasta).expanduser()
        path=(path if path.is_absolute() else root/path).resolve()
        if not any('onedrive' in parte.lower() for parte in path.parts):
            return path/'radar_auth.sqlite3'
    if os.name=='nt':
        return Path.home()/'RadarDados'/root.name/'radar_auth.sqlite3'
    return root/'data'/'radar_auth.sqlite3'


def utc_now():
    return datetime.now(timezone.utc)


def utc_text(value):
    if value is None or pd.isna(value):
        return None
    stamp=pd.Timestamp(value)
    if stamp.tzinfo is None:
        stamp=stamp.tz_localize(SP)
    return stamp.tz_convert('UTC').isoformat()


def json_filtros(filtros):
    if not isinstance(filtros,list) or len(filtros)>5000 or any(not isinstance(c,(str,int)) or isinstance(c,bool) for c in filtros):
        raise AuthError('Selecao de filtros invalida.')
    return json.dumps(filtros,ensure_ascii=False)


def validar_usuario(row):
    result={c:row.get(c) for c in USER_COLUMNS}
    for col,limite in [('CodVendedor',64),('NomeVendedor',256),('Role',32)]:
        valor=result[col]
        if not isinstance(valor,str) or not valor.strip() or len(valor)>limite:
            raise AuthError('Cadastro com identificador, nome ou perfil invalido.')
        result[col]=valor.strip()
    if result['Role'] not in ROLES:
        raise AuthError('Perfil desconhecido no cadastro. Revise os perfis antes da migracao.')
    hashed=result['PasswordHash']
    if isinstance(hashed,bytes):
        hashed=hashed.decode('ascii')
    if not isinstance(hashed,str) or not re.fullmatch(r'\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}',hashed):
        raise AuthError('Cadastro com hash de senha ausente ou invalido. Nenhuma conta foi migrada.')
    result['PasswordHash']=hashed
    for col in ['FirstLogin','ResetRequired','Active']:
        value=result[col]
        if value is None or pd.isna(value) or isinstance(value,str) or value not in (True,False,0,1):
            raise AuthError('Cadastro com marcador de acesso invalido.')
        result[col]=int(bool(value))
    for col in ['CreatedAt','LastLogin']:
        result[col]=utc_text(result[col])
    last=result['LastFilters']
    if last is None or pd.isna(last):last=''
    if not isinstance(last,str):raise AuthError('Filtros salvos com formato invalido.')
    if last.strip():json_filtros(json.loads(last))
    result['LastFilters']=last
    return result


def _rows_dataframe(rows,include_hash=True):
    cols=USER_COLUMNS+['_Version','_AuthVersion']
    df=pd.DataFrame([dict(r) for r in rows],columns=cols)
    for col in ['FirstLogin','ResetRequired','Active']:
        df[col]=df[col].astype(bool)
    for col in ['CreatedAt','LastLogin']:
        df[col]=pd.to_datetime(df[col],utc=True,errors='raise',format='ISO8601').dt.tz_convert(SP).dt.tz_localize(None).astype('datetime64[ns]')
    if not include_hash:df=df.drop(columns=['PasswordHash'])
    return df


class AuthStore:
    def __init__(self,path=None):
        self.path=Path(path or caminho_auth()).resolve()

    @contextmanager
    def connect(self,write=False):
        if not self.path.is_file():
            raise AuthError('Base de autenticacao SQLite ausente. Execute a migracao local antes de abrir o Radar.')
        conn=sqlite3.connect(self.path.as_uri()+'?mode=rw',uri=True,timeout=10,isolation_level=None)
        conn.row_factory=sqlite3.Row
        try:
            conn.execute('PRAGMA foreign_keys=ON')
            conn.execute('PRAGMA busy_timeout=10000')
            if conn.execute('PRAGMA application_id').fetchone()[0]!=APPLICATION_ID or conn.execute('PRAGMA user_version').fetchone()[0]!=SCHEMA_VERSION:
                raise AuthError('Base de autenticacao com versao diferente da esperada.')
            if write:
                conn.execute('PRAGMA synchronous=FULL')
                conn.execute('BEGIN IMMEDIATE')
            yield conn
            if write:conn.commit()
        except BaseException:
            if write:conn.rollback()
            raise
        finally:
            conn.close()

    @classmethod
    def inicializar(cls,path):
        path=Path(path).resolve();path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb'):pass
        if os.name!='nt':path.chmod(0o600)
        conn=sqlite3.connect(str(path),isolation_level=None)
        try:
            conn.executescript('''BEGIN IMMEDIATE;
                CREATE TABLE auth_meta(chave TEXT PRIMARY KEY,valor TEXT NOT NULL);
                CREATE TABLE auth_users(
                    CodVendedor TEXT PRIMARY KEY, NomeVendedor TEXT NOT NULL, Role TEXT NOT NULL,
                    PasswordHash TEXT NOT NULL, FirstLogin INTEGER NOT NULL CHECK(FirstLogin IN (0,1)),
                    ResetRequired INTEGER NOT NULL CHECK(ResetRequired IN (0,1)),
                    Active INTEGER NOT NULL CHECK(Active IN (0,1)), CreatedAt TEXT, LastLogin TEXT,
                    LastFilters TEXT NOT NULL DEFAULT '', _Version INTEGER NOT NULL DEFAULT 1,
                    _AuthVersion INTEGER NOT NULL DEFAULT 1);
                CREATE TABLE auth_sessions(
                    TokenHash TEXT PRIMARY KEY, CodVendedor TEXT NOT NULL UNIQUE REFERENCES auth_users(CodVendedor),
                    Expiry TEXT NOT NULL, LastFilters TEXT NOT NULL, AuthVersion INTEGER NOT NULL);
                CREATE TABLE auth_history(
                    Id INTEGER PRIMARY KEY, CodVendedor TEXT NOT NULL, NomeVendedor TEXT NOT NULL,
                    Role TEXT NOT NULL, Action TEXT NOT NULL, Timestamp TEXT NOT NULL);
                CREATE INDEX auth_history_data ON auth_history(Timestamp);
                PRAGMA application_id=1196245297;
                PRAGMA user_version=1;
                COMMIT;''')
            if conn.execute('PRAGMA application_id').fetchone()[0]!=APPLICATION_ID:
                raise AuthError('Identificador de banco incorreto.')
        except BaseException:
            conn.close();path.unlink(missing_ok=True);raise
        else:conn.close()
        return cls(path)

    def enable_wal(self):
        with self.connect() as c:
            if c.execute('PRAGMA journal_mode=WAL').fetchone()[0].lower()!='wal':
                raise AuthError('Nao foi possivel ativar o journal da base local.')

    @staticmethod
    def _history(c,cod,nome,role,action):
        c.execute('INSERT INTO auth_history(CodVendedor,NomeVendedor,Role,Action,Timestamp) VALUES(?,?,?,?,?)',
                  (str(cod),str(nome),str(role),str(action),utc_now().isoformat()))

    def history(self,cod,nome,role,action):
        with self.connect(True) as c:self._history(c,cod,nome,role,action)

    def users(self,include_hash=True):
        with self.connect() as c:rows=c.execute('SELECT * FROM auth_users ORDER BY CodVendedor').fetchall()
        return _rows_dataframe(rows,include_hash)

    def find_user(self,cod):
        if not isinstance(cod,str) or not cod or len(cod)>64:return None
        df=self.users()
        rows=df.loc[df.CodVendedor.eq(cod)]
        if rows.empty and cod.isdigit():
            rows=df.loc[df.CodVendedor.map(lambda v:v.isdigit() and int(v)==int(cod))]
        if len(rows)>1:raise AuthError('Codigo de login ambiguo. Use o codigo completo.')
        return None if rows.empty else rows.iloc[0]

    def add_user(self,row):
        record=validar_usuario(row)
        with self.connect(True) as c:
            cod=record['CodVendedor']
            existentes=[r[0] for r in c.execute('SELECT CodVendedor FROM auth_users')]
            if any(v==cod or (v.isdigit() and cod.isdigit() and int(v)==int(cod)) for v in existentes):
                raise AuthConflict('Ja existe uma conta equivalente a esse codigo. Conta existente preservada.')
            c.execute('INSERT INTO auth_users('+','.join(USER_COLUMNS)+') VALUES('+','.join('?' for _ in USER_COLUMNS)+')',tuple(record[k] for k in USER_COLUMNS))
            self._history(c,cod,record['NomeVendedor'],record['Role'],'account_created')

    @staticmethod
    def _validated(c,row,pending=False):
        atual=c.execute('SELECT * FROM auth_users WHERE CodVendedor=?',(str(row['CodVendedor']),)).fetchone()
        if (atual is None or not atual['Active'] or atual['PasswordHash']!=row['PasswordHash']
                or ('_AuthVersion' in row and int(row['_AuthVersion'])!=atual['_AuthVersion'])):
            raise AuthConflict('A conta foi alterada. Entre novamente para continuar.')
        if not pending and (atual['FirstLogin'] or atual['ResetRequired']):
            raise AuthConflict('A conta exige troca de senha. Entre novamente.')
        return atual

    def login_pending(self,row):
        with self.connect(True) as c:
            atual=self._validated(c,row,True)
            if not (atual['FirstLogin'] or atual['ResetRequired']):raise AuthConflict('Entre novamente para continuar.')
            c.execute('UPDATE auth_users SET LastLogin=?,_Version=_Version+1 WHERE CodVendedor=?',(utc_now().isoformat(),atual['CodVendedor']))
            self._history(c,atual['CodVendedor'],atual['NomeVendedor'],atual['Role'],'login_pending_password_change')

    def create_session(self,row,filtros,expiry):
        token=secrets.token_urlsafe(32);hashed=hashlib.sha256(token.encode()).hexdigest()
        exp=utc_text(expiry)
        if not exp or pd.Timestamp(exp).to_pydatetime()<=utc_now():raise AuthError('Validade da sessao invalida.')
        filtros_json=json_filtros(filtros)
        with self.connect(True) as c:
            atual=self._validated(c,row)
            c.execute('DELETE FROM auth_sessions WHERE CodVendedor=?',(atual['CodVendedor'],))
            c.execute('INSERT INTO auth_sessions VALUES(?,?,?,?,?)',(hashed,atual['CodVendedor'],exp,filtros_json,atual['_AuthVersion']))
            c.execute('UPDATE auth_users SET LastLogin=?,_Version=_Version+1 WHERE CodVendedor=?',(utc_now().isoformat(),atual['CodVendedor']))
            self._history(c,atual['CodVendedor'],atual['NomeVendedor'],atual['Role'],'login_success')
        return token

    def get_session(self,token):
        if not isinstance(token,str) or not 16<=len(token)<=200:return None
        hashed=hashlib.sha256(token.encode()).hexdigest()
        with self.connect() as c:
            row=c.execute('''SELECT s.*,u.NomeVendedor,u.Role FROM auth_sessions s JOIN auth_users u ON u.CodVendedor=s.CodVendedor
                WHERE s.TokenHash=? AND u.Active=1 AND u.FirstLogin=0 AND u.ResetRequired=0
                AND s.AuthVersion=u._AuthVersion''',(hashed,)).fetchone()
        if row is None:return None
        expiry=pd.Timestamp(row['Expiry']).to_pydatetime()
        if utc_now()>=expiry:
            self.remove_session(token,'session_expired');return None
        return pd.Series(dict(token=token,CodVendedor=row['CodVendedor'],NomeVendedor=row['NomeVendedor'],
                              Role=row['Role'],Expiry=expiry,LastFilters=row['LastFilters']))

    def remove_session(self,token,action='logout'):
        if not isinstance(token,str) or not token:return
        hashed=hashlib.sha256(token.encode()).hexdigest()
        with self.connect(True) as c:
            row=c.execute('''SELECT s.CodVendedor,u.NomeVendedor,u.Role FROM auth_sessions s JOIN auth_users u ON u.CodVendedor=s.CodVendedor WHERE TokenHash=?''',(hashed,)).fetchone()
            if row is not None:
                c.execute('DELETE FROM auth_sessions WHERE TokenHash=?',(hashed,))
                self._history(c,row['CodVendedor'],row['NomeVendedor'],row['Role'],action)

    def change_password(self,row,new_hash):
        valid=validar_usuario(dict(row,PasswordHash=new_hash))
        with self.connect(True) as c:
            atual=self._validated(c,row,True)
            if not (atual['FirstLogin'] or atual['ResetRequired']):raise AuthConflict('A troca de senha nao esta mais pendente. Entre novamente.')
            cod=atual['CodVendedor']
            c.execute('UPDATE auth_users SET PasswordHash=?,FirstLogin=0,ResetRequired=0,_AuthVersion=_AuthVersion+1,_Version=_Version+1 WHERE CodVendedor=?',(valid['PasswordHash'],cod))
            c.execute('DELETE FROM auth_sessions WHERE CodVendedor=?',(cod,))
            self._history(c,cod,atual['NomeVendedor'],atual['Role'],'password_changed')
        return self.find_user(cod)

    def set_flag(self,cod,flag,value,actor='cli'):
        if flag not in {'Active','ResetRequired'} or type(value) is not bool:raise AuthError('Alteracao de acesso invalida.')
        with self.connect(True) as c:
            row=c.execute('SELECT NomeVendedor,Role FROM auth_users WHERE CodVendedor=?',(cod,)).fetchone()
            if row is None:raise AuthError('Conta nao encontrada. Use o codigo completo.')
            c.execute(f'UPDATE auth_users SET {flag}=?,_AuthVersion=_AuthVersion+1,_Version=_Version+1 WHERE CodVendedor=?',(int(value),cod))
            c.execute('DELETE FROM auth_sessions WHERE CodVendedor=?',(cod,))
            self._history(c,cod,row['NomeVendedor'],row['Role'],f'admin_{flag}_{int(value)}:{actor}')

    def save_filters(self,cod,filtros,token=''):
        value=json_filtros(filtros)
        with self.connect(True) as c:
            user=c.execute('SELECT Role,Active,FirstLogin,ResetRequired,_AuthVersion FROM auth_users WHERE CodVendedor=?',(cod,)).fetchone()
            if user is None or user['Role'] not in {'dev','gestao'} or not user['Active'] or user['FirstLogin'] or user['ResetRequired']:return
            hashed=hashlib.sha256(token.encode()).hexdigest() if token else None
            if hashed:
                session=c.execute('SELECT Expiry,AuthVersion FROM auth_sessions WHERE TokenHash=? AND CodVendedor=?',(hashed,cod)).fetchone()
                if session is None or session['AuthVersion']!=user['_AuthVersion'] or pd.Timestamp(session['Expiry']).to_pydatetime()<=utc_now():raise AuthConflict('Sessao invalida para salvar filtros.')
            c.execute('UPDATE auth_users SET LastFilters=?,_Version=_Version+1 WHERE CodVendedor=?',(value,cod))
            if hashed:c.execute('UPDATE auth_sessions SET LastFilters=? WHERE TokenHash=?',(value,hashed))

    def save_snapshot(self,df):
        # Compatibilidade com consumidores antigos: exige versao, nunca apaga ausentes.
        if '_Version' not in df:raise AuthConflict('Releia os usuarios antes de salvar. Prefira o comando de gestao atualizado.')
        records=[(validar_usuario(r),r.get('_Version')) for r in df.to_dict('records')]
        if len({r['CodVendedor'] for r,_ in records})!=len(records):raise AuthError('Contas duplicadas na alteracao.')
        with self.connect(True) as c:
            for record,version in records:
                old=c.execute('SELECT * FROM auth_users WHERE CodVendedor=?',(record['CodVendedor'],)).fetchone()
                if old is None:raise AuthConflict('Para cadastrar uma conta, use o comando de criacao atualizado.')
                if any(old[col]!=record[col] for col in USER_COLUMNS):
                    if version is None or pd.isna(version) or int(version)!=old['_Version']:raise AuthConflict('Outro acesso alterou uma conta. Releia os usuarios e tente novamente.')
                    security=any(old[k]!=record[k] for k in ['Role','PasswordHash','Active','FirstLogin','ResetRequired'])
                    cols=[k for k in USER_COLUMNS if k!='CodVendedor']
                    c.execute('UPDATE auth_users SET '+','.join(k+'=?' for k in cols)+',_Version=_Version+1,_AuthVersion=_AuthVersion+? WHERE CodVendedor=?',tuple(record[k] for k in cols)+(int(security),record['CodVendedor']))
                    if security:c.execute('DELETE FROM auth_sessions WHERE CodVendedor=?',(record['CodVendedor'],))
                    self._history(c,record['CodVendedor'],record['NomeVendedor'],record['Role'],'account_updated')

    def status(self):
        with self.connect() as c:
            integrity=c.execute('PRAGMA quick_check').fetchone()[0]
            return dict(usuarios=c.execute('SELECT COUNT(*) FROM auth_users').fetchone()[0],
                        sessoes=c.execute('SELECT COUNT(*) FROM auth_sessions').fetchone()[0],
                        historico=c.execute('SELECT COUNT(*) FROM auth_history').fetchone()[0],integridade=integrity)

    def backup(self,destino):
        destino=Path(destino).resolve();destino.parent.mkdir(parents=True,exist_ok=True)
        with destino.open('xb'):pass
        if os.name!='nt':destino.chmod(0o600)
        try:
            with self.connect() as origem:
                copia=sqlite3.connect(str(destino))
                try:origem.backup(copia)
                finally:copia.close()
            if AuthStore(destino).status()['integridade']!='ok':raise AuthError('Backup nao passou na verificacao de integridade.')
        except BaseException:
            destino.unlink(missing_ok=True);raise
        return destino

    def export_legacy(self,destino):
        """Exporta um snapshot para retorno de versao; sessoes antigas nao sao recriadas."""
        destino=Path(destino).resolve()
        destino.mkdir(parents=True,exist_ok=False)
        if os.name!='nt':destino.chmod(0o700)
        with self.connect() as c:
            c.execute('BEGIN')
            users=c.execute('SELECT * FROM auth_users ORDER BY CodVendedor').fetchall()
            history=c.execute('SELECT CodVendedor,NomeVendedor,Role,Action,Timestamp FROM auth_history ORDER BY Id').fetchall()
            c.commit()
        df=_rows_dataframe(users)[USER_COLUMNS]
        hist=pd.DataFrame([dict(r) for r in history],columns=HISTORY_COLUMNS)
        hist['Timestamp']=pd.to_datetime(hist.Timestamp,utc=True,format='ISO8601').dt.tz_convert(SP).dt.tz_localize(None).astype('datetime64[ns]')
        sessions=pd.DataFrame(columns=['token','CodVendedor','NomeVendedor','Role','Expiry','LastFilters'])
        for name,tabela in [('usuarios',df),('login_historico',hist),('sessions',sessions)]:
            path=destino/(name+'.parquet')
            tabela.to_parquet(path,index=False)
            if os.name!='nt':path.chmod(0o600)
        return destino


def migrar_parquets(projeto,destino,backup):
    projeto=Path(projeto).resolve();destino=Path(destino).resolve();backup=Path(backup).resolve()
    original=projeto/'cache/usuarios.parquet'
    if not original.is_file():raise AuthError('Cadastro usuarios.parquet ausente. Recupere o arquivo local antes de migrar.')
    dados=original.read_bytes();digest=hashlib.sha256(dados).hexdigest()
    if destino.exists():
        store=AuthStore(destino)
        with store.connect() as c:source=c.execute("SELECT valor FROM auth_meta WHERE chave='usuarios_origem_sha256'").fetchone()
        if source is None or source[0]!=digest:raise AuthError('Ja existe uma base de autenticacao com outra origem. Nada foi reimportado.')
        store.enable_wal()
        return store.status(),False
    import io
    usuarios=pd.read_parquet(io.BytesIO(dados))
    if usuarios.empty or set(USER_COLUMNS)!=set(usuarios.columns):raise AuthError('Cadastro de usuarios vazio ou com esquema inesperado.')
    records=[validar_usuario(r) for r in usuarios.to_dict('records')]
    codigos=[r['CodVendedor'] for r in records]
    if len(set(codigos))!=len(codigos):raise AuthError('Existem codigos duplicados no cadastro. Migracao cancelada.')
    equivalentes=[str(int(c)) if c.isdigit() else 'texto:'+c for c in codigos]
    if len(set(equivalentes))!=len(equivalentes):raise AuthError('Existem codigos numericos equivalentes. Revise as contas antes de migrar.')
    backup.mkdir(parents=True,exist_ok=True)
    if os.name!='nt':backup.chmod(0o700)
    snapshots={original:dados}
    historico=projeto/'cache/login_historico.parquet'
    history=[]
    for arquivo in [projeto/'cache/sessions.parquet',historico]:
        if arquivo.exists():snapshots[arquivo]=arquivo.read_bytes()
    if historico in snapshots:
        hist=pd.read_parquet(io.BytesIO(snapshots[historico]))
        if not set(HISTORY_COLUMNS).issubset(hist.columns):raise AuthError('Historico de acessos com esquema inesperado.')
        for r in hist.to_dict('records'):
            data=utc_text(r['Timestamp'])
            if data is None:raise AuthError('Historico com data ausente. Migracao cancelada.')
            history.append(tuple('' if r[k] is None or pd.isna(r[k]) else str(r[k]) for k in HISTORY_COLUMNS[:-1])+(data,))
    for arquivo,conteudo in snapshots.items():
        copia=backup/arquivo.name
        with copia.open('xb') as f:f.write(conteudo)
        if os.name!='nt':copia.chmod(0o600)
    destino.parent.mkdir(parents=True,exist_ok=True)
    temporario=destino.with_name(destino.stem+'.migracao-'+secrets.token_hex(8)+'.sqlite3')
    store=AuthStore.inicializar(temporario)
    publicado=False
    try:
        with store.connect(True) as c:
            c.executemany('INSERT INTO auth_users('+','.join(USER_COLUMNS)+') VALUES('+','.join('?' for _ in USER_COLUMNS)+')',[tuple(r[k] for k in USER_COLUMNS) for r in records])
            c.executemany('INSERT INTO auth_history(CodVendedor,NomeVendedor,Role,Action,Timestamp) VALUES(?,?,?,?,?)',history)
            c.execute('INSERT INTO auth_meta VALUES(?,?)',('usuarios_origem_sha256',digest))
            c.execute('INSERT INTO auth_meta VALUES(?,?)',('migrado_em_utc',utc_now().isoformat()))
            c.execute('INSERT INTO auth_meta VALUES(?,?)',('origem_projeto',str(projeto)))
        result=store.status()
        if result['integridade']!='ok' or result['usuarios']!=len(records) or result['historico']!=len(history):raise AuthError('Falha na conferencia da migracao.')
        roundtrip=store.users().set_index('CodVendedor')
        if any(roundtrip.loc[r['CodVendedor'],'PasswordHash']!=r['PasswordHash'] for r in records):raise AuthError('Falha na conferencia dos hashes. Migracao cancelada.')
        if any(p.read_bytes()!=b for p,b in snapshots.items()):raise AuthConflict('Os arquivos de origem mudaram durante a migracao. Pare todos os processos do Radar e tente novamente.')
        # Reserva exclusiva: uma segunda migracao nao pode sobrescrever a primeira.
        with destino.open('xb'):pass
        try:os.replace(temporario,destino);publicado=True
        except BaseException:
            destino.unlink(missing_ok=True);raise
        AuthStore(destino).enable_wal()
        return result,True
    finally:
        if temporario.exists():temporario.unlink()
        if not publicado:
            for sufixo in ['-wal','-shm','-journal']:
                Path(str(temporario)+sufixo).unlink(missing_ok=True)
