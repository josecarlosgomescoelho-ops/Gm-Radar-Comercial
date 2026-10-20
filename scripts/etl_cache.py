"""
GM Limpeza — ETL de Cache Local
Agendado via cron às 01h. Pre-computa os Parquets que o dashboard lê durante o dia.
O banco de produção (Cronos) é consultado apenas uma vez ao dia, fora do horário comercial.

NOLOCK: as consultas legadas usam WITH (NOLOCK) para eliminar lock contention com rotinas
noturnas do ERP (backup, fechamento, reindexação). Dirty reads são aceitáveis neste
contexto — analytics em horário noturno, sem operadores ativos, dado corrigido no ETL
do dia seguinte.
As consultas financeiras Cronos novas usam o isolamento padrao do banco.
rentabilidade_cronos.parquet e recalculado por inteiro para o mes corrente,
incluindo alteracoes e cancelamentos de movimentos ja carregados.

Modo de execução por Parquet:
  FULL LOAD   — Parquet ausente: carrega todo o período histórico.
  INCREMENTAL — Parquet existente: carrega só os registros com DataFaturamento >
                watermark (= MAX(DataFaturamento) do Parquet), faz merge + deduplicação.
  FALLBACK    — Incremental com erro: executa full load automaticamente.
  Tabelas pequenas (vendedores, supervisores) e agregações (radar_produtos,
  radar_rent_cli) são sempre full load — não têm ganho com incremental.

Cron: 0 1 * * * cd /home/vmonteiro/gm-limpeza-analytics && venv/bin/python scripts/etl_cache.py >> logs/etl.log 2>&1
"""

import os
import sys
import logging
import argparse
from decimal import Decimal, InvalidOperation
from uuid import uuid4
import pymssql
import pandas as pd
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

DB_CONFIG = {
    "server":   os.environ["DB_SERVER"],
    "port":     int(os.environ["DB_PORT"]),
    "user":     os.environ["DB_USER"],
    "password": os.environ["DB_PASSWORD"],
    "database": os.environ["DB_NAME"],
}

BASE_DIR  = Path(__file__).parent.parent
CACHE_DIR = BASE_DIR / "cache"
LOG_DIR   = BASE_DIR / "logs"
CACHE_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_DIR / "etl.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)


def get_conn():
    return pymssql.connect(**DB_CONFIG, login_timeout=30, timeout=120, charset="UTF-8")


def _run(nome, sql, conn, mode="FULL LOAD", coerce_float=True):
    t0 = datetime.now()
    logging.info(f"[{nome}] {mode} iniciando...")
    df = pd.read_sql(sql, conn, coerce_float=coerce_float)
    elapsed = (datetime.now() - t0).total_seconds()
    slow = elapsed > 60
    logging.log(
        logging.WARNING if slow else logging.INFO,
        f"[{nome}] {'LENTO — ' if slow else ''}{mode}: {elapsed:.1f}s — {len(df)} linhas",
    )
    return df


def _get_watermark(path: Path, date_col: str):
    """Returns MAX(date_col) from existing Parquet, or None if absent/unreadable."""
    if not path.exists():
        return None
    try:
        wm = pd.read_parquet(path, columns=[date_col])[date_col].max()
        return None if pd.isna(wm) else wm
    except Exception as e:
        logging.warning(f"Watermark indisponível em {path.name}: {e}")
        return None


def _merge_and_save(nome: str, path: Path, df_new: pd.DataFrame,
                    dedup_keys: list, date_col: str, months: int):
    """Appends df_new to existing Parquet, deduplicates, trims to N months, saves."""
    if df_new.empty:
        logging.info(f"[{nome}] 0 linhas novas — Parquet mantido")
        return
    df_old = pd.read_parquet(path)
    df = pd.concat([df_old, df_new], ignore_index=True)
    df = df.drop_duplicates(subset=dedup_keys, keep="last")
    cutoff = pd.Timestamp.now() - pd.DateOffset(months=months)
    df = df[df[date_col].isna() | (df[date_col] >= cutoff)]
    df.to_parquet(path, index=False)
    logging.info(f"[{nome}] merge: {len(df)} linhas no Parquet final")


def _etl_incremental(nome, conn, path, sql_full, sql_inc_tpl,
                     dedup_keys, date_col, months, post_fn=None):
    """
    Executa ETL em modo full ou incremental com fallback automático.
    sql_inc_tpl: SQL com placeholder {watermark} para a data de corte.
    post_fn: callable(df) -> df aplicado após leitura (ex: parse de datas).
    """
    watermark = _get_watermark(path, date_col)

    def _load_full(mode="FULL LOAD"):
        df = _run(nome, sql_full, conn, mode=mode)
        if post_fn:
            df = post_fn(df)
        df.to_parquet(path, index=False)

    if watermark is None:
        _load_full()
        return

    wm_str = watermark.strftime("%Y-%m-%d")
    try:
        df_new = _run(nome, sql_inc_tpl.format(watermark=wm_str), conn,
                      mode=f"INCREMENTAL: watermark={wm_str}")
        if post_fn:
            df_new = post_fn(df_new)
        _merge_and_save(nome, path, df_new, dedup_keys, date_col, months)
    except Exception as e:
        logging.warning(f"[{nome}] incremental falhou ({e}), full load como fallback")
        _load_full(mode="FULL LOAD (fallback)")


# ── ETL functions ─────────────────────────────────────────────────────────────

VERSAO_FINANCEIRO_CRONOS = 1


def _sql_valor_ope():
    """Os 27 argumentos da QueryPrincipal de Rentabilidade por Periodo - GM."""
    return """dbo.fn_ValorItemMov4(
        'OPE', M.IdMov, IM.IdItemMov, IM.IdProduto,
        IM.PrecoUnit, IM.PercDescontoItem, IM.Qtd,
        IM.PercICMS, IM.PercIPI, IM.PercISS, IM.MVAitem,
        M.TipoMov, M.CodCliFor, M.CodFilial, M.CodFilialDest,
        M.CodLocalDest, M.PercDesconto, M.CalculaICMSsubstituto,
        M.DescNaoIncideICMS, IM.IdNaturezaOperacao, IM.SitTributariaItem,
        M.ValorIPIincideICMS, M.ValorFreteIncideICMS,
        IM.PercReducaoBICMS, IM.PercSubICMS,
        IM.ValorItemFrete, IM.ValorItemOutDespesas
    )"""


def _data_cronos(valor=None):
    referencia = (pd.Timestamp.now(tz="America/Sao_Paulo")
                  if valor is None else pd.Timestamp(valor))
    if pd.isna(referencia):
        raise ValueError("Data de referencia invalida.")
    if referencia.tzinfo is not None:
        referencia = referencia.tz_convert("America/Sao_Paulo")
    return pd.Timestamp(referencia.date())


