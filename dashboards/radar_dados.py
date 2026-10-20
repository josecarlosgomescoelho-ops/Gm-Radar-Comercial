"""Adaptador dos caches reais para a interface, com recorte antes da serialização."""
from decimal import Decimal
from datetime import datetime
import json
import math
import re
import pandas as pd
import radar_validado as validado
from radar_metas import autorizados, ler_metas, GESTAO, SUPERVISAO


def numero(v):
    return None if v is None or pd.isna(v) else float(v)


def data_br(v):
    return None if v is None or pd.isna(v) else pd.Timestamp(v).strftime('%d/%m/%Y')


def hora_br(v):
    ts = pd.Timestamp(v)
    if ts.tzinfo is None:
        raise ValueError("Atualização sem fuso horário.")
    return ts.tz_convert('America/Sao_Paulo').strftime('%d/%m/%Y às %H:%M')


def telefone(v):
    s = '' if v is None or pd.isna(v) else re.sub(r'\D', '', str(v))
    if len(s) in (10,11):
        s = '55' + s
    if not re.fullmatch(r'55\d{10,11}', s):
        return ''
    return s


def ler_responsaveis(cache):
    p = cache / 'radar_responsaveis.parquet'
    if not p.exists():
        raise ValueError('Execute o ETL completo atualizado para gerar os vínculos da equipe.')
    df = pd.read_parquet(p)
    cols = {'IdEmpresa','CodVendedor','Vendedor','CodSupervisor','Supervisor','Tipo'}
    if not cols.issubset(df.columns):
        raise ValueError('Cadastro de responsáveis antigo. Execute o ETL completo.')
    for col in cols - {'IdEmpresa'}:
        df[col] = df[col].fillna('').astype(str).str.strip()
    if df.IdEmpresa.ne(1).any() or df.CodVendedor.eq('').any() or df.CodVendedor.duplicated().any():
        raise ValueError('Cadastro de responsáveis inválido.')
    return df


