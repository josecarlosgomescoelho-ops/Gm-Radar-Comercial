"""
GM Limpeza — CLI de Gestão de Usuários
Uso:
  python scripts/criar_usuario.py --seed           # popula todos os usuários do parquet
  python scripts/criar_usuario.py --list           # lista todos os usuários
  python scripts/criar_usuario.py --reset COD      # força redefinição de senha no próximo login
  python scripts/criar_usuario.py --deactivate COD # desativa conta
  python scripts/criar_usuario.py --activate COD   # reativa conta
"""

import sys
import argparse
import bcrypt
import pandas as pd
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
CACHE_DIR = ROOT / "cache"
USUARIOS_FILE = CACHE_DIR / "usuarios.parquet"


def _hash(senha: str) -> str:
    return bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()


def _senha_provisoria(cod: str) -> str:
    return f"gm@{cod}"


def _load() -> pd.DataFrame:
    if not USUARIOS_FILE.exists():
        return _vazio()
    return pd.read_parquet(USUARIOS_FILE)


def _save(df: pd.DataFrame):
    df.to_parquet(USUARIOS_FILE, index=False)
    print(f"  Salvo em {USUARIOS_FILE}")


def _vazio() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "CodVendedor", "NomeVendedor", "Role", "PasswordHash",
        "FirstLogin", "ResetRequired", "Active",
        "CreatedAt", "LastLogin", "LastFilters",
    ])


def _nova_linha(cod: str, nome: str, role: str, senha: str) -> dict:
    return {
        "CodVendedor": cod,
        "NomeVendedor": nome,
        "Role": role,
        "PasswordHash": _hash(senha),
        "FirstLogin": True,
        "ResetRequired": False,
        "Active": True,
        "CreatedAt": datetime.now(),
        "LastLogin": pd.NaT,
        "LastFilters": "",
    }


# ============================================================================
# COMANDOS
# ============================================================================

def cmd_seed():
    """Popula usuários a partir do vendedores.parquet + contas especiais."""
    vendedores_file = CACHE_DIR / "vendedores.parquet"
    supervisores_file = CACHE_DIR / "supervisores.parquet"

    if not vendedores_file.exists():
        print("ERRO: cache/vendedores.parquet não encontrado. Rode o ETL primeiro.")
        sys.exit(1)

    df_vend = pd.read_parquet(vendedores_file)
    df_sup = pd.read_parquet(supervisores_file) if supervisores_file.exists() else pd.DataFrame()

    df = _load()
    existentes = set(df["CodVendedor"].tolist())
    novos = []

    # Contas especiais
    especiais = [
        ("dev", "Victor Monteiro (Dev)", "dev", "dev@gm2024"),
        ("gestao", "Gestão GM Limpeza", "gestao", "gestao@gm2024"),
    ]
    for cod, nome, role, senha in especiais:
        if cod not in existentes:
            novos.append(_nova_linha(cod, nome, role, senha))
            print(f"  + {role.upper():<10} {cod:<12} {nome}")
        else:
            print(f"  = já existe: {cod}")

    # Supervisores
    codigos_sup = set()
    if not df_sup.empty:
        for _, row in df_sup.iterrows():
            cod = str(row["CodVendedor"]).strip()
            nome = str(row["Supervisor"]).strip()
            codigos_sup.add(cod)
            if cod not in existentes and nome not in ("VENDEDOR PADRAO",):
                novos.append(_nova_linha(cod, nome, "gestao", _senha_provisoria(cod)))
                print(f"  + SUPERVISOR   {cod:<12} {nome}")
            elif cod not in existentes:
                pass  # ignora VENDEDOR PADRAO
            else:
                print(f"  = já existe: {cod} ({nome})")

    # Vendedores ativos (com supervisor)
    vendedores_validos = df_vend[
        df_vend["CodSupervisor"].notna() &
        (df_vend["CodSupervisor"] != "") &
        (~df_vend["Vendedor"].str.contains("Separador|Erro|INATIVADOS|EMPRESA|PADRAO", case=False, na=False))
    ]

    for _, row in vendedores_validos.iterrows():
        cod = str(row["CodVendedor"]).strip()
        nome = str(row["Vendedor"]).strip()
        if cod in existentes or cod in codigos_sup:
            print(f"  = já existe: {cod} ({nome})")
            continue
        novos.append(_nova_linha(cod, nome, "vendedor", _senha_provisoria(cod)))
        print(f"  + VENDEDOR     {cod:<12} {nome}")

    if novos:
        df_novos = pd.DataFrame(novos)
        df = pd.concat([df, df_novos], ignore_index=True)
        _save(df)
        print(f"\n  {len(novos)} usuário(s) criado(s).")
    else:
        print("\n  Nenhum usuário novo para criar.")

    print()
    cmd_list()


