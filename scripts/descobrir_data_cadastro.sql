-- Consulta somente de leitura. Execute no DBeaver conectado ao dbCronos.
SELECT c.name AS Campo, ty.name AS Tipo,
       CAST(ep.value AS nvarchar(4000)) AS Descricao
FROM [dbCronos].sys.columns c
JOIN [dbCronos].sys.tables t ON t.object_id=c.object_id
JOIN [dbCronos].sys.schemas s ON s.schema_id=t.schema_id
JOIN [dbCronos].sys.types ty ON ty.user_type_id=c.user_type_id
LEFT JOIN [dbCronos].sys.extended_properties ep
  ON ep.major_id=c.object_id AND ep.minor_id=c.column_id
 AND ep.class=1 AND ep.name='MS_Description'
WHERE s.name='dbo' AND t.name='Cli_For'
  AND (ty.name IN ('date','datetime','datetime2','smalldatetime')
       OR c.name LIKE '%cad%' OR c.name LIKE '%incl%')
ORDER BY c.column_id;
