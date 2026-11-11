import os
import json
import zipfile
import logging
import threading
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
import pandas as pd
import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from dateutil.relativedelta import relativedelta

FUSO_HORARIO = ZoneInfo("America/Sao_Paulo")

SOURCE_BASE_URL = os.getenv("SOURCE_BASE_URL")


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

# Diretório exclusivo para cada competência
DATA_ROOT = Path("/app/data")
BASE = DATA_ROOT / COMPETENCIA

BRONZE = BASE / "bronze"
SILVER = BASE / "silver"
GOLD = BASE / "gold"

ZIP_FILE = BRONZE / "Empresas0.zip"
PARQUET_FILE = SILVER / "empresas.parquet"
DB_FILE = BASE / "cnpj.duckdb"


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

def extract_naturezas():

    logging.info("Iniciando download da tabela de naturezas jurídicas")

    url = (
        f"{SOURCE_BASE_URL.rstrip('/')}/"
        f"{COMPETENCIA}/Naturezas.zip"
    )

    zip_file = BRONZE / "Naturezas.zip"
    temp_file = zip_file.with_suffix(".zip.tmp")

    # Reaproveita o arquivo se já existir e for um ZIP válido
    if zip_file.exists() and zipfile.is_zipfile(zip_file):
        logging.info("Tabela de naturezas já existe. Reutilizando.")
        return

    try:
        with requests.get(
            url,
            stream=True,
            timeout=(30, 300)
        ) as response:

            response.raise_for_status()

            with open(temp_file, "wb") as arquivo:
                for bloco in response.iter_content(
                    chunk_size=1024 * 1024
                ):
                    if bloco:
                        arquivo.write(bloco)

        if not zipfile.is_zipfile(temp_file):
            raise ValueError("Naturezas.zip inválido.")

        with zipfile.ZipFile(temp_file) as arquivo_zip:
            arquivos_csv = [
                nome for nome in arquivo_zip.namelist()
                if not nome.endswith("/")
            ]

            if len(arquivos_csv) != 1:
                raise ValueError(
                    "Esperado exatamente um CSV em Naturezas.zip."
                )

        temp_file.replace(zip_file)

        logging.info(
            "Download da tabela de naturezas concluído: %s",
            zip_file.name
        )

    except Exception:
        temp_file.unlink(missing_ok=True)
        raise



def extract_qualificacoes():

    logging.info("Iniciando download da tabela de qualificações")

    url = (
        f"{SOURCE_BASE_URL.rstrip('/')}/"
        f"{COMPETENCIA}/Qualificacoes.zip"
    )

    zip_file = BRONZE / "Qualificacoes.zip"
    temp_file = zip_file.with_suffix(".zip.tmp")

    # Reaproveita o arquivo se já existir e for um ZIP válido
    if zip_file.exists() and zipfile.is_zipfile(zip_file):
        logging.info("Tabela de qualificações já existe. Reutilizando.")
        return

    try:
        with requests.get(
            url,
            stream=True,
            timeout=(30, 300)
        ) as response:

            response.raise_for_status()

            with open(temp_file, "wb") as arquivo:
                for bloco in response.iter_content(
                    chunk_size=1024 * 1024
                ):
                    if bloco:
                        arquivo.write(bloco)

        if not zipfile.is_zipfile(temp_file):
            raise ValueError("Qualificacoes.zip inválido.")

        with zipfile.ZipFile(temp_file) as arquivo_zip:
            arquivos_csv = [
                nome for nome in arquivo_zip.namelist()
                if not nome.endswith("/")
            ]

            if len(arquivos_csv) != 1:
                raise ValueError(
                    "Esperado exatamente um CSV em Qualificacoes.zip."
                )

        temp_file.replace(zip_file)

        logging.info(
            "Download da tabela de qualificações concluído: %s",
            zip_file.name
        )

    except Exception:
        temp_file.unlink(missing_ok=True)
        raise


# ==========================================