def preparar_clientes(carteira, historico, referencia):
    """Only MultV > 0 counts as a purchase; returns still participate in net revenue."""
    obrig = {'MultiplicadorMov','TipoMov','IdMov','ValorLiquido','DataFaturamento'}
    if not obrig.issubset(historico.columns):
        raise ValueError('Histórico sem identificação de vendas e devoluções. Execute o ETL completo.')
    mes = referencia.replace(day=1)
    dois_meses = mes - pd.DateOffset(months=1)
    reais = historico.loc[historico.IdMov.notna()].copy()
    if reais.MultiplicadorMov.isna().any() or not reais.MultiplicadorMov.map(lambda x: math.isfinite(float(x))).all():
        raise ValueError('Histórico com tipo de movimento incompleto.')
    reais['CodCliFor'] = reais.CodCliFor.astype(str)
    vendas = reais.loc[reais.MultiplicadorMov.gt(0)].sort_values(['DataFaturamento','IdMov'])
    ultimas = {r['CodCliFor']: r for r in vendas.drop_duplicates('CodCliFor', keep='last').to_dict('records')}
    primeiras = {r['CodCliFor']: r for r in vendas.drop_duplicates('CodCliFor', keep='first').to_dict('records')}
    compras_mes = set(vendas.loc[vendas.DataFaturamento.ge(mes), 'CodCliFor'])
    ativos = set(vendas.loc[vendas.DataFaturamento.ge(dois_meses), 'CodCliFor'])
    # Series.sum matches the previous per-customer monthly revenue calculation.
    fat_mes = reais.loc[reais.DataFaturamento.ge(mes)].groupby('CodCliFor').ValorLiquido.agg(lambda x: x.sum()).to_dict()
    reais['Mes'] = reais.DataFaturamento.dt.to_period('M')
    mensais = reais.groupby(['CodCliFor','Mes']).ValorLiquido.sum().to_dict()
    clientes_mov = set(reais.CodCliFor)
    periodos = list(pd.period_range(mes-pd.DateOffset(months=11), mes, freq='M')[::-1])
    result = []
    for row in carteira.to_dict('records'):
        codigo = str(row['CodCliFor'])
        ultima = ultimas.get(codigo)
        primeira = primeiras.get(codigo)
        dias = (referencia - pd.Timestamp(ultima['DataFaturamento']).normalize()).days if ultima is not None else 999
        fat = round(float(fat_mes.get(codigo, 0)), 2)
        media = float(row['MediaMensal'])
        cadastro = row.get('DataCadastro')
        cadastro = None if cadastro is None or pd.isna(cadastro) else pd.Timestamp(cadastro).normalize()
        cadastrado = bool(cadastro is not None and mes <= cadastro <= referencia)
        comprou = codigo in compras_mes
        # "Novo" refers to verified registration, never first observed purchase.
        status = 'NOVO' if cadastrado else 'PERDIDO' if dias >= 120 else 'CRITICO' if dias >= 60 else 'ATENCAO' if not comprou else 'ATIVO'
        meses_ultima = ((referencia.year-ultima['DataFaturamento'].year)*12 + referencia.month-ultima['DataFaturamento'].month) if ultima is not None else None
        historico_mensal = []
        if codigo in clientes_mov:
            historico_mensal = [{'mes':str(periodo),'valor':round(float(mensais.get((codigo,periodo),0)),2),'doc':'Total líquido do mês'} for periodo in periodos]
        # First purchase is only asserted for a registration within our fully covered window.
        primeira_confirmada = cadastrado and primeira is not None and pd.Timestamp(primeira['DataFaturamento']).normalize() >= cadastro
        result.append({
            'CodCliFor':codigo,'Cliente':str(row['Cliente']),
            'CodVendedorCarteira':str(row['CodVendedorCarteira']), 'VendedorCarteira':str(row['VendedorCarteira']),
            'IdEquipe':str(row.get('CodSupervisor','')), 'CurvaABC':str(row['CurvaABC']),
            'CompraNos12Meses':codigo in ultimas, 'Status':status, 'ComprouNoMes':comprou, 'AbaixoMedia':bool(comprou and media>0 and fat<media*.8),
            'FatMesAtual':fat,'MediaMensal':media,'TotalPeriodo':float(row['TotalPeriodo']),
            'UltimaCompra':data_br(ultima['DataFaturamento']) if ultima is not None else None,
            'DiasUltimaCompra':dias,'MesesUltimaCompra':meses_ultima,
            'ValorUltimaCompra':numero(ultima['ValorLiquido']) if ultima is not None else None,
            'AtivoUltimos2Meses':codigo in ativos,
            'CadastradoNoMes':cadastrado,'DataCadastro':data_br(cadastro),
            'PrimeiraCompraData':data_br(primeira['DataFaturamento']) if primeira_confirmada else None,
            'PrimeiraCompraValor':numero(primeira['ValorLiquido']) if primeira_confirmada else None,
            'Celular':telefone(row.get('Celular')),'Telefone':str(row.get('Telefone') or ''),
            'ReceitaEmRisco':media if not comprou and str(row['CurvaABC']) in {'A','B'} else 0,
            'Historico':historico_mensal,
        })
    return result


