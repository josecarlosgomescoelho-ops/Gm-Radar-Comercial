#!/usr/bin/env bash
# Inventario de leitura. Nao inicia ETL, nao para processos nem publica codigo.
set -euo pipefail
python3 - "${1:-gm-analytics}" <<'PY'
import json,subprocess,sys,hashlib,pathlib
nome=sys.argv[1]
def cmd(args,timeout=20):
    p=subprocess.run(args,capture_output=True,text=True,timeout=timeout)
    if p.returncode:raise RuntimeError('Comando de leitura falhou: '+args[0])
    return p.stdout
try:
    raw=json.loads(cmd(['docker','inspect',nome]))[0]
    report=dict(container=raw['Name'].lstrip('/'),imagem=raw['Image'],status=raw['State']['Status'],
        saude=raw['State'].get('Health',{}).get('Status','sem healthcheck'),
        portas=raw['NetworkSettings']['Ports'],
        volumes=[{k:m.get(k) for k in ['Type','Source','Destination','RW']} for m in raw.get('Mounts',[])])
    # Config.Env, comandos completos e credenciais nao sao impressos.
    try:report['recursos']=json.loads(cmd(['docker','stats','--no-stream','--format','{{json .}}',nome]))
    except Exception:report['recursos']='Nao foi possivel obter a amostra.'
    codigo=r'''
import os,sys,json,platform,hashlib,pathlib,importlib.metadata,sqlite3,re,subprocess
from datetime import datetime,timezone
roots=[pathlib.Path.cwd(),pathlib.Path('/app'),pathlib.Path('/opt/gm-analytics')]
root=next((p for p in roots if (p/'dashboards/radar_vendedor.py').is_file()),None)
out=dict(python=sys.version.split()[0],sistema=platform.system(),utc=datetime.now(timezone.utc).isoformat(),raiz=str(root) if root else None)
out['bibliotecas']={}
out['processos_streamlit']=[]
for p in pathlib.Path('/proc').glob('[0-9]*/cmdline'):
    try:
        args=p.read_bytes().decode('utf-8',errors='replace').split('\x00')
        if not any('streamlit' in a for a in args):continue
        scripts=[a for a in args if re.fullmatch(r'[\w./-]+\.py',a)]
        portas=[a.split('=',1)[1] for a in args if a.startswith('--server.port=')]
        if '--server.port' in args:portas.append(args[args.index('--server.port')+1])
        out['processos_streamlit'].append(dict(pid=p.parent.name,scripts=scripts,portas=portas))
    except Exception:pass
out['agenda_etl']=[]
try:
    cron=subprocess.run(['crontab','-l'],capture_output=True,text=True,timeout=5)
    for linha in cron.stdout.splitlines():
        partes=linha.split()
        if 'etl_cache.py' in linha and len(partes)>=6 and all(re.fullmatch(r'[0-9*/,-]+',c) for c in partes[:5]):
            out['agenda_etl'].append(' '.join(partes[:5]))
except Exception:pass
for n in ['streamlit','pandas','pyarrow','bcrypt','extra-streamlit-components','python-dotenv']:
    try:out['bibliotecas'][n]=importlib.metadata.version(n)
    except importlib.metadata.PackageNotFoundError:out['bibliotecas'][n]='ausente'
if root:
    out['codigo']={}
    for n in ['dashboards/auth.py','dashboards/radar_vendedor.py','dashboards/radar_auth_store.py','dashboards/radar_instalacao.py','scripts/etl_cache.py']:
        f=root/n;out['codigo'][n]=hashlib.sha256(f.read_bytes()).hexdigest() if f.exists() else 'ausente'
    out['caches']={}
    for n in ['carteira_clientes','carteira_historico','radar_responsaveis','rentabilidade_cronos','usuarios']:
        f=root/'cache'/(n+'.parquet')
        if not f.is_file():out['caches'][n]={'existe':False};continue
        st=f.stat();info=dict(existe=True,bytes=st.st_size,modificado_utc=datetime.fromtimestamp(st.st_mtime,timezone.utc).isoformat())
        try:
            import pyarrow.parquet as pq
            pf=pq.ParquetFile(f);info['linhas']=pf.metadata.num_rows
            if n=='usuarios':info['campos']=pf.schema_arrow.names
            campos=[x for x in ['SnapshotCarteira','DataReferencia','VersaoInterfaceCarteira'] if x in pf.schema_arrow.names]
            if campos:
                tab=pq.read_table(f,columns=campos).to_pydict()
                info['snapshot']={k:sorted({str(v) for v in vals})[:5] for k,vals in tab.items()}
        except Exception:info['metadados']='Falha de leitura; conferir o arquivo.'
        out['caches'][n]=info
    explicit=os.environ.get('RADAR_AUTH_DB')
    data=os.environ.get('RADAR_DATA_DIR')
    db=pathlib.Path(explicit) if explicit else pathlib.Path(data)/'radar_auth.sqlite3' if data else root/'data/radar_auth.sqlite3'
    if not db.is_absolute():db=root/db
    out['auth_sqlite']=dict(caminho=str(db),existe=db.is_file())
    if db.is_file():
        try:
            con=sqlite3.connect(db.resolve().as_uri()+'?mode=ro',uri=True,timeout=5)
            try:
                out['auth_sqlite']['integridade']=con.execute('PRAGMA quick_check').fetchone()[0]
                out['auth_sqlite']['contas']=con.execute('SELECT COUNT(*) FROM auth_users').fetchone()[0]
            finally:con.close()
        except Exception:out['auth_sqlite']['leitura']='Nao foi possivel conferir esta base.'
print(json.dumps(out,ensure_ascii=False,indent=2))
'''
    p=subprocess.run(['docker','exec','-i',nome,'python','-'],input=codigo,capture_output=True,text=True,timeout=30)
    if p.returncode:report['interior_container']='Falha no inventario interno. Confira o caminho e o executavel Python.'
    else:report['interior_container']=json.loads(p.stdout)
    host=pathlib.Path('/opt/gm-analytics')
    report['codigo_host']={}
    for rel in ['dashboards/auth.py','dashboards/radar_vendedor.py','scripts/etl_cache.py']:
        f=host/rel;report['codigo_host'][rel]=hashlib.sha256(f.read_bytes()).hexdigest() if f.is_file() else 'ausente'
    print(json.dumps(report,ensure_ascii=False,indent=2))
except Exception as e:
    print('Inventario nao concluido: '+str(e),file=sys.stderr);raise SystemExit(1)
PY