def load_naturezas():
    logging.info("Carregando tabela de naturezas jurídicas")

    zip_file = BRONZE / "Naturezas.zip"

    if not zipfile.is_zipfile(zip_file):
        raise ValueError("Arquivo Naturezas.zip inexistente ou inválido.")

    with zipfile.ZipFile(zip_file) as arquivo_zip:
        arquivos_csv = [
            nome for nome in arquivo_zip.namelist()
            if not nome.endswith("/")
        ]

        if len(arquivos_csv) != 1:
            raise ValueError("Esperado exatamente um CSV em Naturezas.zip.")

        with arquivo_zip.open(arquivos_csv[0]) as arquivo_csv:
            naturezas = pd.read_csv(
                arquivo_csv,
                sep=";",
                encoding="latin-1",
                header=None,
                names=["natureza_juridica", "descricao_natureza"],
                dtype=str,
                quotechar='"'
            )

    naturezas["natureza_juridica"] = naturezas["natureza_juridica"].str.strip()
    naturezas["descricao_natureza"] = naturezas["descricao_natureza"].str.strip()

    if naturezas["natureza_juridica"].duplicated().any():
        raise ValueError("Existem códigos de natureza jurídica duplicados.")

    con = duckdb.connect(str(DB_FILE))

    try:
        con.register("naturezas_df", naturezas)

        con.execute("""
            CREATE OR REPLACE TABLE naturezas_juridicas AS
            SELECT
                natureza_juridica,
                descricao_natureza
            FROM naturezas_df
        """)

        total = con.execute(
            "SELECT COUNT(*) FROM naturezas_juridicas"
        ).fetchone()[0]

        logging.info(
            "Tabela de naturezas jurídicas carregada: %s registros",
            total
        )

    finally:
        con.close()


