import os
import json
import zipfile
import logging
from decimal import Decimal, InvalidOperation
from pathlib import Path
from datetime import datetime, timezone

import requests
import pandas as pd
import duckdb
import pyarrow as pa
import pyarrow.parquet as pq


# ==========================================
# CONFIGURAÇÕES
# ==========================================

BASE = Path("/app/data")

BRONZE = BASE / "bronze"
SILVER = BASE / "silver"
GOLD = BASE / "gold"

ZIP_FILE = BRONZE / "Empresas0.zip"
PARQUET_FILE = SILVER / "empresas.parquet"
DB_FILE = BASE / "cnpj.duckdb"

import os
from datetime import datetime
from dateutil.relativedelta import relativedelta

SOURCE_BASE_URL = os.getenv("SOURCE_BASE_URL")


def obter_competencia():
    configuracao = os.getenv("COMPETENCIA", "auto").strip()

    if configuracao.lower() == "auto":
        hoje = datetime.now()
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

def obter_arquivos():
    configuracao = os.getenv("ARQUIVOS", "todos")

    if configuracao.lower() == "todos":
        return [f"Empresas{i}" for i in range(10)]

    return [
        arquivo.strip()
        for arquivo in configuracao.split(",")
        if arquivo.strip()
    ]


ARQUIVOS = obter_arquivos()

URLS = {
    arquivo: (
        f"{SOURCE_BASE_URL}/{COMPETENCIA}/{arquivo}.zip"
    )
    for arquivo in ARQUIVOS
}

COLUNAS = [
    "cnpj_basico",
    "razao_social",
    "natureza_juridica",
    "qualificacao_responsavel",
    "capital_social",
    "porte_empresa",
    "ente_federativo_responsavel"
]

MAPA_PORTE = {
    "00": "Não informado",
    "": "Não informado",
    "01": "Microempresa",
    "03": "Empresa de Pequeno Porte",
    "05": "Demais"
}

for pasta in [BRONZE, SILVER, GOLD]:
    pasta.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


# ==========================================
# EXTRACT
# ==========================================


def extract():

    if not URLS:
        raise ValueError("Nenhuma URL de arquivo foi configurada.")

    logging.info(f"Competência: {COMPETENCIA}")
    logging.info(f"Arquivos selecionados: {ARQUIVOS}")

    for nome_arquivo, url in URLS.items():

        zip_file = BRONZE / f"{nome_arquivo}.zip"

        if zip_file.exists() and zipfile.is_zipfile(zip_file):
            logging.info(f"{nome_arquivo}.zip já existe. Reutilizando.")
            continue

        logging.info(f"Iniciando download: {nome_arquivo}")

        temp_file = zip_file.with_suffix(".zip.tmp")

        try:
            with requests.get(
                url,
                stream=True,
                timeout=(30, 300)
            ) as response:

                response.raise_for_status()

                with open(temp_file, "wb") as arquivo:
                    for bloco in response.iter_content(
                        chunk_size=8 * 1024 * 1024
                    ):
                        if bloco:
                            arquivo.write(bloco)

            if not zipfile.is_zipfile(temp_file):
                raise ValueError(
                    f"O arquivo recebido para {nome_arquivo} não é um ZIP válido"
                )

            temp_file.replace(zip_file)

            logging.info(f"Download concluído: {nome_arquivo}")

        except Exception:
            temp_file.unlink(missing_ok=True)
            raise

# ==========================================
# LOAD + TRANSFORM
# ==========================================

