"""
============================================================================
DISCOVERY DO BANCO - GM Limpeza Analytics
Autor: Victor Monteiro
Descrição: Extrai metadados completos do SQL Server para mapeamento.
           Gera CSVs prontos para análise.
============================================================================
"""

import pymssql
import csv
import os
from datetime import datetime

# ============================================================================
# CONFIGURAÇÃO DE CONEXÃO
# ============================================================================
SERVIDOR = "gm.inovareti.eti.br"
PORTA    = 52456
BANCO    = "dbCronos"
USUARIO  = "victor"
SENHA    = "ol@2023"
ESQUEMA  = "dbo"

# Pasta de saída
PASTA_SAIDA = "discovery_output"
os.makedirs(PASTA_SAIDA, exist_ok=True)

# ============================================================================
# CONEXÃO
# ============================================================================
def conectar():
    """Conecta ao SQL Server usando pymssql (sem necessidade de driver ODBC)."""
    try:
        conn = pymssql.connect(
            server=SERVIDOR,
            port=PORTA,
            user=USUARIO,
            password=SENHA,
            database=BANCO,
            login_timeout=30,
            charset='UTF-8'
        )
        print(f"[OK] Conectado via pymssql em {SERVIDOR}:{PORTA}/{BANCO}")
        return conn
    except Exception as e:
        raise Exception(f"Erro ao conectar: {e}\n\nInstale com: pip install pymssql")


# ============================================================================
# QUERIES DE DISCOVERY
# ============================================================================
QUERIES = {
    "01_tabelas_e_linhas": """
        SELECT 
            s.name   AS esquema,
            t.name   AS tabela,
            p.rows   AS linhas_aprox
        FROM sys.tables t
        JOIN sys.schemas s ON t.schema_id = s.schema_id
        JOIN sys.partitions p ON t.object_id = p.object_id AND p.index_id IN (0,1)
        ORDER BY p.rows DESC;
    """,

    "02_colunas_detalhadas": """
        SELECT 
            TABLE_SCHEMA        AS esquema,
            TABLE_NAME           AS tabela,
            COLUMN_NAME          AS coluna,
            ORDINAL_POSITION     AS posicao,
            DATA_TYPE            AS tipo_dado,
            CHARACTER_MAXIMUM_LENGTH AS tamanho_max,
            NUMERIC_PRECISION    AS precisao,
            NUMERIC_SCALE        AS escala,
            IS_NULLABLE          AS aceita_nulo,
            COLUMN_DEFAULT       AS valor_padrao
        FROM INFORMATION_SCHEMA.COLUMNS
        ORDER BY TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION;
    """,

    "03_chaves_primarias": """
        SELECT 
            s.name       AS esquema,
            t.name       AS tabela,
            i.name       AS nome_pk,
            c.name       AS coluna,
            ic.key_ordinal AS ordem
        FROM sys.indexes i
        JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
        JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
        JOIN sys.tables t ON i.object_id = t.object_id
        JOIN sys.schemas s ON t.schema_id = s.schema_id
        WHERE i.is_primary_key = 1
        ORDER BY s.name, t.name, ic.key_ordinal;
    """,

    "04_chaves_estrangeiras": """
        SELECT 
            fk.name      AS fk_nome,
            sp.name      AS esquema_pai,
            tp.name      AS tabela_pai,
            cp.name      AS coluna_pai,
            sr.name      AS esquema_ref,
            tr.name      AS tabela_ref,
            cr.name      AS coluna_ref
        FROM sys.foreign_keys fk
        JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
        JOIN sys.tables tp  ON fkc.parent_object_id = tp.object_id
        JOIN sys.schemas sp ON tp.schema_id = sp.schema_id
        JOIN sys.columns cp ON fkc.parent_object_id = cp.object_id 
                            AND fkc.parent_column_id = cp.column_id
        JOIN sys.tables tr  ON fkc.referenced_object_id = tr.object_id
        JOIN sys.schemas sr ON tr.schema_id = sr.schema_id
        JOIN sys.columns cr ON fkc.referenced_object_id = cr.object_id 
                            AND fkc.referenced_column_id = cr.column_id
        ORDER BY tp.name, fk.name;
    """,

    "05_indices": """
        SELECT 
            s.name       AS esquema,
            t.name       AS tabela,
            i.name       AS nome_indice,
            i.type_desc  AS tipo_indice,
            i.is_unique  AS eh_unico,
            c.name       AS coluna,
            ic.key_ordinal AS ordem
        FROM sys.indexes i
        JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
        JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
        JOIN sys.tables t ON i.object_id = t.object_id
        JOIN sys.schemas s ON t.schema_id = s.schema_id
        WHERE i.is_primary_key = 0 AND i.type > 0
        ORDER BY s.name, t.name, i.name, ic.key_ordinal;
    """,

    "06_views": """
        SELECT 
            TABLE_SCHEMA AS esquema,
            TABLE_NAME   AS view_nome,
            VIEW_DEFINITION AS definicao
        FROM INFORMATION_SCHEMA.VIEWS
        ORDER BY TABLE_SCHEMA, TABLE_NAME;
    """,

    "07_procedures": """
        SELECT 
            ROUTINE_SCHEMA   AS esquema,
            ROUTINE_NAME     AS procedure_nome,
            ROUTINE_TYPE     AS tipo,
            CREATED          AS criado_em,
            LAST_ALTERED     AS alterado_em
        FROM INFORMATION_SCHEMA.ROUTINES
        WHERE ROUTINE_TYPE = 'PROCEDURE'
        ORDER BY ROUTINE_SCHEMA, ROUTINE_NAME;
    """,

    "08_tabelas_core_amostra_movimento": """
        SELECT TOP 5 * FROM Movimento;
    """,

    "09_tabelas_core_amostra_itensmov": """
        SELECT TOP 5 * FROM ItensMov;
    """,

    "10_tabelas_core_amostra_clifor": """
        SELECT TOP 5 * FROM Cli_For;
    """,

    "11_tabelas_core_amostra_produtos": """
        SELECT TOP 5 * FROM Produtos;
    """,

    "12_tabelas_core_amostra_estoque": """
        SELECT TOP 5 * FROM Estoque;
    """,

    "13_tabelas_core_amostra_vendedores": """
        SELECT TOP 5 * FROM Vendedores;
    """,
}