def _money_unidades(valor):
    """MONEY em unidades de 0,0001 real; nao arredonda por nota nem usa float."""
    if pd.isna(valor):
        raise ValueError("Valor financeiro ausente; cache anterior preservado.")
    try:
        unidades = Decimal(str(valor)) * 10000
        if (not unidades.is_finite() or unidades != unidades.to_integral_value()
                or not -(2**63) <= unidades < 2**63):
            raise ValueError("Valor financeiro fora da precisao MONEY.")
        return int(unidades)
    except InvalidOperation as exc:
        raise ValueError("Valor financeiro invalido.") from exc


def _salvar_parquet_atomico(df, path):
    temporario = path.with_name(f"{path.stem}.{uuid4().hex}.tmp.parquet")
    try:
        df.to_parquet(temporario, index=False)
        os.replace(temporario, path)
    finally:
        temporario.unlink(missing_ok=True)


def etl_rentabilidade_cronos(conn, data_referencia=None):
    """Mes ate a referencia, com os filtros e a contagem da QueryPrincipal.

    Preserva inclusive os joins originais sem IdEmpresa e a subconsulta Qtd
    por DtMov, sem os filtros financeiros. Isso permite conferir o relatorio.
    NULLIF apenas torna a margem indisponivel quando a receita e zero.
    Este cache e independente de movimentos.parquet e itens.parquet.
    """
    dia = _data_cronos(data_referencia)
    inicio = dia.replace(day=1)
    valor_ope = _sql_valor_ope()
    receita = "SUM(CONVERT(MONEY, X.Mult * X.ValorOPE))"
    custo = "SUM(CONVERT(MONEY, X.Mult * ISNULL(IM.CustoUnitarioItem * IM.Qtd, 0)))"
    sql = f"""
    DECLARE @DataInicial DATE = '{inicio:%Y%m%d}',
            @DataFinal DATE = '{dia:%Y%m%d}';
    SELECT
        V.CodVendedor,
        V.NomeVendedor,
        F.NomeFilial,
        F.IdImagem,
        Qtd = (
            SELECT SUM(dbo.MultV(M1.TipoMov) * 1)
            FROM Movimento AS M1
            WHERE M1.TipoMov IN ('2.4', '2.8', '2.3', '2.1')
              AND M1.Status NOT IN ('C', 'T')
              AND CONVERT(DATE, M1.DtMov, 103) BETWEEN @DataInicial AND @DataFinal
              AND M1.CodVendedor = V.CodVendedor
        ),
        PrecoLiquido = CONVERT(DECIMAL(19, 4), {receita}),
        CustoLiqU = CONVERT(DECIMAL(19, 4), {custo}),
        PercRetabilidadeItem = CONVERT(NUMERIC(7, 2),
            ({receita} - {custo}) / NULLIF({receita}, 0) * 100),
        ValorRentabilidadeItem = CONVERT(DECIMAL(19, 4), SUM(CONVERT(MONEY, X.Mult * ISNULL(
            (X.ValorOPE - CONVERT(MONEY, ISNULL(IM.CustoUnitarioItem * IM.Qtd, 0))), 0)))),
        ItensSemReceita = COUNT_BIG(*) - COUNT_BIG(X.Mult * X.ValorOPE)
    FROM Movimento AS M
    INNER JOIN ItensMov AS IM ON M.IdMov = IM.IdMov
    INNER JOIN Produtos AS P ON IM.IdProduto = P.IdProduto
    INNER JOIN Filiais AS F ON M.CodFilial = F.CodFilial
    INNER JOIN Cli_For AS CF ON M.CodCliFor = CF.CodCliFor
    LEFT JOIN CondPag AS CP ON M.CodCondPag = CP.CodCondPag
    LEFT JOIN Vendedores AS V ON M.CodVendedor = V.CodVendedor
    CROSS APPLY (SELECT dbo.MultV(M.TipoMov) AS Mult,
                        {valor_ope} AS ValorOPE) AS X
    WHERE M.TipoMov IN ('2.4', '2.8', '2.3', '2.1')
      AND M.Status NOT IN ('C', 'T')
      AND M.CodFilial = '01' AND M.CodLocal = '01'
      AND CONVERT(DATE, M.DataFaturamento, 103) BETWEEN @DataInicial AND @DataFinal
      AND CP.CodCondPag NOT IN ('28', '45', '80', '81', '84', '85')
    GROUP BY F.NomeFilial, F.Cgc, F.IdImagem, V.CodVendedor, V.NomeVendedor
    ORDER BY PrecoLiquido DESC;
    """
    df = _run("rentabilidade_cronos", sql, conn, coerce_float=False).copy()
    obrigatorias = {
        "CodVendedor", "NomeVendedor", "NomeFilial", "IdImagem", "Qtd",
        "PrecoLiquido", "CustoLiqU", "PercRetabilidadeItem",
        "ValorRentabilidadeItem", "ItensSemReceita",
    }
    if not obrigatorias.issubset(df.columns):
        raise ValueError("Consulta Cronos sem as colunas esperadas.")
    problemas = pd.to_numeric(df["ItensSemReceita"], errors="raise")
    if problemas.isna().any() or problemas.ne(0).any():
        raise ValueError("Itens sem receita OPE no financeiro; cache anterior preservado.")
    for origem, destino in [
        ("PrecoLiquido", "ReceitaUnidades"),
        ("CustoLiqU", "CustoUnidades"),
        ("ValorRentabilidadeItem", "LucroUnidades"),
    ]:
        df[destino] = pd.array([_money_unidades(v) for v in df[origem]], dtype="Int64")
    # Qtd ausente e diferente de zero: e o retorno original da subconsulta.
    df["Qtd"] = pd.to_numeric(df["Qtd"], errors="raise").astype("Int64")
    df["PercRetabilidadeItem"] = pd.to_numeric(
        df["PercRetabilidadeItem"], errors="raise"
    ).astype("Float64")
    from math import isfinite
    for receita_u, margem in zip(df["ReceitaUnidades"], df["PercRetabilidadeItem"]):
        if (pd.isna(margem) and receita_u != 0) or (not pd.isna(margem) and not isfinite(margem)):
            raise ValueError("Margem financeira incompleta; cache anterior preservado.")
    df["CodVendedor"] = df["CodVendedor"].astype("string").str.strip()
    df["NomeVendedor"] = df["NomeVendedor"].astype("string").str.strip()
    df = df.drop(columns=["PrecoLiquido", "CustoLiqU", "ValorRentabilidadeItem", "ItensSemReceita"])
    df["LinhaFinanceira"] = True
    if df.empty:
        # Registro de metadados para representar um periodo realmente sem vendas.
        df = pd.DataFrame([{
            "CodVendedor": pd.NA, "NomeVendedor": pd.NA,
            "NomeFilial": pd.NA, "IdImagem": pd.NA, "Qtd": pd.NA,
            "ReceitaUnidades": 0, "CustoUnidades": 0, "LucroUnidades": 0,
            "PercRetabilidadeItem": pd.NA, "LinhaFinanceira": False,
        }])
        for coluna in ["ReceitaUnidades", "CustoUnidades", "LucroUnidades", "Qtd"]:
            df[coluna] = df[coluna].astype("Int64")
        df["PercRetabilidadeItem"] = df["PercRetabilidadeItem"].astype("Float64")
        for coluna in ["CodVendedor", "NomeVendedor", "NomeFilial"]:
            df[coluna] = df[coluna].astype("string")
    df["VersaoFinanceiroCronos"] = VERSAO_FINANCEIRO_CRONOS
    df["PeriodoInicio"] = inicio
    df["PeriodoFimInclusivo"] = dia
    df["DataReferencia"] = dia
    df["AtualizadoEmUTC"] = pd.Timestamp.now(tz="UTC")
    _salvar_parquet_atomico(df, CACHE_DIR / "rentabilidade_cronos.parquet")
    receita_total = sum(int(v) for v in df["ReceitaUnidades"]) / Decimal(10000)
    custo_total = sum(int(v) for v in df["CustoUnidades"]) / Decimal(10000)
    qtd_total = df["Qtd"].sum(min_count=1)
    logging.info(
        "[rentabilidade_cronos] %s a %s; %d linhas; receita=%s; custo=%s; Qtd=%s",
        inicio.date(), dia.date(), int(df["LinhaFinanceira"].sum()),
        receita_total, custo_total, qtd_total,
    )