def documentos(cache, nome, codigos, avisos):
    p = cache / (nome+'.parquet')
    if not p.exists():
        avisos.append(f'{nome}: dados indisponíveis; execute o ETL completo.')
        return None
    df = pd.read_parquet(p)
    required={'IdEmpresa','VersaoDocumentosRadar','CodVendedor','CodCliFor','NumMov','DtMov','ValorLiquido'}
    if not required.issubset(df.columns):
        avisos.append(f'{nome}: cache antigo; execute o ETL completo.')
        return None
    if df.IdEmpresa.ne(1).any() or df.VersaoDocumentosRadar.ne(2).any():
        avisos.append(f'{nome}: cache sem recorte de empresa validado. Execute o ETL completo.')
        return None
    df.CodVendedor=df.CodVendedor.astype('string').str.strip()
    df=df.loc[df.CodVendedor.isin(codigos)].copy()
    result=[]
    for r in df.to_dict('records'):
        nome_cliente = r.get('NomeCliFor',r.get('Cliente',''))
        data=pd.Timestamp(r['DtMov'])
        result.append({'CodVendedor':str(r['CodVendedor']),'CodCliFor':str(r['CodCliFor']).strip(),
                       'NumMov':str(r['NumMov']),'DtMov':data_br(data),
                       'Cliente':str(nome_cliente),'NomeCliFor':str(nome_cliente),
                       'ValorLiquido':numero(r['ValorLiquido']),
                       'DiasAberto':None if pd.isna(data) else max(0,(pd.Timestamp.now(tz='America/Sao_Paulo').date()-data.date()).days)})
    return result