def transform():

    logging.info("Iniciando transformação Silver")
    logging.info(f"Competência: {COMPETENCIA}")
    logging.info(f"Arquivos selecionados: {ARQUIVOS}")

    # Valida todos os ZIPs antes de iniciar
    for nome_arquivo in ARQUIVOS:

        zip_file = BRONZE / f"{nome_arquivo}.zip"

        if not zipfile.is_zipfile(zip_file):
            raise ValueError(
                f"ZIP inexistente ou inválido: {zip_file.name}"
            )

    # Schema fixo para garantir consistência entre os blocos
    schema = pa.schema([
        ("cnpj_basico", pa.string()),
        ("razao_social", pa.string()),
        ("natureza_juridica", pa.string()),
        ("qualificacao_responsavel", pa.string()),
        ("capital_social", pa.decimal128(20, 2)),
        ("porte_empresa", pa.string()),
        ("porte_descricao", pa.string()),
        ("ente_federativo_responsavel", pa.string()),
        ("cnpj_basico_valido", pa.bool_()),
        ("capital_social_valido", pa.bool_()),
        ("competencia", pa.string())
    ])

    temp_file = PARQUET_FILE.with_suffix(".parquet.tmp")
    temp_file.unlink(missing_ok=True)

    total = 0
    writer = None

    def converter_capital(valor):

        if not valor:
            return None

        try:
            return Decimal(
                valor.replace(",", ".")
            ).quantize(Decimal("0.01"))

        except InvalidOperation:
            return None

    try:

        # Percorre todos os arquivos selecionados
        for nome_arquivo in ARQUIVOS:

            zip_file = BRONZE / f"{nome_arquivo}.zip"

            logging.info(
                f"Transformando arquivo: {nome_arquivo}"
            )

            with zipfile.ZipFile(zip_file) as arquivo_zip:

                arquivos_csv = [
                    nome for nome in arquivo_zip.namelist()
                    if not nome.endswith("/")
                ]

                if len(arquivos_csv) != 1:
                    raise ValueError(
                        f"{nome_arquivo}: esperado 1 CSV, "
                        f"encontrados: {len(arquivos_csv)}"
                    )

                with arquivo_zip.open(arquivos_csv[0]) as arquivo:

                    leitor = pd.read_csv(
                        arquivo,
                        sep=";",
                        header=None,
                        names=COLUNAS,
                        dtype="string",
                        encoding="latin-1",
                        chunksize=250_000,
                        on_bad_lines="error",
                        keep_default_na=False
                    )

                    for df in leitor:

                        # Padronização dos textos
                        for coluna in COLUNAS:
                            df[coluna] = df[coluna].str.strip()

                        # Classificação do porte da empresa
                        df["porte_descricao"] = (
                            df["porte_empresa"]
                            .map(MAPA_PORTE)
                            .fillna("Código não mapeado")
                        )

                        # Validação do CNPJ básico
                        df["cnpj_basico_valido"] = (
                            df["cnpj_basico"]
                            .str.fullmatch(r"\d{8}")
                        )

                        # Validação e conversão do capital social
                        capital_original = df["capital_social"]

                        df["capital_social_valido"] = (
                            capital_original.str.fullmatch(
                                r"\d+(,\d{2})?"
                            )
                        )

                        df["capital_social"] = [
                            converter_capital(valor)
                            for valor in capital_original
                        ]

                        # Rastreabilidade
                        df["competencia"] = COMPETENCIA

                        tabela = pa.Table.from_pandas(
                            df,
                            schema=schema,
                            preserve_index=False
                        )

                        # Um único writer para todos os arquivos
                        if writer is None:
                            writer = pq.ParquetWriter(
                                temp_file,
                                schema,
                                compression="snappy"
                            )

                        writer.write_table(tabela)
                        total += len(df)

                        logging.info(
                            "%s | Registros acumulados: %s",
                            nome_arquivo,
                            f"{total:,}"
                        )

        if writer is not None:
            writer.close()
            writer = None

        if total == 0:
            raise ValueError(
                "Nenhum registro foi processado"
            )

        # Só substitui o arquivo final quando tudo termina bem
        temp_file.replace(PARQUET_FILE)

        logging.info(
            "Silver concluída. Total: %s registros",
            f"{total:,}"
        )

        return total

    except Exception:

        if writer is not None:
            writer.close()

        temp_file.unlink(missing_ok=True)
        raise

# ==========================================
# QUALITY
# ==========================================


