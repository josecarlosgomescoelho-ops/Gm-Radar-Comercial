"""
Script de debug para diagnosticar problema de rentabilidade no painel de gestão
"""
import pandas as pd
import numpy as np
from datetime import date
from pathlib import Path

CACHE_DIR = Path(__file__).parent.parent / "cache"

# Carregar dados
print("📦 Carregando dados...")
df_mov = pd.read_parquet(CACHE_DIR / "movimentos.parquet")
df_itens = pd.read_parquet(CACHE_DIR / "itens.parquet")

# Converter datas
df_mov["DataFaturamento"] = pd.to_datetime(df_mov["DataFaturamento"])
df_itens["DataFaturamento"] = pd.to_datetime(df_itens["DataFaturamento"])

# Período atual (mês atual)
HOJE = date.today()
dt_inicio = HOJE.replace(day=1)
dt_fim = HOJE

d0 = pd.to_datetime(dt_inicio)
d1 = pd.to_datetime(dt_fim)

# Filtrar período
df_mov = df_mov[(df_mov["DataFaturamento"] >= d0) & (df_mov["DataFaturamento"] <= d1)]
df_itens = df_itens[(df_itens["DataFaturamento"] >= d0) & (df_itens["DataFaturamento"] <= d1)]

print(f"\n📅 Período: {dt_inicio} a {dt_fim}")
print(f"📊 Movimentos no período: {len(df_mov)}")
print(f"📦 Itens no período: {len(df_itens)}")
print(f"💰 Faturamento total: R$ {df_mov['ValorLiquido'].sum():,.2f}")
print(f"💸 Custo total: R$ {df_itens['CustoItem'].sum():,.2f}")

# Preencher Supervisor
df_mov["Supervisor"] = df_mov["Supervisor"].fillna("Outros")

print("\n" + "="*80)
print("🔍 ANÁLISE POR SUPERVISOR")
print("="*80)

for sup in sorted(df_mov["Supervisor"].unique()):
    print(f"\n📋 Supervisor: {sup}")
    print("-" * 80)

    mov_sup = df_mov[df_mov["Supervisor"] == sup]

    print(f"   Pedidos: {mov_sup['IdMov'].nunique()}")
    print(f"   Vendedores: {mov_sup['CodVendedor'].nunique()}")
    print(f"   Faturamento: R$ {mov_sup['ValorLiquido'].sum():,.2f}")

    # Método ANTIGO (potencialmente incorreto)
    itens_old = df_itens[df_itens["CodVendedor"].isin(mov_sup["CodVendedor"].unique())]
    custo_old = itens_old["CustoItem"].sum()
    margem_old = mov_sup["ValorLiquido"].sum() - custo_old
    rent_old = (margem_old / mov_sup["ValorLiquido"].sum() * 100) if mov_sup["ValorLiquido"].sum() > 0 else 0

    print(f"\n   ❌ MÉTODO ANTIGO (por CodVendedor):")
    print(f"      Itens encontrados: {len(itens_old)}")
    print(f"      Custo: R$ {custo_old:,.2f}")
    print(f"      Margem: R$ {margem_old:,.2f}")
    print(f"      Rentabilidade: {rent_old:.2f}%")

    # Método NOVO (correto)
    itens_new = df_itens[df_itens["IdMov"].isin(mov_sup["IdMov"].unique())]
    custo_new = itens_new["CustoItem"].sum()
    margem_new = mov_sup["ValorLiquido"].sum() - custo_new
    rent_new = (margem_new / mov_sup["ValorLiquido"].sum() * 100) if mov_sup["ValorLiquido"].sum() > 0 else 0

    print(f"\n   ✅ MÉTODO NOVO (por IdMov):")
    print(f"      Itens encontrados: {len(itens_new)}")
    print(f"      Custo: R$ {custo_new:,.2f}")
    print(f"      Margem: R$ {margem_new:,.2f}")
    print(f"      Rentabilidade: {rent_new:.2f}%")

    # Diferença
    if abs(rent_old - rent_new) > 0.01:
        print(f"\n   ⚠️  DIFERENÇA: {abs(rent_old - rent_new):.2f}% pontos percentuais")
        print(f"      Itens a mais/menos: {len(itens_old) - len(itens_new)}")

print("\n" + "="*80)
print("✅ Análise concluída!")
print("="*80)
