-- Consulta opcional no DBeaver para confirmar o estado administrativo do cadastro.
-- Somente leitura. Nao extrai movimentos, clientes ou faturamento.
SELECT
    V.IdEmpresa,
    V.CodVendedor,
    V.NomeVendedor,
    V.Tipo,
    V.CodSupervisor,
    V.Inativo,
    CASE WHEN V.Inativo = 'N' THEN 'Ativo no Cronos'
         WHEN V.Inativo = 'S' THEN 'Inativo no Cronos'
         ELSE 'Conferir indicador' END AS SituacaoCadastro
FROM [dbCronos].[dbo].[Vendedores] AS V
WHERE V.IdEmpresa = 1
  AND V.Tipo IN ('V', 'S')
ORDER BY V.Inativo, V.NomeVendedor, V.CodVendedor;