def cmd_list():
    """Lista todos os usuários com senhas provisórias."""
    df = _load()
    if df.empty:
        print("Nenhum usuário cadastrado.")
        return

    print("\n" + "=" * 80)
    print(f"{'CÓD':<12} {'NOME':<28} {'ROLE':<10} {'SENHA PROV.':<18} {'ATIVO':<6} {'PRIMEIRO LOGIN'}")
    print("=" * 80)

    for _, row in df.iterrows():
        cod = str(row["CodVendedor"])
        nome = str(row["NomeVendedor"])[:27]
        role = str(row["Role"])
        ativo = "SIM" if row["Active"] else "NÃO"
        first = "Pendente" if row["FirstLogin"] else "Concluído"

        if role in ("dev", "gestao"):
            senha_exibir = f"{cod}@gm2024"
        else:
            senha_exibir = _senha_provisoria(cod)

        print(f"{cod:<12} {nome:<28} {role:<10} {senha_exibir:<18} {ativo:<6} {first}")

    print("=" * 80)
    print(f"Total: {len(df)} usuário(s)\n")


def cmd_reset(cod: str):
    df = _load()
    if cod not in df["CodVendedor"].values:
        print(f"ERRO: usuário '{cod}' não encontrado.")
        sys.exit(1)
    df.loc[df["CodVendedor"] == cod, "ResetRequired"] = True
    _save(df)
    nome = df.loc[df["CodVendedor"] == cod, "NomeVendedor"].iloc[0]
    print(f"Reset ativado para {nome} ({cod}). Será solicitado na próxima sessão.")


def cmd_deactivate(cod: str):
    df = _load()
    if cod not in df["CodVendedor"].values:
        print(f"ERRO: usuário '{cod}' não encontrado.")
        sys.exit(1)
    df.loc[df["CodVendedor"] == cod, "Active"] = False
    _save(df)
    print(f"Conta '{cod}' desativada.")


def cmd_activate(cod: str):
    df = _load()
    if cod not in df["CodVendedor"].values:
        print(f"ERRO: usuário '{cod}' não encontrado.")
        sys.exit(1)
    df.loc[df["CodVendedor"] == cod, "Active"] = True
    _save(df)
    print(f"Conta '{cod}' reativada.")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gestão de usuários — GM Limpeza Radar")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--seed", action="store_true", help="Popula usuários do parquet")
    group.add_argument("--list", action="store_true", help="Lista todos os usuários")
    group.add_argument("--reset", metavar="COD", help="Ativa flag de reset para o usuário")
    group.add_argument("--deactivate", metavar="COD", help="Desativa conta")
    group.add_argument("--activate", metavar="COD", help="Reativa conta")

    args = parser.parse_args()

    if args.seed:
        cmd_seed()
    elif args.list:
        cmd_list()
    elif args.reset:
        cmd_reset(args.reset)
    elif args.deactivate:
        cmd_deactivate(args.deactivate)
    elif args.activate:
        cmd_activate(args.activate)