def load_qualificacoes():

    logging.info("Carregando tabela de qualificações")

    zip_file = BRONZE / "Qualificacoes.zip"

    if not zipfile.is_zipfile(zip_file):
        raise ValueError("Arquivo Qualificacoes.zip inexistente ou inválido.")

    with zipfile.ZipFile(zip_file) as arquivo_zip:
        arquivos_csv = [
            nome for nome in arquivo_zip.namelist()
            if not nome.endswith("/")
        ]

        if len(arquivos_csv) != 1:
            raise ValueError(
                "Esperado exatamente um CSV em Qualificacoes.zip."
            )

        with arquivo_zip.open(arquivos_csv[0]) as arquivo_csv:
            qualificacoes = pd.read_csv(
                arquivo_csv,
                sep=";",
                encoding="latin-1",
                header=None,
                names=[
                    "codigo_qualificacao",
                    "descricao_qualificacao"
                ],
                dtype=str,
                quotechar='"'
            )

    qualificacoes["codigo_qualificacao"] = (
        qualificacoes["codigo_qualificacao"].str.strip()
    )
    qualificacoes["descricao_qualificacao"] = (
        qualificacoes["descricao_qualificacao"].str.strip()
    )

    if qualificacoes["codigo_qualificacao"].duplicated().any():
        raise ValueError("Existem códigos de qualificação duplicados.")

    con = duckdb.connect(str(DB_FILE))

    try:
        con.register("qualificacoes_df", qualificacoes)

        con.execute("""
            CREATE OR REPLACE TABLE qualificacoes_responsavel AS
            SELECT
                codigo_qualificacao,
                descricao_qualificacao
            FROM qualificacoes_df
        """)

        total = con.execute(
            "SELECT COUNT(*) FROM qualificacoes_responsavel"
        ).fetchone()[0]

        logging.info(
            "Tabela de qualificações carregada: %s registros",
            total
        )

    finally:
        con.close()

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

                        print(
                            f"\r{nome_arquivo} | Registros processados: {total:,}",
                            end="",
                            flush=True
                        )

                    print()

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

    TEMP_DIR = BASE / "tmp"
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(str(DB_FILE))

    try:
        # Controle de consumo de recursos
        con.execute("SET memory_limit = '1GB'")
        con.execute("SET threads = 1")
        con.execute("SET preserve_insertion_order = false")
        con.execute(f"SET temp_directory = '{TEMP_DIR}'")
        con.execute("SET max_temp_directory_size = '10GB'")

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
            GOLD / "empresas_por_qualificacao.parquet",
            GOLD / "top_empresas_por_porte.parquet",
            GOLD / "menores_empresas_por_porte.parquet",
            GOLD / "empresas_consolidada.parquet",
            GOLD / "capital_social_atipicos.parquet"
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
                    e.natureza_juridica,
                    COALESCE(
                        nj.descricao_natureza,
                        'Não encontrada'
                    ) AS descricao_natureza,
                    COUNT(*) AS quantidade_empresas,
                    SUM(e.capital_social) AS capital_total,
                    AVG(e.capital_social) AS capital_medio
                FROM empresas e
                LEFT JOIN naturezas_juridicas nj
                    ON TRIM(e.natureza_juridica) = nj.natureza_juridica
                GROUP BY
                    e.natureza_juridica,
                    nj.descricao_natureza
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


        # 3. Distribuição por qualificação do responsável
        logging.info(
            "Gerando distribuição por qualificação do responsável"
        )

        con.execute(f"""
            COPY (
                SELECT
                    TRIM(e.qualificacao_responsavel)
                        AS codigo_qualificacao,
                    COALESCE(
                        q.descricao_qualificacao,
                        'Código não encontrado na tabela oficial'
                    ) AS descricao_qualificacao,
                    COUNT(*) AS quantidade_empresas,
                    SUM(e.capital_social) AS capital_total,
                    AVG(e.capital_social) AS capital_medio
                FROM empresas e
                LEFT JOIN qualificacoes_responsavel q
                    ON TRIM(e.qualificacao_responsavel)
                       = q.codigo_qualificacao
                GROUP BY
                    TRIM(e.qualificacao_responsavel),
                    q.descricao_qualificacao
                ORDER BY quantidade_empresas DESC
            )
            TO '{GOLD / "empresas_por_qualificacao.parquet"}'
            (FORMAT PARQUET, COMPRESSION SNAPPY)
        """)

        # 4. Base geral consolidada de empresas
        logging.info("Gerando base geral consolidada de empresas")

        con.execute(f"""
            COPY (
                SELECT
                    e.cnpj_basico,
                    e.razao_social,
                    e.natureza_juridica,
                    COALESCE(
                        nj.descricao_natureza,
                        'Não encontrada'
                    ) AS descricao_natureza,
                    e.qualificacao_responsavel,
                    COALESCE(
                        q.descricao_qualificacao,
                        'Código não encontrado na tabela oficial'
                    ) AS descricao_qualificacao,
                    e.capital_social,
                    e.porte_empresa,
                    e.porte_descricao,
                    e.ente_federativo_responsavel,
                    e.cnpj_basico_valido,
                    e.capital_social_valido,
                    e.competencia
                FROM empresas e
                LEFT JOIN naturezas_juridicas nj
                    ON TRIM(e.natureza_juridica) = nj.natureza_juridica
                LEFT JOIN qualificacoes_responsavel q
                    ON TRIM(e.qualificacao_responsavel)
                       = q.codigo_qualificacao
            )
            TO '{GOLD / "empresas_consolidada.parquet"}'
            (FORMAT PARQUET, COMPRESSION SNAPPY)
        """)

        # 5. Identificação de capitais sociais potencialmente atípicos
        logging.info("Gerando identificação de capitais sociais atípicos")

        con.execute(f"""
            COPY (
                WITH quartis AS (
                    SELECT
                        porte_descricao,
                        quantile_cont(capital_social, 0.25) AS p25,
                        quantile_cont(capital_social, 0.75) AS p75
                    FROM empresas
                    WHERE capital_social_valido = TRUE
                      AND capital_social > 0
                      AND porte_descricao <> 'Não informado'
                    GROUP BY porte_descricao
                ),
                limites AS (
                    SELECT
                        porte_descricao,
                        p25,
                        p75,
                        p75 - p25 AS intervalo_interquartil,
                        p75 + 1.5 * (p75 - p25) AS limite_superior
                    FROM quartis
                )
                SELECT
                    e.cnpj_basico,
                    e.razao_social,
                    e.porte_descricao,
                    e.natureza_juridica,
                    e.capital_social,
                    CASE
                        WHEN e.capital_social >= 999950000000 THEN
                            'R$ ' || REGEXP_REPLACE(
                                REPLACE(PRINTF('%.1f', e.capital_social / 1000000000000), '.', ','),
                                ',0$', ''
                            ) || CASE
                                WHEN ROUND(e.capital_social / 1000000000000, 1) < 2
                                    THEN ' trilhão'
                                ELSE ' trilhões'
                            END

                        WHEN e.capital_social >= 999950000 THEN
                            'R$ ' || REGEXP_REPLACE(
                                REPLACE(PRINTF('%.1f', e.capital_social / 1000000000), '.', ','),
                                ',0$', ''
                            ) || CASE
                                WHEN ROUND(e.capital_social / 1000000000, 1) < 2
                                    THEN ' bilhão'
                                ELSE ' bilhões'
                            END

                        WHEN e.capital_social >= 999500 THEN
                            'R$ ' || REGEXP_REPLACE(
                                REPLACE(PRINTF('%.1f', e.capital_social / 1000000), '.', ','),
                                ',0$', ''
                            ) || CASE
                                WHEN ROUND(e.capital_social / 1000000, 1) < 2
                                    THEN ' milhão'
                                ELSE ' milhões'
                            END

                        WHEN e.capital_social >= 1000 THEN
                            'R$ ' || REGEXP_REPLACE(
                                REPLACE(PRINTF('%.1f', e.capital_social / 1000), '.', ','),
                                ',0$', ''
                            ) || ' mil'

                        ELSE
                            'R$ ' || REPLACE(
                                PRINTF('%.2f', e.capital_social),
                                '.', ','
                            )
                    END AS capital_social_formatado,
                    l.p25,
                    l.p75,
                    l.intervalo_interquartil,
                    l.limite_superior,
                    'Potencialmente atípico' AS classificacao
                FROM empresas e
                INNER JOIN limites l
                    ON e.porte_descricao = l.porte_descricao
                WHERE e.capital_social_valido = TRUE
                  AND e.capital_social > 0
                  AND e.porte_descricao <> 'Não informado'
                  AND e.capital_social > l.limite_superior
            )
            TO '{GOLD / "capital_social_atipicos.parquet"}'
            (FORMAT PARQUET, COMPRESSION SNAPPY)
        """)

        # Registra as saídas Gold como views no DuckDB
        arquivos_gold = {
            "empresas_por_natureza": "empresas_por_natureza.parquet",
            "capital_por_porte": "capital_por_porte.parquet",
            "empresas_por_qualificacao": "empresas_por_qualificacao.parquet",
            "empresas_consolidada": "empresas_consolidada.parquet",
            "capital_social_atipicos": "capital_social_atipicos.parquet",
        }

        for nome_view, nome_arquivo in arquivos_gold.items():
            arquivo = GOLD / nome_arquivo

            con.execute(f"""
                CREATE OR REPLACE VIEW {nome_view} AS
                SELECT *
                FROM read_parquet('{arquivo}')
            """)

        logging.info("Views Gold registradas no DuckDB")

        logging.info("Camada Gold criada com sucesso")

    finally:
        con.close()