def _parse_datas(df: pd.DataFrame) -> pd.DataFrame:
    df["DataFaturamento"] = pd.to_datetime(df["DataFaturamento"])
    return df


def etl_movimentos(conn):
    """Faturamento nível movimento (sem ItensMov). 13 meses."""
    path = CACHE_DIR / "movimentos.parquet"

    _base = """
    SELECT
        M.IdMov,
        M.NumMov,
        M.DataFaturamento,
        M.CodCliFor,
        CF.NomeCliFor                                               AS Cliente,
        COALESCE(M.CodVendedor, CF.CodFunc)                        AS CodVendedor,
        V.NomeVendedor                                             AS Vendedor,
        V.CodSupervisor,
        SUP.NomeVendedor                                           AS Supervisor,
        M.TipoMov,
        ISNULL(M.PercDesconto, 0)                                  AS PercDesconto,
        -- TotMov já embute PercDescontoItem (desconto por item, aplicado pelo Cronos antes de salvar).
        -- PercDesconto é o desconto adicional de cabeçalho — único nível não refletido em TotMov.
        -- Validado nota a nota: TotMov * (1 - PercDesconto/100) bate com o sistema ao centavo.
        CASE WHEN M.TipoMov IN ('2.8','2.3') THEN (M.TotMov * (1 - ISNULL(M.PercDesconto, 0)/100.0) * -1) + ISNULL(M.ValorFrete, 0)
             ELSE (M.TotMov * (1 - ISNULL(M.PercDesconto, 0)/100.0)) + ISNULL(M.ValorFrete, 0) END AS ValorLiquido
    FROM Movimento M WITH (NOLOCK)
    INNER JOIN Cli_For CF   WITH (NOLOCK) ON M.CodCliFor = CF.CodCliFor
    LEFT  JOIN Vendedores V WITH (NOLOCK) ON V.CodVendedor = COALESCE(M.CodVendedor, CF.CodFunc)
    LEFT  JOIN Vendedores SUP WITH (NOLOCK) ON SUP.CodVendedor = V.CodSupervisor
    WHERE M.TipoMov IN ('2.4','2.1','2.8','2.3')
      AND M.Status NOT IN ('C','T')
    """
    sql_full = _base + "  AND M.DataFaturamento >= DATEADD(MONTH, -13, GETDATE())"
    sql_inc  = _base + "  AND M.DataFaturamento > '{watermark}'\n  AND M.DataFaturamento <= GETDATE()"

    _etl_incremental("movimentos", conn, path, sql_full, sql_inc,
                     ["IdMov"], "DataFaturamento", 13, _parse_datas)


def etl_itens(conn):
    """Itens de venda com custo e receita por item. 13 meses."""
    path = CACHE_DIR / "itens.parquet"

    _base = """
    SELECT
        IM.IdMov,
        M.DataFaturamento,
        COALESCE(M.CodVendedor, CF.CodFunc)   AS CodVendedor,
        M.CodCliFor,
        P.IdProduto,
        P.NOMEPRODUTO                          AS Produto,
        ISNULL(G.NomeGrupo, 'Sem Grupo')       AS Grupo,
        IM.Qtd,
        IM.PrecoUnit                                                                AS ValorUnitario,
        IM.CustoUnitarioItem,
        IM.Qtd * IM.PrecoUnit * (1 - ISNULL(IM.PercDescontoItem, 0) / 100.0)      AS ReceitaItem,
        IM.Qtd * IM.CustoUnitarioItem                                              AS CustoItem
    FROM ItensMov IM WITH (NOLOCK)
    INNER JOIN Movimento M  WITH (NOLOCK) ON IM.IdMov    = M.IdMov
    INNER JOIN Cli_For CF   WITH (NOLOCK) ON M.CodCliFor = CF.CodCliFor
    INNER JOIN Produtos P   WITH (NOLOCK) ON IM.IdProduto = P.IdProduto
    LEFT  JOIN Grupos G     WITH (NOLOCK) ON P.IdGrupo   = G.IdGrupo
    WHERE M.TipoMov IN ('2.4','2.1')
      AND M.Status NOT IN ('C','T')
      AND IM.StatusItemMov NOT IN ('C')
    """
    sql_full = _base + "  AND M.DataFaturamento >= DATEADD(MONTH, -13, GETDATE())"
    sql_inc  = _base + "  AND M.DataFaturamento > '{watermark}'\n  AND M.DataFaturamento <= GETDATE()"

    _etl_incremental("itens", conn, path, sql_full, sql_inc,
                     ["IdMov", "IdProduto"], "DataFaturamento", 13, _parse_datas)


