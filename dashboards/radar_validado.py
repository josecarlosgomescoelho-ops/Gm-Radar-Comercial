"""Validadores e cálculo financeiro preservados da versão conferida com o Cronos."""
import os
from contextvars import ContextVar
from functools import wraps
from radar_leitura import ler_parquet, leitura_validada

_CONTEXTO = ContextVar('radar_base_por_chamada', default=None)

def contexto_cache(func):
    @wraps(func)
    def wrapped(usuario, cache, *args, **kwargs):
        token = _CONTEXTO.set((Path(cache), pd.Timestamp.now(tz='America/Sao_Paulo').date()))
        try:
            return func(usuario, cache, *args, **kwargs)
        finally:
            _CONTEXTO.reset(token)
    return wrapped

def pasta_cache():
    atual = _CONTEXTO.get()
    return atual[0] if atual else CACHE_DIR

def hoje():
    atual = _CONTEXTO.get()
    return atual[1] if atual else HOJE

def snapshot_validado(func):
    @wraps(func)
    def wrapped(versao):
        verificar = _versao_cache_carteira if func.__name__ == '_load_carteira_abc' else _versao_cache_financeiro
        if verificar() != versao:
            raise ValueError('Base local em atualização; releia os arquivos.')
        chave = (func.__name__, str(pasta_cache().resolve()), hoje(), versao)
        resultado = leitura_validada(chave, lambda: func(versao))
        if verificar() != versao:
            raise ValueError('Base local mudou durante a leitura; releia os arquivos.')
        return resultado
    return wrapped

from pathlib import Path
from decimal import Decimal
import numpy as np
import pandas as pd
CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"
HOJE = pd.Timestamp.now(tz="America/Sao_Paulo").date()
VERSAO_FINANCEIRO_CRONOS = 1
def _versao_cache_financeiro():
    p = pasta_cache() / "rentabilidade_cronos.parquet"
    s = p.stat()
    return (s.st_mtime_ns, s.st_size, s.st_ino)

@snapshot_validado
def _load_financeiro_cronos(versao):
    """Recusa esquemas antigos e invalida o cache ao trocar o arquivo."""
    df = ler_parquet(pasta_cache() / "rentabilidade_cronos.parquet")
    meta = {"VersaoFinanceiroCronos", "PeriodoInicio", "PeriodoFimInclusivo",
            "DataReferencia", "AtualizadoEmUTC"}
    dados = {"CodVendedor", "NomeVendedor", "NomeFilial", "IdImagem", "Qtd",
             "ReceitaUnidades", "CustoUnidades", "LucroUnidades",
             "PercRetabilidadeItem", "LinhaFinanceira"}
    if df.empty or not (meta | dados).issubset(df.columns):
        raise ValueError("Cache financeiro ausente ou antigo; execute o ETL atualizado.")
    for coluna in meta:
        if df[coluna].isna().any() or df[coluna].nunique(dropna=False) != 1:
            raise ValueError("Metadados financeiros inconsistentes.")
    if df["VersaoFinanceiroCronos"].ne(VERSAO_FINANCEIRO_CRONOS).any():
        raise ValueError("Versao do financeiro desatualizada.")
    if pd.Timestamp(df["AtualizadoEmUTC"].iloc[0]).tzinfo is None:
        raise ValueError("Horario de atualizacao financeira sem fuso.")
    inicio = pd.Timestamp(df["PeriodoInicio"].iloc[0])
    fim = pd.Timestamp(df["PeriodoFimInclusivo"].iloc[0])
    referencia = pd.Timestamp(df["DataReferencia"].iloc[0])
    if (inicio != referencia.replace(day=1) or fim != referencia
            or referencia != referencia.normalize() or referencia.date() > hoje()
            or (referencia.year, referencia.month) != (hoje().year, hoje().month)):
        raise ValueError("Financeiro de outro periodo; atualize o ETL.")
    if not df["LinhaFinanceira"].isin([True, False]).all():
        raise ValueError("Marcador de linhas financeiras invalido.")
    df["LinhaFinanceira"] = df["LinhaFinanceira"].astype(bool)
    if not df["LinhaFinanceira"].all() and (len(df) != 1 or df["LinhaFinanceira"].any()):
        raise ValueError("Registro financeiro vazio misturado com vendas.")
    for coluna in ["ReceitaUnidades", "CustoUnidades", "LucroUnidades"]:
        if df[coluna].isna().any():
            raise ValueError("Valores financeiros incompletos.")
        df[coluna] = pd.to_numeric(df[coluna], errors="raise").astype("Int64")
        if not df["LinhaFinanceira"].any() and df[coluna].ne(0).any():
            raise ValueError("Periodo sem vendas com valores financeiros.")
    df["Qtd"] = pd.to_numeric(df["Qtd"], errors="raise").astype("Int64")
    df["PercRetabilidadeItem"] = pd.to_numeric(
        df["PercRetabilidadeItem"], errors="raise"
    ).astype("Float64")
    sem_margem = df["PercRetabilidadeItem"].isna()
    if (sem_margem & df["ReceitaUnidades"].ne(0)).any():
        raise ValueError("Margem ausente para receita diferente de zero.")
    if not np.isfinite(df.loc[~sem_margem, "PercRetabilidadeItem"].astype(float)).all():
        raise ValueError("Margem financeira invalida.")
    df["CodVendedor"] = df["CodVendedor"].astype("string").str.strip()
    if _versao_cache_financeiro() != versao:
        raise ValueError("Financeiro em atualizacao; recarregue a pagina.")
    return df