# ==========================================
# AUDITORIA E EXECUÇÃO
# ==========================================



def executar_etapa(nome, funcao, *args):
    inicio = time.perf_counter()
    parar = threading.Event()

    def atualizar_tempo():
        while not parar.wait(1):
            decorrido = int(time.perf_counter() - inicio)
            print(
                f"\r⏳ {nome} em andamento... {decorrido}s",
                end="",
                flush=True
            )

    print(f"\n⏳ {nome} iniciado...", flush=True)

    thread = threading.Thread(
        target=atualizar_tempo,
        daemon=True
    )
    thread.start()

    try:
        resultado = funcao(*args)

    except BaseException:
        parar.set()
        thread.join()

        duracao = time.perf_counter() - inicio

        print(
            f"\r✗ {nome} falhou após {duracao:.1f}s"
            + " " * 15,
            flush=True
        )
        raise

    else:
        parar.set()
        thread.join()

        duracao = time.perf_counter() - inicio

        print(
            f"\r✓ {nome} concluído em {duracao:.1f}s"
            + " " * 15,
            flush=True
        )

        return resultado


def main():

    inicio = datetime.now(FUSO_HORARIO)

    logging.info("===== PIPELINE CNPJ INICIADO =====")

    executar_etapa("EXTRAÇÃO — EMPRESAS", extract)

    executar_etapa("EXTRAÇÃO — NATUREZAS", extract_naturezas)
    executar_etapa("EXTRAÇÃO — QUALIFICAÇÕES", extract_qualificacoes)

    total = executar_etapa("TRANSFORMAÇÃO — SILVER", transform)

    indicadores = executar_etapa("QUALIDADE DOS DADOS", quality, total)

    executar_etapa("CARGA — NATUREZAS", load_naturezas)
    executar_etapa("CARGA — QUALIFICAÇÕES", load_qualificacoes)

    executar_etapa("GERAÇÃO — GOLD", create_gold)

    # Exibe um exemplo do modelo final da tabela Gold
    caminho_gold = GOLD / "empresas_consolidada.parquet"

    con = duckdb.connect()
    try:
        registro = con.execute(f"""
            SELECT
                cnpj_basico,
                razao_social,
                natureza_juridica,
                descricao_natureza,
                qualificacao_responsavel,
                descricao_qualificacao,
                capital_social
            FROM read_parquet('{caminho_gold}')
            ORDER BY cnpj_basico
            LIMIT 1
        """).fetchone()
    finally:
        con.close()

    if registro:
        (
            cnpj,
            razao_social,
            natureza,
            descricao_natureza,
            qualificacao,
            descricao_qualificacao,
            capital_social
        ) = registro

        if capital_social is not None:
            capital_formatado = (
                f"R$ {capital_social:,.2f}"
                .replace(",", "X")
                .replace(".", ",")
                .replace("X", ".")
            )
        else:
            capital_formatado = "Não informado"

        print("\n" + "=" * 68)
        print("CAMADA GOLD — MODELO DA TABELA EMPRESAS CONSOLIDADAS")
        print("=" * 68)
        print("Exemplo de um registro após os joins e tratamentos:\n")
        print(f"CNPJ básico:                 {cnpj}")
        print(f"Razão social:                {razao_social}")
        print(f"Natureza jurídica:           {natureza}")
        print(f"Descrição da natureza:       {descricao_natureza}")
        print(f"Qualificação do responsável: {qualificacao}")
        print(f"Descrição da qualificação:   {descricao_qualificacao}")
        print(f"Capital social:              {capital_formatado}")
        print("=" * 68 + "\n")

    # Indicadores de correspondência das qualificações
    con = duckdb.connect(str(DB_FILE), read_only=True)

    try:
        qualificacoes_auditoria = con.execute("""
            SELECT
                COUNT(DISTINCT TRIM(e.qualificacao_responsavel)),
                COUNT(DISTINCT CASE
                    WHEN q.codigo_qualificacao IS NOT NULL
                    THEN TRIM(e.qualificacao_responsavel)
                END),
                COUNT(DISTINCT CASE
                    WHEN q.codigo_qualificacao IS NULL
                    THEN TRIM(e.qualificacao_responsavel)
                END),
                COUNT(*) FILTER (
                    WHERE q.codigo_qualificacao IS NULL
                )
            FROM empresas e
            LEFT JOIN qualificacoes_responsavel q
                ON TRIM(e.qualificacao_responsavel)
                   = q.codigo_qualificacao
        """).fetchone()
    finally:
        con.close()

    indicadores_qualificacoes = {
        "codigos_utilizados": qualificacoes_auditoria[0],
        "codigos_encontrados": qualificacoes_auditoria[1],
        "codigos_sem_correspondencia": qualificacoes_auditoria[2],
        "empresas_sem_descricao": qualificacoes_auditoria[3]
    }

    auditoria = {
        "competencia": COMPETENCIA,
        "arquivos": [
            f"{nome}.zip" for nome in ARQUIVOS
        ] + ["Naturezas.zip", "Qualificacoes.zip"],
        "data_execucao_utc": inicio.isoformat(),
        "total_registros": total,
        "qualidade": indicadores,
        "qualidade_qualificacoes": indicadores_qualificacoes,
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