def etl_radar_clientes(conn):
    """Histórico de compras de todos os clientes de todos os vendedores. 12 meses."""
    path = CACHE_DIR / "radar_clientes.parquet"

    # Full load: usa CF.CodFunc (vendedor cadastrado no cliente) para atribuir a carteira.
    # KPIs de faturamento usam movimentos.parquet (COALESCE) — aqui só interessa a carteira cadastral.
    # LEFT JOIN mantém clientes sem compras no período (PERDIDO).
    sql_full = """
    ;WITH Compras AS (
        SELECT
            M.CodCliFor,
            CF.CodFunc AS CodVendedor,
            CF.NomeCliFor   AS Cliente,
            CF.FoneCliFor   AS Telefone,
            CF.CelCliFor    AS Celular,
            M.TipoMov,
            M.DataFaturamento,
            M.IdMov,
            -- TotMov já embute PercDescontoItem (desconto por item, aplicado pelo Cronos antes de salvar).
            -- PercDesconto é o desconto adicional de cabeçalho — único nível não refletido em TotMov.
            -- Validado nota a nota: TotMov * (1 - PercDesconto/100) bate com o sistema ao centavo.
            CASE WHEN M.TipoMov IN ('2.8','2.3') THEN (M.TotMov * (1 - ISNULL(M.PercDesconto, 0)/100.0) * -1) + ISNULL(M.ValorFrete, 0)
                 ELSE (M.TotMov * (1 - ISNULL(M.PercDesconto, 0)/100.0)) + ISNULL(M.ValorFrete, 0) END AS ValorLiquido
        FROM Movimento M WITH (NOLOCK)
        INNER JOIN Cli_For CF WITH (NOLOCK) ON M.CodCliFor = CF.CodCliFor
        WHERE CF.Inativo = 'N'
          AND M.DataFaturamento >= DATEADD(MONTH, -12, GETDATE())
          AND M.TipoMov IN ('2.4','2.1','2.8','2.3')
          AND M.Status NOT IN ('C','T')
    ),
    CarteiraCadastro AS (
        SELECT CF.CodCliFor, CF.CodFunc AS CodVendedor
        FROM Cli_For CF WITH (NOLOCK)
        WHERE CF.Inativo = 'N' AND CF.CodFunc IS NOT NULL
    ),
    Carteira AS (
        SELECT CodCliFor, CodVendedor FROM CarteiraCadastro
        UNION
        SELECT CodCliFor, CodVendedor FROM Compras WHERE CodVendedor IS NOT NULL
    ),
    ClientesInfo AS (
        SELECT CF.CodCliFor, CF.NomeCliFor AS Cliente,
               CF.FoneCliFor AS Telefone, CF.CelCliFor AS Celular
        FROM Cli_For CF WITH (NOLOCK) WHERE CF.Inativo = 'N'
    )
    SELECT
        CA.CodCliFor, CI.Cliente, CI.Telefone, CI.Celular, CA.CodVendedor,
        C.TipoMov, C.DataFaturamento, C.IdMov, ISNULL(C.ValorLiquido, 0) AS ValorLiquido
    FROM Carteira CA
    INNER JOIN ClientesInfo CI ON CA.CodCliFor = CI.CodCliFor
    LEFT JOIN Compras C ON CA.CodCliFor = C.CodCliFor AND CA.CodVendedor = C.CodVendedor
    """

    # Incremental: só movimentos novos. CodVendedor = CF.CodFunc (carteira cadastral).
    sql_inc = """
    SELECT
        M.CodCliFor,
        CF.CodFunc AS CodVendedor,
        CF.NomeCliFor   AS Cliente,
        CF.FoneCliFor   AS Telefone,
        CF.CelCliFor    AS Celular,
        M.TipoMov,
        M.DataFaturamento,
        M.IdMov,
        -- TotMov já embute PercDescontoItem (desconto por item, aplicado pelo Cronos antes de salvar).
        -- PercDesconto é o desconto adicional de cabeçalho — único nível não refletido em TotMov.
        -- Validado nota a nota: TotMov * (1 - PercDesconto/100) bate com o sistema ao centavo.
        CASE WHEN M.TipoMov IN ('2.8','2.3') THEN (M.TotMov * (1 - ISNULL(M.PercDesconto, 0)/100.0) * -1) + ISNULL(M.ValorFrete, 0)
             ELSE (M.TotMov * (1 - ISNULL(M.PercDesconto, 0)/100.0)) + ISNULL(M.ValorFrete, 0) END AS ValorLiquido
    FROM Movimento M WITH (NOLOCK)
    INNER JOIN Cli_For CF WITH (NOLOCK) ON M.CodCliFor = CF.CodCliFor
    WHERE CF.Inativo = 'N'
      AND M.DataFaturamento > '{watermark}'
      AND M.DataFaturamento <= GETDATE()
      AND M.TipoMov IN ('2.4','2.1','2.8','2.3')
      AND M.Status NOT IN ('C','T')
    """

    _etl_incremental(
        "radar_clientes", conn, path, sql_full, sql_inc,
        ["CodCliFor", "CodVendedor", "TipoMov", "DataFaturamento", "IdMov"],
        "DataFaturamento", 12, _parse_datas,
    )


def etl_radar_produtos(conn):
    """Produtos habituais por cliente/vendedor. Últimos 6 meses. Sempre full load (agregado)."""
    sql = """
    SELECT
        M.IdEmpresa, M.CodCliFor,
        CF.CodFunc          AS CodVendedor,
        P.NOMEPRODUTO       AS Produto,
        SUM(IM.Qtd)         AS QtdTotal,
        COUNT(DISTINCT M.IdMov) AS Frequencia
    FROM Movimento M WITH (NOLOCK)
    INNER JOIN Cli_For CF   WITH (NOLOCK) ON M.CodCliFor  = CF.CodCliFor AND M.IdEmpresa=CF.IdEmpresa
    INNER JOIN ItensMov IM  WITH (NOLOCK) ON M.IdMov      = IM.IdMov AND M.IdEmpresa=IM.IdEmpresa
    INNER JOIN Produtos P   WITH (NOLOCK) ON IM.IdProduto = P.IdProduto
    WHERE M.IdEmpresa=1 AND CF.Inativo = 'N'
      AND CF.CodFunc IS NOT NULL
      AND M.DataFaturamento >= DATEADD(MONTH, -6, GETDATE())
      AND M.TipoMov IN ('2.4','2.1')
      AND M.Status NOT IN ('C','T')
    GROUP BY M.IdEmpresa, M.CodCliFor, CF.CodFunc, P.NOMEPRODUTO
    """
    df = _run("radar_produtos", sql, conn)
    df.to_parquet(CACHE_DIR / "radar_produtos.parquet", index=False)