def construir_payload(usuario, cache, db_path=None):
    validado.CACHE_DIR=cache
    validado.HOJE=pd.Timestamp.now(tz='America/Sao_Paulo').date()
    resp=ler_responsaveis(cache)
    permitido=autorizados(usuario,resp)
    vendedores=permitido.loc[permitido.Tipo.eq('V') & ~permitido.CodVendedor.isin(['00002','01174'])].copy()
    if vendedores.empty:
        raise ValueError('Nenhuma vendedora elegível vinculada ao seu perfil. Confira o cadastro de equipe.')
    codigos=set(vendedores.CodVendedor)
    total, historico_total = validado._load_carteira_abc(validado._versao_cache_carteira())
    dia_cache = pd.Timestamp(total.DataReferencia.iloc[0]).date()
    if dia_cache > validado.HOJE or (dia_cache.year, dia_cache.month) != (validado.HOJE.year, validado.HOJE.month):
        raise ValueError('Carteira de outro mês. Confira a base local antes de analisar o mês atual.')
    carteira = total.loc[total.CarteiraVAtiva & total.CodVendedorCarteira.isin(codigos)].copy()
    hist = historico_total.loc[historico_total.CodCliFor.isin(carteira.CodCliFor)].copy()
    if 'VersaoInterfaceCarteira' not in carteira or carteira.VersaoInterfaceCarteira.ne(2).any():
        raise ValueError('Execute o ETL completo desta versão antes de abrir a nova interface.')
    # Empty authorized wallets still need date metadata from validated cache.
    referencia=pd.Timestamp(total.DataReferencia.iloc[0])
    campo = str(total.CampoDataCadastro.iloc[0]) if 'CampoDataCadastro' in total else ''
    competencia=referencia.strftime('%Y-%m')
    metas=ler_metas(codigos,db_path)
    avisos=[]
    if referencia.date()!=validado.HOJE:
        avisos.append('Carteira com dados até '+data_br(referencia)+'. Atualize o ETL para incluir as compras mais recentes.')
    sem_data = not campo or carteira.DataCadastro.isna().any()
    if sem_data:
        avisos.append('Data de cadastro indisponível ou incompleta. Os totais de novos cadastros não serão exibidos como zero.')
    try:
        financeiro=validado._load_financeiro_cronos(validado._versao_cache_financeiro())
        atual_fin=hora_br(financeiro.AtualizadoEmUTC.iloc[0])
        if pd.Timestamp(financeiro.DataReferencia.iloc[0])!=referencia:
            avisos.append('Financeiro e carteira têm datas de referência diferentes. Consulte as duas atualizações.')
    except (ValueError,FileNotFoundError) as e:
        financeiro=None
        atual_fin='Indisponível'
        avisos.append(str(e))
    role=str(usuario['role']).lower().strip()
    if role in GESTAO:
        visao='gestao_geral'
    elif role in SUPERVISAO:
        visao='supervisor_'+str(usuario['cod'])
        # Scope already enforced in Python; group under this supervisor for rendering.
        vendedores['CodSupervisor']=str(usuario['cod'])
        vendedores['Supervisor']=str(usuario['nome'])
    else:
        visao='vendedora_'+str(usuario['cod'])
    vendedoras=[{'CodVendedor':r.CodVendedor,'Nome':r.Vendedor,'IdEquipe':r.CodSupervisor or 'SEM',
                  'Supervisor':r.Supervisor,'PodeMeta':True} for r in vendedores.itertuples()]
    supervisores=[{'IdEquipe':r.CodSupervisor or 'SEM','Nome':r.Supervisor or 'Sem supervisor'}
                  for r in vendedores[['CodSupervisor','Supervisor']].drop_duplicates().itertuples()]
    clientes=preparar_clientes(carteira,hist,referencia)
    for c in clientes:
        c['IdEquipe']=next(v['IdEquipe'] for v in vendedoras if v['CodVendedor']==c['CodVendedorCarteira'])
    # Client profitability is optional, never replaced with invented zeros.
    rp=cache/'radar_rent_cli.parquet'
    if rp.exists():
        rent=pd.read_parquet(rp)
        if {'CodCliFor','CodVendedor','Faturamento','CustoTotal','VersaoRentabilidadeCronos','PeriodoFimExclusivo'}.issubset(rent.columns) and not rent.empty and rent.VersaoRentabilidadeCronos.eq(1).all() and pd.Timestamp(rent.PeriodoFimExclusivo.iloc[0]).to_period('M')==referencia.to_period('M'):
            rent.CodVendedor=rent.CodVendedor.astype('string').str.strip()
            rent=rent.loc[rent.CodVendedor.isin(codigos)]
            rr={(str(r.CodVendedor).strip(),str(r.CodCliFor).strip()):r for r in rent.itertuples()}
            for c in clientes:
                r=rr.get((c['CodVendedorCarteira'],c['CodCliFor']))
                c['RentPerc']=float((r.Faturamento-r.CustoTotal)/r.Faturamento*100) if r is not None and pd.notna(r.Faturamento) and pd.notna(r.CustoTotal) and r.Faturamento!=0 else None
    produtos_path=cache/'radar_produtos.parquet'
    if produtos_path.exists():
        produtos=pd.read_parquet(produtos_path)
        cols={'IdEmpresa','CodCliFor','CodVendedor','Produto','QtdTotal','Frequencia'}
        if cols.issubset(produtos.columns) and produtos.IdEmpresa.eq(1).all():
            produtos.CodVendedor=produtos.CodVendedor.astype('string').str.strip()
            produtos.CodCliFor=produtos.CodCliFor.astype('string').str.strip()
            produtos=produtos.loc[produtos.CodVendedor.isin(codigos)]
            pg={(str(a),str(b)):g.sort_values('Frequencia',ascending=False).head(3)
                for (a,b),g in produtos.groupby(['CodVendedor','CodCliFor'])}
            for c in clientes:
                g=pg.get((c['CodVendedorCarteira'],c['CodCliFor']))
                c['ProdutosHabituais']=[] if g is None else [{'Produto':str(r.Produto),'Frequencia':numero(r.Frequencia),'QtdTotal':numero(r.QtdTotal)} for r in g.itertuples()]
    meses=[str(p) for p in pd.period_range(referencia.to_period('M')-12,referencia.to_period('M')+12,freq='M')]
    registros={}
    for v in vendedoras:
        cod=v['CodVendedor']
        fin=validado._resumo_financeiro_cronos(financeiro,[cod]) if financeiro is not None else None
        for m in meses:
            meta=metas.get((cod,m))
            registros[f'1|{cod}|{m}']={'CodVendedor':cod,'Competencia':m,
                'MetaValor':meta['centavos']/100 if meta else None,'Versao':meta['versao'] if meta else 0,
                'RealizadoMeta':numero(fin['receita']) if fin and m==competencia else None,
                'CustoValido':numero(fin['custo']) if fin and m==competencia else None,
                'RentabilidadePct':numero(fin['margem']) if fin and m==competencia else None,
                'AtualizadoPor':meta['autor'] if meta else None,'AtualizadoEm':hora_br(meta['atualizado']) if meta else None}
    grupos=[sorted(codigos)]+[[v['CodVendedor']] for v in vendedoras]+[
        sorted(v['CodVendedor'] for v in vendedoras if v['IdEquipe']==s['IdEquipe']) for s in supervisores]
    resumos={}
    for codes in grupos:
        linhas=[registros[f'1|{c}|{competencia}'] for c in codes]
        sem=[v for v in vendedoras if v['CodVendedor'] in codes and registros[f"1|{v['CodVendedor']}|{competencia}"]['MetaValor'] is None]
        fin=validado._resumo_financeiro_cronos(financeiro,codes) if financeiro is not None else None
        soma_meta=sum(metas[(c,competencia)]['centavos'] for c in codes if (c,competencia) in metas)/100
        completa=bool(codes) and not sem
        receita=fin['receita'] if fin else None
        pct=float(receita/(Decimal(str(soma_meta)))*100) if receita is not None and completa and soma_meta>0 else None
        resumos['|'.join(codes)]={'somaRealizado':numero(receita),'somaMeta':soma_meta if completa else None,
            'somaMetaParcial':soma_meta,'todasTemMeta':completa,'vendedorasSemMeta':sem,
            'rentabilidadeConsolidada':numero(fin['margem']) if fin else None,
            'percentualMeta':pct,'larguraBarra':max(0,min(100,pct)) if pct is not None else 0,
            'falta':max(0,float(soma_meta)-float(receita)) if completa and receita is not None else None,
            'superou':max(0,float(receita)-float(soma_meta)) if completa and receita is not None else None}
    # Full company financial includes unassigned and inactive report rows, not just active team.
    global_fin=validado._resumo_financeiro_cronos(financeiro,[],True) if role in GESTAO and financeiro is not None else None
    global_data={k:numero(global_fin[k]) for k in ['receita','custo','lucro','margem','qtd']} if global_fin else None
    orcamentos=documentos(cache,'orcamentos_abertos',codigos,avisos)
    prevendas=documentos(cache,'prevendas',codigos,avisos)
    cadastros_mes = [c for c in clientes if c['CadastradoNoMes']]
    clientes_carteira = [c for c in clientes if c['CompraNos12Meses']]
    payload={'usuario':{'cod':str(usuario['cod']),'nome':str(usuario['nome']),'role':role},
        'visao':visao,'competencia':competencia,'mesesMetas':meses,'vendedoras':vendedoras,
        'supervisores':supervisores,'clientes':clientes_carteira,'cadastrosMes':cadastros_mes,
        'periodoCarteiraInicio':data_br(total.PeriodoInicio.iloc[0]),
        'regraCarteira':'Clientes com compra nos 12 meses de calendário do período salvo; responsável atual do cadastro.','financeiro':registros,'resumos':resumos,
        'financeiroGeral':global_data,'cadastroDisponivel':not sem_data,
        'atualizacaoCarteira':hora_br(total.AtualizadoEmUTC.iloc[0]),'atualizacaoFinanceiro':atual_fin,
        'referenciaCarteira':data_br(referencia),'avisos':avisos,
        'documentosDisponiveis':{'orcamentos':orcamentos is not None,'prevendas':prevendas is not None},
        'orcamentos':orcamentos or [], 'prevendas':prevendas or []}
    # Fail before sending non-finite values to JS. No other user's data leaves Python.
    json.dumps(payload,allow_nan=False)
    return payload, resp, financeiro
