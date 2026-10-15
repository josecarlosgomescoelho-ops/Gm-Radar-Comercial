/*
RELATÓRIO DE VENDAS POR PRODUTO E FORNECEDOR
Período: Últimos 12 meses fechados (dinâmico)
Granularidade: Mensal - Apenas Quantidade Vendida
Formato: Colunas dinâmicas com nome/ano do mês (ex: jun/26)
IMPORTANTE: As colunas dos meses são geradas DINAMICAMENTE conforme o mês atual
*/

-- Parâmetro de filtro: ID do Fornecedor (OPCIONAL - comentar linha WHERE para ver todos)
-- IMPORTANTE: Ajustado para REAL pois CodFabr é numérico no banco
DECLARE @CodFabr REAL = :COD_FORNECEDOR;  -- Parâmetro dinâmico do Cronos
-- DECLARE @CodFabr REAL = 186;  -- DONAPACK
-- DECLARE @CodFabr REAL = 5;    -- PARPEL
-- DECLARE @CodFabr REAL = NULL; -- TODOS (descomente para ver todos)

-- Calcular período: últimos 12 meses fechados
DECLARE @DataInicio DATE = DATEADD(MONTH, DATEDIFF(MONTH, 0, DATEADD(MONTH, -12, GETDATE())), 0);
DECLARE @DataFim DATE = DATEADD(DAY, -1, DATEADD(MONTH, DATEDIFF(MONTH, 0, GETDATE()), 0));

-- Debug: mostrar período calculado
PRINT 'Período: ' + CONVERT(VARCHAR, @DataInicio, 103) + ' a ' + CONVERT(VARCHAR, @DataFim, 103);

-- Variáveis para SQL dinâmico
DECLARE @MesesColunas NVARCHAR(MAX);
DECLARE @MesesISNULL NVARCHAR(MAX);
DECLARE @MesesSoma NVARCHAR(MAX);
DECLARE @SQL NVARCHAR(MAX);

-- Gerar lista de meses dinamicamente
;WITH TodosMeses AS (
    SELECT TOP 12
        DATEADD(MONTH, -ROW_NUMBER() OVER (ORDER BY (SELECT NULL)),
                DATEADD(MONTH, DATEDIFF(MONTH, 0, GETDATE()), 0)) AS PrimeiroDiaMes
    FROM sys.objects
),
MesesFormatados AS (
    SELECT
        LOWER(LEFT(DATENAME(MONTH, PrimeiroDiaMes), 3)) + '/' +
        RIGHT(CAST(YEAR(PrimeiroDiaMes) AS VARCHAR), 2) AS MesFormatado,
        PrimeiroDiaMes
    FROM TodosMeses
    WHERE PrimeiroDiaMes >= @DataInicio AND PrimeiroDiaMes <= @DataFim
)
SELECT
    @MesesColunas = STRING_AGG(QUOTENAME(MesFormatado), ', ') WITHIN GROUP (ORDER BY PrimeiroDiaMes),
    @MesesISNULL = STRING_AGG('ISNULL(' + QUOTENAME(MesFormatado) + ', 0) AS ' + QUOTENAME(MesFormatado), ', ' + CHAR(10) + '    ') WITHIN GROUP (ORDER BY PrimeiroDiaMes),
    @MesesSoma = STRING_AGG('ISNULL(' + QUOTENAME(MesFormatado) + ', 0)', ' + ')  WITHIN GROUP (ORDER BY PrimeiroDiaMes)
FROM MesesFormatados;

-- Debug: mostrar colunas geradas
PRINT 'Colunas geradas: ' + @MesesColunas;

-- Construir query dinâmica
SET @SQL = N'
;WITH DadosBase AS (
    SELECT
        F.CodFabr,
        F.NomeFabr AS Fornecedor,
        P.NOMEPRODUTO AS Produto,
        P.IdProduto,
        -- Formato: jun/26
        LOWER(LEFT(DATENAME(MONTH, M.DataFaturamento), 3)) + ''/'' +
        RIGHT(CAST(YEAR(M.DataFaturamento) AS VARCHAR), 2) AS MesFormatado,
        SUM(IM.Qtd) AS QtdVendida
    FROM ItensMov IM WITH (NOLOCK)
    INNER JOIN Movimento M WITH (NOLOCK)
        ON IM.IdMov = M.IdMov
    INNER JOIN Produtos P WITH (NOLOCK)
        ON IM.IdProduto = P.IdProduto
    LEFT JOIN Fabricantes F WITH (NOLOCK)
        ON P.CodFabr = F.CodFabr
    WHERE M.DataFaturamento >= @DataInicio
      AND M.DataFaturamento <= @DataFim
      AND M.TipoMov IN (''2.4'',''2.1'')  -- Filtros do Radar (vendas)
      AND M.Status NOT IN (''C'',''T'')
      AND IM.StatusItemMov NOT IN (''C'')
      AND (@CodFabr IS NULL OR P.CodFabr = @CodFabr)
    GROUP BY
        F.CodFabr,
        F.NomeFabr,
        P.NOMEPRODUTO,
        P.IdProduto,
        LOWER(LEFT(DATENAME(MONTH, M.DataFaturamento), 3)) + ''/'' +
        RIGHT(CAST(YEAR(M.DataFaturamento) AS VARCHAR), 2)
)
SELECT
    Fornecedor,
    Produto,
    ' + @MesesISNULL + ',
    -- Total de vendas
    ' + @MesesSoma + ' AS Total
FROM (
    SELECT
        Fornecedor,
        Produto,
        MesFormatado,
        QtdVendida
    FROM DadosBase
) AS SourceData
PIVOT (
    SUM(QtdVendida)
    FOR MesFormatado IN (' + @MesesColunas + ')
) AS PivotTable
WHERE ' + @MesesSoma + ' > 0
ORDER BY Fornecedor, Total DESC;
';

-- Executar query dinâmica
EXEC sp_executesql @SQL,
    N'@DataInicio DATE, @DataFim DATE, @CodFabr REAL',
    @DataInicio, @DataFim, @CodFabr;
