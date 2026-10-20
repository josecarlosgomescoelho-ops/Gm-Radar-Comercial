"""Execute na raiz do projeto: python preparar_login_gestao.py --criar-local.

Localiza o cadastro usado pelo auth.py sem importar ou modificar esse modulo.
Se o cadastro existe, apenas lista as contas de gestao. Caso esteja ausente,
--criar-local permite configurar uma conta de teste com senha digitada no terminal.
"""
import argparse
import getpass
import io
import json
import os
import re
from pathlib import Path

import pandas as pd


def localizar_cadastro(base):
    candidatos = set()
    ignorar = {".git", ".venv", "venv", "node_modules", "__pycache__"}
    for pasta, diretorios, arquivos in os.walk(base):
        diretorios[:] = [d for d in diretorios if d not in ignorar]
        if "auth.py" not in arquivos:
            continue
        auth = Path(pasta) / "auth.py"
        fonte = auth.read_text(encoding="utf-8-sig")
        if "check_session" not in fonte or "usuarios.parquet" not in fonte:
            continue
        match = re.search(
            r'^CACHE_DIR\s*=\s*Path\(__file__\)\.(parent(?:\.parent)*)\s*/\s*[\'"]cache[\'"]',
            fonte, flags=re.MULTILINE,
        )
        if not match:
            raise ValueError(f"Conferir a configuracao de CACHE_DIR em {auth}.")
        cache = auth.resolve()
        for _ in match.group(1).split("."):
            cache = cache.parent
        candidatos.add(cache / "cache" / "usuarios.parquet")
    if len(candidatos) != 1:
        raise ValueError(
            f"Encontrados {len(candidatos)} caminhos de cadastro. "
            "Execute na raiz do projeto do Radar, onde esta scripts/etl_cache.py."
        )
    return candidatos.pop()


def listar_gestao(arquivo):
    df = pd.read_parquet(arquivo)
    colunas = ["CodVendedor", "NomeVendedor", "Role", "Active", "FirstLogin", "ResetRequired"]
    if not set(colunas).issubset(df.columns):
        raise ValueError("O cadastro existente nao tem as colunas esperadas pelo auth.py.")
    gestao = df.loc[df["Role"].eq("gestao"), colunas]
    if gestao.empty:
        print("Cadastro existente, sem contas com Role=gestao.")
    else:
        print(gestao.to_string(index=False))


def criar_gestao_local(arquivo, senha):
    if arquivo.exists():
        raise FileExistsError("O cadastro ja existe; consulte as contas existentes.")
    if not senha or len(senha.encode("utf-8")) > 72:
        raise ValueError("A senha deve ter de 1 a 72 bytes em UTF-8, conforme o bcrypt.")
    try:
        import bcrypt
    except ImportError as exc:
        raise RuntimeError(
            "Falta bcrypt neste Python. Use o ambiente do Radar ou execute: "
            "python -m pip install bcrypt"
        ) from exc
    senha_hash = bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    df = pd.DataFrame([{
        "CodVendedor": "gestao_teste",
        "NomeVendedor": "Gestao (teste local)",
        "Role": "gestao",
        "PasswordHash": senha_hash,
        "FirstLogin": False,       # senha escolhida durante esta configuracao
        "ResetRequired": False,
        "Active": True,
        "CreatedAt": pd.Timestamp.now(),
        "LastLogin": pd.NaT,
        "LastFilters": json.dumps([]),
    }])
    # Serializa antes de criar o arquivo. "xb" impede sobrescrever um cadastro
    # que apareca enquanto a senha estiver sendo configurada.
    buffer = io.BytesIO()
    df.to_parquet(buffer, index=False)
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    criado = False
    try:
        with arquivo.open("xb") as destino:
            criado = True
            destino.write(buffer.getvalue())
    except BaseException:
        if criado:
            arquivo.unlink(missing_ok=True)
        raise


def main():
    parser = argparse.ArgumentParser(description="Consultar ou preparar o login local de gestao.")
    parser.add_argument("--criar-local", action="store_true", help="Criar gestao_teste quando o cadastro estiver ausente.")
    args = parser.parse_args()
    base = Path.cwd().resolve()
    if not (base / "scripts" / "etl_cache.py").is_file():
        raise ValueError("Execute na raiz do projeto do Radar, ao lado da pasta scripts.")
    arquivo = localizar_cadastro(base)
    print(f"Cadastro usado pelo Radar: {arquivo}")
    if arquivo.exists():
        listar_gestao(arquivo)
        return
    print("Cadastro ausente neste caminho.")
    if not args.criar_local:
        print("Para preparar a conta de teste, execute novamente com --criar-local.")
        return
    print("Configurando usuario local: gestao_teste / perfil: gestao.")
    senha = getpass.getpass("Escolha a senha para gestao_teste: ")
    confirmacao = getpass.getpass("Repita a senha: ")
    if senha != confirmacao:
        raise ValueError("As senhas nao coincidem. Execute novamente.")
    criar_gestao_local(arquivo, senha)
    print("Cadastro criado. Usuario: gestao_teste")
    print("Entre no Radar com a senha que voce acabou de escolher.")


if __name__ == "__main__":
    try:
        main()
    except Exception as erro:
        raise SystemExit(f"Nao foi possivel concluir: {erro}")
