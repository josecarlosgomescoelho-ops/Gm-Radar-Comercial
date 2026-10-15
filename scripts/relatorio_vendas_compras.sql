/*
RELATÓRIO DE VENDAS E COMPRAS POR PRODUTO E FORNECEDOR
Período: Últimos 12 meses fechados (dinâmico)
Granularidade: Mensal (Vendido vs Comprado)
*/

-- Parâmetro de filtro: ID do Fornecedor (OPCIONAL - comentar linha WHERE para ver todos)
DECLARE @CodFabr VARCHAR(20) = '0186';  -- DONAPACK
-- DECLARE @CodFabr VARCHAR(20) = '0005';  -- PARPEL
-- DECLARE @CodFabr VARCHAR(20) = NULL;    -- TODOS (descomente para ver todos)

-- Calcular período: últimos 12 meses fechados
DECLARE @DataInicio DATE = DATEADD(MONTH, DATEDIFF(MONTH, 0, DATEADD(MONTH, -12, GETDATE())), 0);
DECLARE @DataFim DATE = DATEADD(DAY, -1, DATEADD(MONTH, DATEDIFF(MONTH, 0, GETDATE()), 0));

-- Debug: mostrar período calculado
PRINT 'Período: ' + CONVERT(VARCHAR, @DataInicio, 103) + ' a ' + CONVERT(VARCHAR, @DataFim, 103);

;WITH DadosBase AS (
    SELECT
        F.CodFabr,
        F.NomeFabr AS Fornecedor,
        P.NOMEPRODUTO AS Produto,
        P.IdProduto,
        M.DataFaturamento,
        YEAR(M.DataFaturamento) AS Ano,
        MONTH(M.DataFaturamento) AS Mes,
        -- Classificar como Venda ou Compra
        CASE
            WHEN M.TipoMov IN ('2.4','2.1','2.5') THEN 'VENDA'
            WHEN M.TipoMov IN ('1.1') THEN 'COMPRA'
            ELSE NULL
        END AS TipoOperacao,
        SUM(IM.Qtd) AS Quantidade
    FROM ItensMov IM WITH (NOLOCK)
    INNER JOIN Movimento M WITH (NOLOCK)
        ON IM.IdMov = M.IdMov
    INNER JOIN Produtos P WITH (NOLOCK)
        ON IM.IdProduto = P.IdProduto
    LEFT JOIN Fabricantes F WITH (NOLOCK)
        ON P.CodFabr = F.CodFabr
    WHERE M.DataFaturamento >= @DataInicio
      AND M.DataFaturamento <= @DataFim
      AND M.Status NOT IN ('C','T')
      AND IM.StatusItemMov NOT IN ('C')
      AND M.TipoMov IN ('2.4','2.1','2.5','1.1')  -- Vendas + Compras
      AND (@CodFabr IS NULL OR P.CodFabr = @CodFabr)  -- Filtro por fornecedor
    GROUP BY
        F.CodFabr,
        F.NomeFabr,
        P.NOMEPRODUTO,
        P.IdProduto,
        M.DataFaturamento,
        YEAR(M.DataFaturamento),
        MONTH(M.DataFaturamento),
        CASE
            WHEN M.TipoMov IN ('2.4','2.1','2.5') THEN 'VENDA'
            WHEN M.TipoMov IN ('1.1') THEN 'COMPRA'
            ELSE NULL
        END
),
AgregadoMensal AS (
    SELECT
        CodFabr,
        Fornecedor,
        Produto,
        IdProduto,
        Ano,
        Mes,
        SUM(CASE WHEN TipoOperacao = 'VENDA' THEN Quantidade ELSE 0 END) AS QtdVendida,
        SUM(CASE WHEN TipoOperacao = 'COMPRA' THEN Quantidade ELSE 0 END) AS QtdComprada
    FROM DadosBase
    GROUP BY CodFabr, Fornecedor, Produto, IdProduto, Ano, Mes
),
Meses AS (
    -- Gerar os últimos 12 meses
    SELECT TOP 12
        DATEADD(MONTH, -ROW_NUMBER() OVER (ORDER BY (SELECT NULL)),
                DATEADD(MONTH, DATEDIFF(MONTH, 0, GETDATE()), 0)) AS PrimeiroDiaMes
    FROM sys.objects
),
MesesNumerados AS (
    SELECT
        YEAR(PrimeiroDiaMes) AS Ano,
        MONTH(PrimeiroDiaMes) AS Mes,
        ROW_NUMBER() OVER (ORDER BY PrimeiroDiaMes) AS NumMes,
        -- Formato: jul/25
        LOWER(LEFT(DATENAME(MONTH, PrimeiroDiaMes), 3)) + '/' +
        RIGHT(CAST(YEAR(PrimeiroDiaMes) AS VARCHAR), 2) AS MesFormatado
    FROM Meses
    WHERE PrimeiroDiaMes >= @DataInicio AND PrimeiroDiaMes <= @DataFim
)
SELECT
    Fornecedor,
    Produto,

    -- Mês 1
    MAX(Mes1_Label) AS Mes1_Label,
    SUM(Mes1_Vendido) AS Mes1_Vendido,
    SUM(Mes1_Comprado) AS Mes1_Comprado,

    -- Mês 2
    MAX(Mes2_Label) AS Mes2_Label,
    SUM(Mes2_Vendido) AS Mes2_Vendido,
    SUM(Mes2_Comprado) AS Mes2_Comprado,

    -- Mês 3
    MAX(Mes3_Label) AS Mes3_Label,
    SUM(Mes3_Vendido) AS Mes3_Vendido,
    SUM(Mes3_Comprado) AS Mes3_Comprado,

    -- Mês 4
    MAX(Mes4_Label) AS Mes4_Label,
    SUM(Mes4_Vendido) AS Mes4_Vendido,
    SUM(Mes4_Comprado) AS Mes4_Comprado,

    -- Mês 5
    MAX(Mes5_Label) AS Mes5_Label,
    SUM(Mes5_Vendido) AS Mes5_Vendido,
    SUM(Mes5_Comprado) AS Mes5_Comprado,

    -- Mês 6
    MAX(Mes6_Label) AS Mes6_Label,
    SUM(Mes6_Vendido) AS Mes6_Vendido,
    SUM(Mes6_Comprado) AS Mes6_Comprado,

    -- Mês 7
    MAX(Mes7_Label) AS Mes7_Label,
    SUM(Mes7_Vendido) AS Mes7_Vendido,
    SUM(Mes7_Comprado) AS Mes7_Comprado,

    -- Mês 8
    MAX(Mes8_Label) AS Mes8_Label,
    SUM(Mes8_Vendido) AS Mes8_Vendido,
    SUM(Mes8_Comprado) AS Mes8_Comprado,

    -- Mês 9
    MAX(Mes9_Label) AS Mes9_Label,
    SUM(Mes9_Vendido) AS Mes9_Vendido,
    SUM(Mes9_Comprado) AS Mes9_Comprado,

    -- Mês 10
    MAX(Mes10_Label) AS Mes10_Label,
    SUM(Mes10_Vendido) AS Mes10_Vendido,
    SUM(Mes10_Comprado) AS Mes10_Comprado,

    -- Mês 11
    MAX(Mes11_Label) AS Mes11_Label,
    SUM(Mes11_Vendido) AS Mes11_Vendido,
    SUM(Mes11_Comprado) AS Mes11_Comprado,

    -- Mês 12
    MAX(Mes12_Label) AS Mes12_Label,
    SUM(Mes12_Vendido) AS Mes12_Vendido,
    SUM(Mes12_Comprado) AS Mes12_Comprado,

    -- Totais
    SUM(Total_Vendido) AS Total_Vendido,
    SUM(Total_Comprado) AS Total_Comprado