def _resumo_financeiro_cronos(df, vendedores, visao_global=False):
    """Agrega MONEY sem perder casas decimais; respeita a selecao autorizada."""
    linhas = df.loc[df["LinhaFinanceira"]].copy()
    codigos = {str(c).strip() for c in vendedores}
    if not visao_global:
        linhas = linhas.loc[linhas["CodVendedor"].isin(codigos)].copy()
    receita = Decimal(sum(int(v) for v in linhas["ReceitaUnidades"])) / 10000
    custo = Decimal(sum(int(v) for v in linhas["CustoUnidades"])) / 10000
    lucro = Decimal(sum(int(v) for v in linhas["LucroUnidades"])) / 10000
    qtd = linhas["Qtd"].sum(min_count=1) if not linhas.empty else 0
    qtd = None if pd.isna(qtd) else int(qtd)
    margem = (receita - custo) / receita * 100 if receita != 0 else None
    # A linha individual usa o percentual da SQL, inclusive sua aritmetica MONEY.
    # O consolidado usa os totais, como o rodape do relatorio, sem media de margens.
    if not visao_global and len(codigos) == 1 and len(linhas) == 1:
        percentual = linhas["PercRetabilidadeItem"].iloc[0]
        margem = None if pd.isna(percentual) else Decimal(str(percentual))
    return {"receita": receita, "custo": custo, "lucro": lucro,
            "qtd": qtd, "margem": margem, "linhas": linhas}

def _exportar_financeiro_cronos(linhas):
    df = linhas[["CodVendedor", "NomeVendedor", "NomeFilial", "IdImagem", "Qtd"]].copy()
    for origem, destino in [("ReceitaUnidades", "PrecoLiquido"),
                            ("CustoUnidades", "CustoLiqU"),
                            ("LucroUnidades", "ValorRentabilidadeItem")]:
        df[destino] = [format(Decimal(int(v)) / 10000, ".4f") for v in linhas[origem]]
    df["PercRetabilidadeItem"] = linhas["PercRetabilidadeItem"]
    return df

def _versao_cache_carteira():
    paths = [pasta_cache() / "carteira_clientes.parquet", pasta_cache() / "carteira_historico.parquet"]
    return tuple((s.st_mtime_ns, s.st_size, s.st_ino) for s in (p.stat() for p in paths))