# ============================================================================
# EXECUÇÃO
# ============================================================================
def executar_discovery():
    print("=" * 60)
    print("  DISCOVERY DO BANCO - GM Limpeza")
    print(f"  Servidor: {SERVIDOR}")
    print(f"  Banco:    {BANCO}")
    print(f"  Início:   {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("=" * 60)
    
    conn = conectar()
    cursor = conn.cursor()
    
    arquivos_gerados = []
    
    for nome, query in QUERIES.items():
        arquivo = os.path.join(PASTA_SAIDA, f"{nome}.csv")
        print(f"\n>> Executando: {nome}...")
        
        try:
            cursor.execute(query)
            colunas = [desc[0] for desc in cursor.description]
            linhas = cursor.fetchall()
            
            with open(arquivo, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(colunas)
                for linha in linhas:
                    writer.writerow(linha)
            
            print(f"   [OK] {len(linhas)} linhas → {arquivo}")
            arquivos_gerados.append(arquivo)
            
        except Exception as e:
            print(f"   [ERRO] {e}")
    
    cursor.close()
    conn.close()
    
    print("\n" + "=" * 60)
    print(f"  Concluído! {len(arquivos_gerados)} arquivos gerados em: {PASTA_SAIDA}/")
    print("=" * 60)
    print("\nPróximo passo: envie a pasta 'discovery_output' para o Claude.")


if __name__ == "__main__":
    executar_discovery()