def quality(total):

    logging.info("Executando testes de qualidade")

    con = duckdb.connect(str(DB_FILE))

    try:
        # Carrega todos os campos da Silver no DuckDB
        con.execute(f"""
            CREATE OR REPLACE TABLE empresas AS
            SELECT *
            FROM read_parquet('{PARQUET_FILE}')
        """)

        # Verifica se a coluna de descrição do porte existe
        colunas = [
            linha[0]
            for linha in con.execute(
                "DESCRIBE empresas"
            ).fetchall()
        ]

        if "porte_descricao" not in colunas:
            raise ValueError(
                "A coluna porte_descricao não existe na Silver. "
                "Execute novamente a transformação."
            )

        resultado = con.execute("""
            SELECT
                COUNT(*) AS total,
                COUNT(DISTINCT cnpj_basico) AS cnpjs_unicos,
                COUNT(*) FILTER (
                    WHERE cnpj_basico_valido = FALSE
                ) AS cnpjs_invalidos,
                COUNT(*) FILTER (
                    WHERE capital_social IS NULL
                ) AS capitais_invalidos,
                COUNT(*) FILTER (
                    WHERE capital_social < 0
                ) AS capitais_negativos,
                COUNT(*) FILTER (
                    WHERE natureza_juridica IS NULL
                       OR natureza_juridica = ''
                ) AS naturezas_ausentes,
                COUNT(*) FILTER (
                    WHERE porte_empresa IS NULL
                       OR porte_empresa = ''
                ) AS portes_ausentes
            FROM empresas
        """).fetchdf()

        resultado = resultado.iloc[0].to_dict()

        total_arquivo = int(resultado["total"])

        if total_arquivo != total:
            raise ValueError(
                f"Divergência de registros: Silver={total}, "
                f"DuckDB={total_arquivo}"
            )

        logging.info(
            "Resultado dos testes de qualidade: %s",
            resultado
        )

        return {
            chave: int(valor)
            for chave, valor in resultado.items()
        }

    finally:
        con.close()

# ==========================================
# GOLD - MODELAGEM ANALÍTICA
# ==========================================


def create_gold():

    logging.info("Iniciando geração da camada Gold")

    # Diretório para operações temporárias em disco
    TEMP_DIR = BASE / "tmp"
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(str(DB_FILE))

    try:
        # Controle de consumo de recursos
        con.execute("SET memory_limit = '2GB'")
        con.execute("SET threads = 2")
        con.execute("SET preserve_insertion_order = false")
        con.execute(f"SET temp_directory = '{TEMP_DIR}'")
        con.execute("SET max_temp_directory_size = '10GB'")

        # Remove arquivos de execuções anteriores
        arquivos_gold = [
            GOLD / "empresas_por_natureza.parquet",
            GOLD / "capital_por_porte.parquet",
            GOLD / "top_empresas_por_porte.parquet",
            GOLD / "menores_empresas_por_porte.parquet"
        ]

        for arquivo in arquivos_gold:
            arquivo.unlink(missing_ok=True)

        # 1. Distribuição por natureza jurídica
        logging.info(
            "Gerando distribuição por natureza jurídica"
        )

        con.execute(f"""
            COPY (
                SELECT
                    natureza_juridica,
                    COUNT(*) AS quantidade_empresas,
                    SUM(capital_social) AS capital_total,
                    AVG(capital_social) AS capital_medio
                FROM empresas
                GROUP BY natureza_juridica
                ORDER BY quantidade_empresas DESC
            )
            TO '{GOLD / "empresas_por_natureza.parquet"}'
            (FORMAT PARQUET, COMPRESSION SNAPPY)
        """)

        # 2. Distribuição do capital social por porte
        logging.info(
            "Gerando distribuição de capital social por porte"
        )

        con.execute(f"""
            COPY (
                SELECT
                    porte_empresa,
                    porte_descricao,
                    COUNT(*) AS quantidade_empresas,
                    SUM(capital_social) AS capital_total,
                    AVG(capital_social) AS capital_medio
                FROM empresas
                GROUP BY
                    porte_empresa,
                    porte_descricao
                ORDER BY quantidade_empresas DESC
            )
            TO '{GOLD / "capital_por_porte.parquet"}'
            (FORMAT PARQUET, COMPRESSION SNAPPY)
        """)

        logging.info("Camada Gold criada com sucesso")

    finally:
        con.close()

# ==========================================
# AUDITORIA E EXECUÇÃO
# ==========================================

def main():

    inicio = datetime.now(timezone.utc)

    logging.info("===== PIPELINE CNPJ INICIADO =====")

    extract()

    total = transform()

    indicadores = quality(total)

    create_gold()

    auditoria = {
        "competencia": COMPETENCIA,
        "arquivos": [
            f"{nome}.zip" for nome in ARQUIVOS
        ],
        "data_execucao_utc": inicio.isoformat(),
        "total_registros": total,
        "qualidade": indicadores,
        "status": "SUCESSO"
    }

    with open(
        BASE / "auditoria.json",
        "w",
        encoding="utf-8"
    ) as arquivo:
        json.dump(
            auditoria,
            arquivo,
            ensure_ascii=False,
            indent=4
        )

    logging.info("===== PIPELINE FINALIZADO =====")


if __name__ == "__main__":
    main()