def etl_radar_rent_cli(conn):
    """Rentabilidade da carteira atual, em seis meses, com receita OPE por item."""
    dia = _data_cronos()
    inicio = dia - pd.DateOffset(months=6)
    fim = dia + pd.Timedelta(days=1)
    valor_ope = _sql_valor_ope()
    sql = f"""
    SELECT
        M.CodCliFor,
        CF.CodFunc AS CodVendedor,
        SUM(CONVERT(MONEY, dbo.MultV(M.TipoMov) * {valor_ope})) AS Faturamento,
        SUM(CONVERT(MONEY, dbo.MultV(M.TipoMov) *
            ISNULL(IM.CustoUnitarioItem * IM.Qtd, 0))) AS CustoTotal,
        COUNT_BIG(*) - COUNT_BIG(dbo.MultV(M.TipoMov) * {valor_ope}) AS ItensSemReceita
    FROM Movimento AS M
    INNER JOIN Cli_For AS CF
        ON M.CodCliFor = CF.CodCliFor AND M.IdEmpresa = CF.IdEmpresa
    INNER JOIN ItensMov AS IM
        ON M.IdMov = IM.IdMov AND M.IdEmpresa = IM.IdEmpresa
    INNER JOIN Produtos AS P ON IM.IdProduto = P.IdProduto
    WHERE M.IdEmpresa = 1 AND CF.Inativo = 'N'
      AND CF.CodFunc IS NOT NULL
      AND M.CodFilial = '01' AND M.CodLocal = '01'
      AND M.DataFaturamento >= '{inicio:%Y%m%d}'
      AND M.DataFaturamento < '{fim:%Y%m%d}'
      AND M.TipoMov IN ('2.4','2.1','2.8','2.3')
      AND M.Status NOT IN ('C','T')
      AND EXISTS (
          SELECT 1 FROM CondPag AS CP
          WHERE CP.CodCondPag = M.CodCondPag
            AND CP.CodCondPag NOT IN ('28', '45', '80', '81', '84', '85')
      )
    GROUP BY M.CodCliFor, CF.CodFunc
    """
    df = _run("radar_rent_cli", sql, conn)
    for coluna in ["Faturamento", "CustoTotal", "ItensSemReceita"]:
        df[coluna] = pd.to_numeric(df[coluna], errors="raise")
        if df[coluna].isna().any() or not df[coluna].map(
                lambda v: float('-inf') < v < float('inf')).all():
            raise ValueError("Rentabilidade por cliente incompleta; cache anterior preservado.")
    if df["ItensSemReceita"].ne(0).any():
        raise ValueError("Itens sem receita OPE por cliente; cache anterior preservado.")
    df = df.drop(columns=["ItensSemReceita"])
    df["VersaoRentabilidadeCronos"] = 1
    df["PeriodoInicio"] = inicio
    df["PeriodoFimExclusivo"] = fim
    _salvar_parquet_atomico(df, CACHE_DIR / "radar_rent_cli.parquet")


def etl_vendedores(conn):
    """Carteira de vendedores ativos + supervisores que venderam. Sempre full load (tabela pequena)."""
    sql = """
    -- Vendedores tipo 'V'
    SELECT DISTINCT
        V.CodVendedor,
        V.NomeVendedor              AS Vendedor,
        ISNULL(V.CodSupervisor, '') AS CodSupervisor
    FROM Vendedores V WITH (NOLOCK)
    WHERE V.Inativo = 'N' AND V.Tipo = 'V'

    UNION

    -- Supervisores tipo 'S' que têm vendas nos últimos 13 meses
    SELECT DISTINCT
        V.CodVendedor,
        V.NomeVendedor              AS Vendedor,
        ISNULL(V.CodSupervisor, '') AS CodSupervisor
    FROM Vendedores V WITH (NOLOCK)
    INNER JOIN Movimento M WITH (NOLOCK) ON COALESCE(M.CodVendedor, '') = V.CodVendedor
    WHERE V.Inativo = 'N'
      AND V.Tipo = 'S'
      AND M.DataFaturamento >= DATEADD(MONTH, -13, GETDATE())
      AND M.TipoMov IN ('2.4','2.1','2.8','2.3')
      AND M.Status NOT IN ('C','T')

    ORDER BY Vendedor
    """
    df = _run("vendedores", sql, conn)
    df.to_parquet(CACHE_DIR / "vendedores.parquet", index=False)


def etl_supervisores(conn):
    """Supervisores ativos. Sempre full load (tabela pequena)."""
    sql = """
    SELECT DISTINCT
        SUP.CodVendedor,
        SUP.NomeVendedor AS Supervisor
    FROM Vendedores V WITH (NOLOCK)
    INNER JOIN Vendedores SUP WITH (NOLOCK) ON V.CodSupervisor = SUP.CodVendedor
    WHERE V.Inativo = 'N' AND V.Tipo = 'V'
    ORDER BY SUP.NomeVendedor
    """
    df = _run("supervisores", sql, conn)
    df.to_parquet(CACHE_DIR / "supervisores.parquet", index=False)


def etl_clientes_info(conn):
    """Metadados cadastrais de clientes: Região e Segmento. Sempre full load."""
    sql = """
    SELECT
        CF.CodCliFor,
        ISNULL(R.NomeRegiao,   'Sem Região')                   AS Regiao,
        ISNULL(CAT.Denominacao, 'Não Classificado')            AS Segmento
    FROM Cli_For CF WITH (NOLOCK)
    LEFT JOIN Regiao R          WITH (NOLOCK) ON CF.IdRegiao          = R.IdRegiao
    LEFT JOIN CategoriaCliFor CAT WITH (NOLOCK) ON CF.IdCategoriaCliFor = CAT.IdCategoriaCliFor
    WHERE CF.Inativo = 'N'
    """
    df = _run("clientes_info", sql, conn)
    df.to_parquet(CACHE_DIR / "clientes_info.parquet", index=False)


def etl_pedidos_pendentes(conn):
    """Pedidos não faturados (TipoMov='P'). Sempre full load — estado corrente da fila."""
    sql = """
    SELECT
        M.NumMov                                                    AS NumMov,
        M.DtMov                                                     AS Data,
        CF.NomeCliFor                                               AS Cliente,
        COALESCE(M.CodVendedor, CF.CodFunc)                        AS CodVendedor,
        V.NomeVendedor                                              AS Vendedor,
        M.TotMov                                                    AS ValorTotal,
        (SELECT COUNT(*) FROM ItensMov IM2 WITH (NOLOCK)
         WHERE IM2.IdMov = M.IdMov)                                AS QtdItens
    FROM Movimento M WITH (NOLOCK)
    INNER JOIN Cli_For CF   WITH (NOLOCK) ON M.CodCliFor = CF.CodCliFor
    LEFT  JOIN Vendedores V WITH (NOLOCK) ON V.CodVendedor = COALESCE(M.CodVendedor, CF.CodFunc)
    WHERE M.TipoMov = 'P'
      AND M.Status NOT IN ('C', 'T')
    ORDER BY M.DtMov DESC
    """
    df = _run("pedidos_pendentes", sql, conn)
    df["Data"] = pd.to_datetime(df["Data"])
    df.to_parquet(CACHE_DIR / "pedidos_pendentes.parquet", index=False)