@snapshot_validado
def _load_carteira_abc(versoes):
    """Le os dois caches juntos; a versao dos arquivos invalida o cache da tela."""
    df = ler_parquet(pasta_cache() / "carteira_clientes.parquet")
    hist = ler_parquet(pasta_cache() / "carteira_historico.parquet")
    meta = {"SnapshotCarteira", "DataReferencia", "PeriodoInicio", "PeriodoFimExclusivo"}
    cadastro = {
        "IdEmpresa", "CodCliFor", "Cliente", "Telefone", "Celular",
        "CodVendedorCarteira", "VendedorCarteira", "CarteiraVAtiva",
        "TotalPeriodo", "MediaMensal", "QuantidadeMovimentos",
        "CurvaABC", "PosicaoCurva", "QtdClientesCurva",
    }
    movimento = {"IdEmpresa", "CodCliFor", "IdMov", "DtMov", "DataFaturamento", "ValorLiquido"}
    if not (meta | cadastro).issubset(df.columns) or not (meta | movimento).issubset(hist.columns):
        raise ValueError("Caches antigos: execute o ETL com o bloco de carteira atualizado.")
    if df.empty or hist.empty:
        raise ValueError("Cache de carteira vazio.")
    for coluna in meta:
        valores = [t[coluna].drop_duplicates() for t in [df, hist]]
        if any(len(v) != 1 or v.isna().any() for v in valores) or valores[0].iloc[0] != valores[1].iloc[0]:
            raise ValueError("Carteira e historico de atualizacoes diferentes; aguarde o ETL e recarregue.")
    for tabela in [df, hist]:
        if tabela[["IdEmpresa", "CodCliFor"]].isna().any().any() or tabela["IdEmpresa"].ne(1).any():
            raise ValueError("Chaves de carteira invalidas.")
        tabela["CodCliFor"] = tabela["CodCliFor"].astype("string").str.strip()
        if tabela["CodCliFor"].eq("").any():
            raise ValueError("Codigo de cliente vazio no cache.")
    if df.duplicated(["IdEmpresa", "CodCliFor"]).any() or not df["CarteiraVAtiva"].isin([0, 1]).all():
        raise ValueError("Carteira duplicada ou com elegibilidade invalida.")
    df["CarteiraVAtiva"] = df["CarteiraVAtiva"].eq(1)
    df["CodVendedorCarteira"] = df["CodVendedorCarteira"].astype("string").str.strip()
    base = df.loc[df["CarteiraVAtiva"]].copy()
    if base.empty or base["CodVendedorCarteira"].isna().any():
        raise ValueError("Carteira elegivel ausente ou sem responsavel.")
    numeros = ["TotalPeriodo", "MediaMensal", "QuantidadeMovimentos", "PosicaoCurva", "QtdClientesCurva"]
    for coluna in numeros:
        base[coluna] = pd.to_numeric(base[coluna], errors="raise")
    if not np.isfinite(base[numeros].to_numpy(dtype=float)).all():
        raise ValueError("Receita ou classificacao incompleta.")
    n = len(base)
    if (
        base["QtdClientesCurva"].ne(n).any()
        or sorted(base["PosicaoCurva"].tolist()) != list(range(1, n + 1))
        or not np.allclose(base["MediaMensal"], base["TotalPeriodo"] / 12, rtol=0, atol=0.000001)
    ):
        raise ValueError("Media ou ranking global inconsistente.")
    esperado = np.where(base["PosicaoCurva"] <= (n + 4) // 5, "A",
                        np.where(base["PosicaoCurva"] <= (n + 1) // 2, "B", "C"))
    if base["CurvaABC"].isna().any() or not base["CurvaABC"].eq(esperado).all():
        raise ValueError("Cortes da curva global inconsistentes.")
    ordem = base.sort_values(["TotalPeriodo", "CodCliFor"], ascending=[False, True], kind="stable")
    if ordem["PosicaoCurva"].tolist() != list(range(1, n + 1)):
        raise ValueError("Ordem da curva global inconsistente.")

    hist["IdMov"] = pd.to_numeric(hist["IdMov"], errors="raise").astype("Int64")
    hist["ValorLiquido"] = pd.to_numeric(hist["ValorLiquido"], errors="raise").astype(float)
    if not np.isfinite(hist["ValorLiquido"]).all():
        raise ValueError("Receita do historico incompleta.")
    for coluna in ["DataFaturamento", "DtMov"]:
        hist[coluna] = pd.to_datetime(hist[coluna], errors="raise")
    reais = hist["IdMov"].notna()
    if hist.loc[reais].duplicated(["IdEmpresa", "IdMov"]).any():
        raise ValueError("Movimentos duplicados no historico.")
    inicio = pd.Timestamp(df["PeriodoInicio"].iloc[0])
    fim = pd.Timestamp(df["PeriodoFimExclusivo"].iloc[0])
    referencia = pd.Timestamp(df["DataReferencia"].iloc[0])
    if inicio != referencia.replace(day=1) - pd.DateOffset(months=11) or fim != referencia + pd.Timedelta(days=1):
        raise ValueError("Janela do cache diferente dos 12 meses definidos.")
    for coluna in ["DtMov", "DataFaturamento"]:
        if not hist.loc[reais, coluna].between(inicio, fim, inclusive="left").all():
            raise ValueError("Historico fora da janela da carteira.")
    if hist.loc[~reais, "ValorLiquido"].ne(0).any() or hist.loc[~reais, ["DataFaturamento", "DtMov"]].notna().any().any():
        raise ValueError("Registro de cliente sem compra invalido.")
    if set(hist["CodCliFor"]) != set(base["CodCliFor"]):
        raise ValueError("Historico nao cobre a carteira completa.")
    resumo = hist.loc[reais].groupby("CodCliFor").agg(
        ReceitaHistorico=("ValorLiquido", "sum"), MovimentosHistorico=("IdMov", "count")
    )
    conferencia = base.join(resumo, on="CodCliFor")
    if (
        not np.allclose(conferencia["TotalPeriodo"], conferencia["ReceitaHistorico"].fillna(0), rtol=0, atol=0.005)
        or conferencia["QuantidadeMovimentos"].ne(conferencia["MovimentosHistorico"].fillna(0)).any()
    ):
        raise ValueError("Receita ou quantidade diverge entre carteira e historico.")
    if _versao_cache_carteira() != versoes:
        raise ValueError("Atualizacao em andamento; recarregue a pagina em alguns instantes.")
    return df, hist

def q_base_carteira(codigos_vendedores):
    df, hist = _load_carteira_abc(_versao_cache_carteira())
    referencia = pd.Timestamp(df["DataReferencia"].iloc[0]).date()
    if referencia > hoje() or (referencia.year, referencia.month) != (hoje().year, hoje().month):
        raise ValueError("Carteira de outro mes: atualize o ETL antes de analisar o mes atual.")
    codigos = {str(c).strip() for c in codigos_vendedores}
    carteira = df.loc[df["CarteiraVAtiva"] & df["CodVendedorCarteira"].isin(codigos)].copy()
    historico = hist.loc[hist["CodCliFor"].isin(carteira["CodCliFor"])].copy()
    return carteira, historico