FROM (
    SELECT
        AM.Fornecedor,
        AM.Produto,
        AM.IdProduto,

        -- Mês 1
        CASE WHEN M.NumMes = 1 THEN M.MesFormatado END AS Mes1_Label,
        CASE WHEN M.NumMes = 1 THEN ISNULL(AM.QtdVendida, 0) ELSE 0 END AS Mes1_Vendido,
        CASE WHEN M.NumMes = 1 THEN ISNULL(AM.QtdComprada, 0) ELSE 0 END AS Mes1_Comprado,

        -- Mês 2
        CASE WHEN M.NumMes = 2 THEN M.MesFormatado END AS Mes2_Label,
        CASE WHEN M.NumMes = 2 THEN ISNULL(AM.QtdVendida, 0) ELSE 0 END AS Mes2_Vendido,
        CASE WHEN M.NumMes = 2 THEN ISNULL(AM.QtdComprada, 0) ELSE 0 END AS Mes2_Comprado,

        -- Mês 3
        CASE WHEN M.NumMes = 3 THEN M.MesFormatado END AS Mes3_Label,
        CASE WHEN M.NumMes = 3 THEN ISNULL(AM.QtdVendida, 0) ELSE 0 END AS Mes3_Vendido,
        CASE WHEN M.NumMes = 3 THEN ISNULL(AM.QtdComprada, 0) ELSE 0 END AS Mes3_Comprado,

        -- Mês 4
        CASE WHEN M.NumMes = 4 THEN M.MesFormatado END AS Mes4_Label,
        CASE WHEN M.NumMes = 4 THEN ISNULL(AM.QtdVendida, 0) ELSE 0 END AS Mes4_Vendido,
        CASE WHEN M.NumMes = 4 THEN ISNULL(AM.QtdComprada, 0) ELSE 0 END AS Mes4_Comprado,

        -- Mês 5
        CASE WHEN M.NumMes = 5 THEN M.MesFormatado END AS Mes5_Label,
        CASE WHEN M.NumMes = 5 THEN ISNULL(AM.QtdVendida, 0) ELSE 0 END AS Mes5_Vendido,
        CASE WHEN M.NumMes = 5 THEN ISNULL(AM.QtdComprada, 0) ELSE 0 END AS Mes5_Comprado,

        -- Mês 6
        CASE WHEN M.NumMes = 6 THEN M.MesFormatado END AS Mes6_Label,
        CASE WHEN M.NumMes = 6 THEN ISNULL(AM.QtdVendida, 0) ELSE 0 END AS Mes6_Vendido,
        CASE WHEN M.NumMes = 6 THEN ISNULL(AM.QtdComprada, 0) ELSE 0 END AS Mes6_Comprado,

        -- Mês 7
        CASE WHEN M.NumMes = 7 THEN M.MesFormatado END AS Mes7_Label,
        CASE WHEN M.NumMes = 7 THEN ISNULL(AM.QtdVendida, 0) ELSE 0 END AS Mes7_Vendido,
        CASE WHEN M.NumMes = 7 THEN ISNULL(AM.QtdComprada, 0) ELSE 0 END AS Mes7_Comprado,

        -- Mês 8
        CASE WHEN M.NumMes = 8 THEN M.MesFormatado END AS Mes8_Label,
        CASE WHEN M.NumMes = 8 THEN ISNULL(AM.QtdVendida, 0) ELSE 0 END AS Mes8_Vendido,
        CASE WHEN M.NumMes = 8 THEN ISNULL(AM.QtdComprada, 0) ELSE 0 END AS Mes8_Comprado,

        -- Mês 9
        CASE WHEN M.NumMes = 9 THEN M.MesFormatado END AS Mes9_Label,
        CASE WHEN M.NumMes = 9 THEN ISNULL(AM.QtdVendida, 0) ELSE 0 END AS Mes9_Vendido,
        CASE WHEN M.NumMes = 9 THEN ISNULL(AM.QtdComprada, 0) ELSE 0 END AS Mes9_Comprado,

        -- Mês 10
        CASE WHEN M.NumMes = 10 THEN M.MesFormatado END AS Mes10_Label,
        CASE WHEN M.NumMes = 10 THEN ISNULL(AM.QtdVendida, 0) ELSE 0 END AS Mes10_Vendido,
        CASE WHEN M.NumMes = 10 THEN ISNULL(AM.QtdComprada, 0) ELSE 0 END AS Mes10_Comprado,

        -- Mês 11
        CASE WHEN M.NumMes = 11 THEN M.MesFormatado END AS Mes11_Label,
        CASE WHEN M.NumMes = 11 THEN ISNULL(AM.QtdVendida, 0) ELSE 0 END AS Mes11_Vendido,
        CASE WHEN M.NumMes = 11 THEN ISNULL(AM.QtdComprada, 0) ELSE 0 END AS Mes11_Comprado,

        -- Mês 12
        CASE WHEN M.NumMes = 12 THEN M.MesFormatado END AS Mes12_Label,
        CASE WHEN M.NumMes = 12 THEN ISNULL(AM.QtdVendida, 0) ELSE 0 END AS Mes12_Vendido,
        CASE WHEN M.NumMes = 12 THEN ISNULL(AM.QtdComprada, 0) ELSE 0 END AS Mes12_Comprado,

        -- Totais (repetidos para cada linha, serão somados no final)
        ISNULL(AM.QtdVendida, 0) AS Total_Vendido,
        ISNULL(AM.QtdComprada, 0) AS Total_Comprado

    FROM (
        -- Lista de produtos únicos
        SELECT DISTINCT CodFabr, Fornecedor, Produto, IdProduto
        FROM AgregadoMensal
    ) Prods
    CROSS JOIN MesesNumerados M
    LEFT JOIN AgregadoMensal AM
        ON Prods.IdProduto = AM.IdProduto
       AND M.Ano = AM.Ano
       AND M.Mes = AM.Mes
) AS DadosPivotados

GROUP BY Fornecedor, Produto
HAVING SUM(Total_Vendido) > 0 OR SUM(Total_Comprado) > 0  -- Apenas produtos com movimento

ORDER BY Fornecedor, SUM(Total_Vendido) DESC;