def etl_prevendas(conn):
    """Pré-vendas em aberto (Status='T'). Full load — estado corrente, muda o tempo todo."""
    sql = """
    SELECT
        M.IdEmpresa, M.IdMov, M.CodVendedor, M.CodCliFor,
        V.NomeVendedor,
        CF.NomeCliFor AS Cliente,
        M.NumMov,
        M.DtMov,
        ROUND(
            CASE WHEN M.TipoMov IN ('2.8','2.3')
                 THEN (M.TotMov * (1 - ISNULL(M.PercDesconto, 0)/100.0) * -1) + ISNULL(M.ValorFrete, 0)
                 ELSE (M.TotMov * (1 - ISNULL(M.PercDesconto, 0)/100.0)) + ISNULL(M.ValorFrete, 0)
            END, 2
        ) AS ValorLiquido
    FROM Movimento M WITH (NOLOCK)
    INNER JOIN Cli_For CF WITH (NOLOCK) ON M.CodCliFor = CF.CodCliFor AND M.IdEmpresa = CF.IdEmpresa
    INNER JOIN Vendedores V WITH (NOLOCK) ON V.CodVendedor = M.CodVendedor AND V.IdEmpresa = M.IdEmpresa
    WHERE M.IdEmpresa = 1 AND CF.Inativo = 'N'
      AND M.TipoMov IN ('2.4','2.1','2.8','2.3')
      AND M.Status = 'T'
      AND M.DtMov >= '2026-06-01'
    ORDER BY M.DtMov ASC
    """
    df = _run("prevendas", sql, conn)
    if df.duplicated(["IdEmpresa", "IdMov"]).any():
        raise ValueError("Documentos duplicados; confira os vínculos do cadastro e ZMovimentoCompl.")
    df["VersaoDocumentosRadar"] = 2
    df["AtualizadoEmUTC"] = pd.Timestamp.now(tz="UTC")
    df["DtMov"] = pd.to_datetime(df["DtMov"])
    df.to_parquet(CACHE_DIR / "prevendas.parquet", index=False)


def etl_orcamentos_abertos(conn):
    """Orçamentos em aberto (Status='T', TipoMov='2.7'). Full load — estado corrente."""
    sql = """
    SELECT
        M.IdEmpresa, M.IdMov, M.CodVendedor,
        V.NomeVendedor,
        M.NumMov,
        M.DtMov,
        M.CodCliFor,
        CF.NomeCliFor,
        Z.CodTd_PO,
        ROUND(
            (M.TotMov * (1 - ISNULL(M.PercDesconto, 0)/100.0)) + ISNULL(M.ValorFrete, 0), 2
        ) AS ValorLiquido
    FROM Movimento M WITH (NOLOCK)
    INNER JOIN ZMovimentoCompl Z ON Z.IdMov     = M.IdMov
    INNER JOIN Cli_For CF        ON CF.CodCliFor = M.CodCliFor AND CF.IdEmpresa = M.IdEmpresa
    LEFT  JOIN Vendedores V      ON V.CodVendedor = M.CodVendedor AND V.IdEmpresa = M.IdEmpresa
    WHERE M.IdEmpresa = 1 AND M.TipoMov = '2.7'
      AND M.Status  = 'T'
      AND M.DtMov  >= '2026-06-01'
      AND Z.CodTd_PO IN ('Negociando', 'Faltas', 'Preço Concorren', 'Venda Perdida')
    ORDER BY M.DtMov DESC, ValorLiquido DESC
    """
    df = _run("orcamentos_abertos", sql, conn)
    if df.duplicated(["IdEmpresa", "IdMov"]).any():
        raise ValueError("Documentos duplicados; confira os vínculos do cadastro e ZMovimentoCompl.")
    df["VersaoDocumentosRadar"] = 2
    df["AtualizadoEmUTC"] = pd.Timestamp.now(tz="UTC")
    df["DtMov"] = pd.to_datetime(df["DtMov"])
    df.to_parquet(CACHE_DIR / "orcamentos_abertos.parquet", index=False)


