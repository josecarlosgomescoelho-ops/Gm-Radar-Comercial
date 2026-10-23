"""Ordem alfabetica para nomes, com acentos ignorados e codigo como desempate."""
import unicodedata


def chave_nome(valor):
    texto = '' if valor is None else str(valor).strip()
    return ''.join(c for c in unicodedata.normalize('NFKD', texto) if not unicodedata.combining(c)).casefold()


def ordenar_registros(registros, nome, codigo):
    return sorted(registros, key=lambda r: (chave_nome(r.get(nome)), str(r.get(codigo, ''))))


def ordenar_dataframe(df, nome, codigo):
    posicoes = sorted(range(len(df)), key=lambda i: (chave_nome(df.iloc[i][nome]), str(df.iloc[i][codigo])))
    return df.iloc[posicoes].copy()
