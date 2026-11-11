
import os
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import duckdb
import pandas as pd
from tabulate import tabulate
from dateutil.relativedelta import relativedelta

FUSO_HORARIO = ZoneInfo("America/Sao_Paulo")

def obter_competencia():
    configuracao = os.getenv("COMPETENCIA", "auto").strip()

    if configuracao.lower() == "auto":
        hoje = datetime.now(FUSO_HORARIO)
        primeiro_dia = hoje.replace(day=1)
        mes_anterior = primeiro_dia - relativedelta(months=1)
        return mes_anterior.strftime("%Y-%m")

    try:
        datetime.strptime(configuracao, "%Y-%m")
    except ValueError:
        raise ValueError(
            "COMPETENCIA inválida. Use AAAA-MM ou 'auto'."
        )

    return configuracao


COMPETENCIA = obter_competencia()
DB_FILE = Path("data") / COMPETENCIA / "cnpj.duckdb"

if not DB_FILE.exists():
    raise FileNotFoundError(
        f"Banco de dados não encontrado: {DB_FILE}. "
        "Execute o pipeline antes de iniciar as consultas."
    )

con = duckdb.connect(str(DB_FILE), read_only=True)


def consultar(sql):
    resultado = con.execute(sql).fetchdf()

    print(
        tabulate(
            resultado,
            headers="keys",
            tablefmt="psql",
            showindex=False
        )
    )

    print(f"\nTotal de registros exibidos: {len(resultado)}")
    return resultado


print("\nAmbiente de consulta CNPJ iniciado!")
print(f"Competência: {COMPETENCIA}")
print("DuckDB, Pandas e Tabulate disponíveis.")
print("\nExemplo:")
print("consultar('SELECT * FROM empresas_consolidada LIMIT 10')")
print("\nDigite exit() para sair.\n")