def _campo_data_cadastro(conn):
    """Only use a field explicitly confirmed by the operator. Never guess."""
    campo = os.getenv("RADAR_CAMPO_DATA_CADASTRO", "").strip()
    if not campo:
        logging.warning("Data de cadastro não configurada; aba exibirá informação indisponível.")
        return None
    import re
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", campo):
        raise ValueError("RADAR_CAMPO_DATA_CADASTRO inválido.")
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT c.name FROM [dbCronos].sys.columns c
            JOIN [dbCronos].sys.tables t ON t.object_id=c.object_id
            JOIN [dbCronos].sys.schemas s ON s.schema_id=t.schema_id
            JOIN [dbCronos].sys.types ty ON ty.user_type_id=c.user_type_id
            WHERE s.name='dbo' AND t.name='Cli_For' AND c.name=%s
              AND ty.name IN ('date','datetime','datetime2','smalldatetime')
        """, (campo,))
        if cursor.fetchone() is None:
            raise ValueError("Campo de cadastro não encontrado ou não é data. Confirme no Cronos.")
    finally:
        cursor.close()
    return campo


def etl_radar_responsaveis(conn):
    sql = """
        SELECT V.IdEmpresa, V.CodVendedor, V.NomeVendedor AS Vendedor,
               V.Tipo, ISNULL(V.CodSupervisor,'') AS CodSupervisor,
               ISNULL(S.NomeVendedor,'Sem supervisor') AS Supervisor
        FROM [dbCronos].[dbo].[Vendedores] V
        LEFT JOIN [dbCronos].[dbo].[Vendedores] S
          ON S.IdEmpresa=V.IdEmpresa AND S.CodVendedor=V.CodSupervisor
        WHERE V.IdEmpresa=1 AND V.Inativo='N' AND V.Tipo IN ('V','S')
    """
    df = _run("radar_responsaveis", sql, conn)
    if df.empty or df.CodVendedor.isna().any() or df.duplicated(["IdEmpresa","CodVendedor"]).any():
        raise ValueError("Responsáveis vazios ou duplicados.")
    df["AtualizadoEmUTC"] = pd.Timestamp.now(tz="UTC")
    _salvar_parquet_atomico(df, CACHE_DIR / "radar_responsaveis.parquet")

def etl_carteira_clientes(conn, data_referencia=None):
    """Carteira, receita OPE e curva global 20/30/50, com historico coerente.

    Substitui somente etl_carteira_clientes em scripts/etl_cache.py.
    Usa _run, pd, os, CACHE_DIR e logging ja existentes no arquivo.
    Mantem os tipos cadastrais C/R e os 12 meses incluindo o mes parcial.
    """
    from uuid import uuid4

    referencia = (
        pd.Timestamp.now(tz="America/Sao_Paulo")
        if data_referencia is None else pd.Timestamp(data_referencia)
    )
    if pd.isna(referencia):
        raise ValueError("Data de referencia invalida.")
    if referencia.tzinfo is not None:
        referencia = referencia.tz_convert("America/Sao_Paulo")
    dia = pd.Timestamp(referencia.date())
    inicio = dia.replace(day=1) - pd.DateOffset(months=11)
    fim = dia + pd.Timedelta(days=1)
    inicio_sql, fim_sql = inicio.strftime("%Y%m%d"), fim.strftime("%Y%m%d")

    campo_cadastro = _campo_data_cadastro(conn)
    data_cadastro_sql = f"CF.[{campo_cadastro}]" if campo_cadastro else "CAST(NULL AS DATETIME)"
    sql = f"""
    ;WITH Carteira AS (
        SELECT
            CF.IdEmpresa, CF.CodCliFor, CF.NomeCliFor AS Cliente,
            CF.TipoCliente, CF.Inativo AS ClienteInativo,
            {data_cadastro_sql} AS DataCadastro,
            CF.FoneCliFor AS Telefone, CF.CelCliFor AS Celular,
            CF.CodFunc AS CodVendedorCarteira,
            V.IdEmpresa AS IdEmpresaResponsavel,
            V.NomeVendedor AS VendedorCarteira,
            V.Tipo AS TipoResponsavel, V.Inativo AS ResponsavelInativo,
            V.CodSupervisor,
            COUNT_BIG(*) OVER (
                PARTITION BY CF.IdEmpresa, CF.CodCliFor
            ) AS LinhasCadastro,
            CAST(CASE
                WHEN V.Tipo = 'V' AND V.Inativo = 'N'
                 AND CF.CodFunc NOT IN ('00002', '01174')
                THEN 1 ELSE 0
            END AS BIT) AS CarteiraVAtiva
        FROM [dbCronos].[dbo].[Cli_For] AS CF
        LEFT JOIN [dbCronos].[dbo].[Vendedores] AS V
            ON V.CodVendedor = CF.CodFunc AND V.IdEmpresa = CF.IdEmpresa
        WHERE CF.IdEmpresa = 1 AND CF.Inativo = 'N'
    ), ReceitaMovimentos AS (
        SELECT
            M.IdEmpresa, M.CodCliFor, M.IdMov, M.NumMov, M.TipoMov,
            M.DtMov, M.DataFaturamento,
            [dbCronos].[dbo].[MultV](M.TipoMov) AS MultiplicadorMov,
            COUNT_BIG(*) - COUNT_BIG(F.ReceitaItem) AS ItensSemValor,
            CASE WHEN COUNT_BIG(*) = COUNT_BIG(F.ReceitaItem)
                THEN CONVERT(DECIMAL(19, 2), SUM(F.ReceitaItem))
            END AS ValorLiquido
        FROM [dbCronos].[dbo].[Movimento] AS M
        INNER JOIN [dbCronos].[dbo].[ItensMov] AS IM
            ON IM.IdEmpresa = M.IdEmpresa AND IM.IdMov = M.IdMov
        CROSS APPLY (
            SELECT CASE WHEN IM.IdItemMov IS NULL THEN NULL
            ELSE CONVERT(FLOAT,
                [dbCronos].[dbo].[MultV](M.TipoMov) *
                [dbCronos].[dbo].[fn_ValorItemMov4](
                    'OPE', M.IdMov, IM.IdItemMov, IM.IdProduto,
                    IM.PrecoUnit, IM.PercDescontoItem, IM.Qtd,
                    IM.PercICMS, IM.PercIPI, IM.PercISS, IM.MVAitem,
                    M.TipoMov, M.CodCliFor, M.CodFilial,
                    M.CodFilialDest, M.CodLocalDest, M.PercDesconto,
                    M.CalculaICMSsubstituto, M.DescNaoIncideICMS,
                    IM.IdNaturezaOperacao, IM.SitTributariaItem,
                    M.ValorIPIincideICMS, M.ValorFreteIncideICMS,
                    IM.PercReducaoBICMS, IM.PercSubICMS,
                    IM.ValorItemFrete, IM.ValorItemOutDespesas
                )
            ) END AS ReceitaItem
        ) AS F
        WHERE M.IdEmpresa = 1
          AND M.DataFaturamento >= '{inicio_sql}'
          AND M.DataFaturamento < '{fim_sql}'
          AND M.DtMov >= '{inicio_sql}'
          AND M.DtMov < '{fim_sql}'
          AND M.Status NOT IN ('C', 'T')
          AND M.TipoMov IN ('2.4', '2.8', '2.3', '2.1')
          AND M.CodFilial = '01' AND M.CodLocal = '01'
          AND EXISTS (
              SELECT 1 FROM Carteira AS CA
              WHERE CA.IdEmpresa = M.IdEmpresa
                AND CA.CodCliFor = M.CodCliFor AND CA.CarteiraVAtiva = 1
          )
          AND EXISTS (
              SELECT 1 FROM [dbCronos].[dbo].[CondPag] AS CP
              WHERE CP.CodCondPag = M.CodCondPag
                AND CP.CodCondPag NOT IN ('28', '45', '80', '81', '84', '85')
          )
        GROUP BY M.IdEmpresa, M.CodCliFor, M.IdMov, M.NumMov, M.TipoMov,
                 M.DtMov, M.DataFaturamento
    )
    SELECT CA.*, RM.IdMov, RM.NumMov, RM.TipoMov, RM.DtMov,
           RM.DataFaturamento, RM.MultiplicadorMov, RM.ItensSemValor,
           CASE
               WHEN CA.CarteiraVAtiva = 0 THEN NULL
               WHEN RM.IdMov IS NULL THEN CONVERT(DECIMAL(19, 2), 0)
               ELSE RM.ValorLiquido
           END AS ValorLiquido
    FROM Carteira AS CA
    LEFT JOIN ReceitaMovimentos AS RM
        ON RM.IdEmpresa = CA.IdEmpresa AND RM.CodCliFor = CA.CodCliFor;
    """
    bruto = _run("carteira_clientes", sql, conn).reset_index(drop=True)
    cadastro = [
        "IdEmpresa", "CodCliFor", "Cliente", "TipoCliente", "ClienteInativo",
        "Telefone", "Celular", "CodVendedorCarteira", "IdEmpresaResponsavel",
        "VendedorCarteira", "TipoResponsavel", "ResponsavelInativo",
        "CodSupervisor", "CarteiraVAtiva", "DataCadastro",
    ]
    movimentos = [
        "IdMov", "NumMov", "TipoMov", "DtMov", "DataFaturamento",
        "ItensSemValor", "ValorLiquido", "MultiplicadorMov",
    ]
    obrigatorias = set(cadastro + movimentos + ["LinhasCadastro"])
    if bruto.empty or not obrigatorias.issubset(bruto.columns):
        raise ValueError("Carteira vazia ou sem as colunas esperadas.")
    if bruto[["IdEmpresa", "CodCliFor", "CarteiraVAtiva"]].isna().any().any():
        raise ValueError("Carteira com identificadores ou elegibilidade ausentes.")
    if bruto["LinhasCadastro"].ne(1).any():
        raise ValueError("Cadastro ou responsavel duplicado; revisar os vinculos.")
    if not bruto["CarteiraVAtiva"].isin([0, 1]).all():
        raise ValueError("Marcador de elegibilidade invalido.")
    if bruto["IdEmpresa"].ne(1).any():
        raise ValueError("Carteira fora da empresa 1.")
    for coluna in ["CodCliFor", "CodVendedorCarteira"]:
        bruto[coluna] = bruto[coluna].astype("string").str.strip()
    if bruto["CodCliFor"].eq("").any():
        raise ValueError("Codigo de cliente vazio.")
    for coluna in ["Cliente", "Telefone", "Celular", "VendedorCarteira"]:
        bruto[coluna] = bruto[coluna].fillna("").astype(str).str.strip()
    bruto["CarteiraVAtiva"] = bruto["CarteiraVAtiva"].eq(1)
    df = bruto[cadastro].drop_duplicates().reset_index(drop=True)
    chaves = ["IdEmpresa", "CodCliFor"]
    if df.duplicated(chaves).any():
        raise ValueError("Informacoes conflitantes para o mesmo cliente.")
    elegivel = df["CarteiraVAtiva"]
    n = int(elegivel.sum())
    if n == 0:
        raise ValueError("Nenhum cliente elegivel; revisar os responsaveis.")

    hist = bruto.loc[bruto["CarteiraVAtiva"], cadastro + movimentos].copy()
    hist["IdMov"] = pd.to_numeric(hist["IdMov"], errors="raise").astype("Int64")
    reais = hist["IdMov"].notna()
    hist["MultiplicadorMov"] = pd.to_numeric(hist["MultiplicadorMov"], errors="raise")
    if hist.loc[reais, "MultiplicadorMov"].isna().any():
        raise ValueError("Multiplicador de movimento ausente; não é possível identificar compras.")
    df["DataCadastro"] = pd.to_datetime(df["DataCadastro"], errors="raise")
    if hist.loc[reais].duplicated(["IdEmpresa", "IdMov"]).any():
        raise ValueError("Movimento duplicado na carteira.")
    if hist.loc[reais, "ItensSemValor"].isna().any() or hist.loc[reais, "ItensSemValor"].ne(0).any():
        raise ValueError("Itens sem receita OPE; cache anterior preservado.")
    hist["ValorLiquido"] = pd.to_numeric(hist["ValorLiquido"], errors="raise")
    if hist["ValorLiquido"].isna().any() or not hist["ValorLiquido"].map(lambda v: float('-inf') < v < float('inf')).all():
        raise ValueError("Receita incompleta; cache anterior preservado.")
    hist["ValorLiquido"] = hist["ValorLiquido"].astype(float).round(2)
    hist.loc[~reais, "ItensSemValor"] = 0
    for coluna in ["DtMov", "DataFaturamento"]:
        hist[coluna] = pd.to_datetime(hist[coluna], errors="raise")
        if not hist.loc[reais, coluna].between(inicio, fim, inclusive="left").all():
            raise ValueError("Movimento fora da janela conferida.")

    resumo = hist.loc[reais].groupby(chaves, as_index=False).agg(
        TotalPeriodo=("ValorLiquido", "sum"),
        QuantidadeMovimentos=("IdMov", "count"),
    )
    df = df.merge(resumo, on=chaves, how="left", validate="one_to_one")
    elegivel = df["CarteiraVAtiva"]
    df.loc[elegivel, "TotalPeriodo"] = df.loc[elegivel, "TotalPeriodo"].fillna(0)
    df.loc[elegivel, "QuantidadeMovimentos"] = df.loc[elegivel, "QuantidadeMovimentos"].fillna(0)
    df["TotalPeriodo"] = df["TotalPeriodo"].round(2)
    df["QuantidadeMovimentos"] = df["QuantidadeMovimentos"].astype("Int64")
    df["ItensSemValor"] = pd.Series(pd.NA, index=df.index, dtype="Int64")
    df.loc[elegivel, "ItensSemValor"] = 0
    df["MediaMensal"] = df["TotalPeriodo"] / 12
    df["PosicaoCurva"] = pd.Series(pd.NA, index=df.index, dtype="Int64")
    df["CurvaABC"] = pd.Series(pd.NA, index=df.index, dtype="string")
    ordem = df.loc[elegivel].sort_values(
        ["TotalPeriodo", "CodCliFor"], ascending=[False, True], kind="stable"
    ).index
    limite_a, limite_ab = (n + 4) // 5, (n + 1) // 2
    df.loc[ordem, "PosicaoCurva"] = range(1, n + 1)
    df.loc[ordem[:limite_a], "CurvaABC"] = "A"
    df.loc[ordem[limite_a:limite_ab], "CurvaABC"] = "B"
    df.loc[ordem[limite_ab:], "CurvaABC"] = "C"

    snapshot = uuid4().hex
    atualizado = pd.Timestamp.now(tz="UTC")
    for tabela in [df, hist]:
        tabela["VersaoInterfaceCarteira"] = 2
        tabela["CampoDataCadastro"] = campo_cadastro or ""
        tabela["SnapshotCarteira"] = snapshot
        tabela["QtdClientesCurva"] = n
        tabela["PeriodoInicio"] = inicio
        tabela["PeriodoFimExclusivo"] = fim
        tabela["DataReferencia"] = dia
        tabela["AtualizadoEmUTC"] = atualizado

    # Serializa ambos antes de publicar. O Radar confere SnapshotCarteira
    # para recusar uma leitura entre as duas trocas de arquivos.
    paths = [CACHE_DIR / "carteira_clientes.parquet", CACHE_DIR / "carteira_historico.parquet"]
    temporarios = [p.with_name(f"{p.stem}.{snapshot}.tmp.parquet") for p in paths]
    try:
        for tabela, temp in zip([df, hist], temporarios):
            tabela.to_parquet(temp, index=False)
        for temp, path in zip(temporarios, paths):
            os.replace(temp, path)
    finally:
        for temp in temporarios:
            temp.unlink(missing_ok=True)
    logging.info(
        "[carteira_clientes] %d cadastros; %d elegiveis; A=%d, B=%d, C=%d; %s a %s",
        len(df), n, limite_a, limite_ab - limite_a, n - limite_ab,
        inicio.date(), dia.date(),
    )

        
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Atualiza os caches locais do Radar.")
    parser.add_argument("--somente-financeiro", action="store_true",
                        help="Atualiza apenas o mes corrente do relatorio Cronos.")
    args = parser.parse_args()
    logging.info("=" * 60)
    logging.info("ETL GM LIMPEZA — INICIADO")
    conn = None
    try:
        conn = get_conn()
        etl_rentabilidade_cronos(conn)
        if not args.somente_financeiro:
            etl_movimentos(conn)
            etl_itens(conn)
            etl_radar_clientes(conn)
            etl_carteira_clientes(conn)
            etl_radar_responsaveis(conn)
            etl_radar_produtos(conn)
            etl_radar_rent_cli(conn)
            etl_vendedores(conn)
            etl_supervisores(conn)
            etl_clientes_info(conn)
            etl_pedidos_pendentes(conn)
            etl_prevendas(conn)
            etl_orcamentos_abertos(conn)
        logging.info("ETL CONCLUÍDO COM SUCESSO")
    except Exception as e:
        logging.error(f"ETL FALHOU: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if conn is not None:
            conn.close()
    logging.info("=" * 60)
