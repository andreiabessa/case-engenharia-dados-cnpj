import pandas as pd
import pytest
import zipfile

from src import pipeline


def preparar_silver(tmp_path, incluir_porte_descricao=True):
    arquivo = tmp_path / "empresas.parquet"

    dados = {
        "cnpj_basico": ["12345678", "12345678", "87654321"],
        "cnpj_basico_valido": [True, True, False],
        "capital_social": [100.0, None, -5.0],
        "natureza_juridica": ["2135", "", None],
        "porte_empresa": ["01", "03", ""],
    }

    if incluir_porte_descricao:
        dados["porte_descricao"] = [
            "Microempresa",
            "Empresa de Pequeno Porte",
            "Não informado",
        ]

    pd.DataFrame(dados).to_parquet(arquivo, index=False)

    pipeline.PARQUET_FILE = arquivo
    pipeline.DB_FILE = tmp_path / "teste.duckdb"


def test_quality_retorna_indicadores_corretos(tmp_path, monkeypatch):
    preparar_silver(tmp_path)

    resultado = pipeline.quality(3)

    assert resultado == {
        "total": 3,
        "cnpjs_unicos": 2,
        "cnpjs_invalidos": 1,
        "capitais_invalidos": 1,
        "capitais_negativos": 1,
        "naturezas_ausentes": 2,
        "portes_ausentes": 1,
    }


def test_quality_identifica_divergencia_de_registros(tmp_path):
    preparar_silver(tmp_path)

    with pytest.raises(ValueError, match="Divergência de registros"):
        pipeline.quality(10)


def test_quality_identifica_coluna_ausente(tmp_path):
    preparar_silver(tmp_path, incluir_porte_descricao=False)

    with pytest.raises(ValueError, match="porte_descricao"):
        pipeline.quality(3)

def test_transform_aceita_cnpj_alfanumerico(tmp_path, monkeypatch):
    bronze = tmp_path / "bronze"
    silver = tmp_path / "silver"

    bronze.mkdir()
    silver.mkdir()

    conteudo = (
        "12345678;Empresa Numerica;2135;05;100,00;01;\n"
        "12abc345;Empresa Alfanumerica;2135;05;200,00;03;\n"
        "12@BC345;Empresa Invalida;2135;05;300,00;01;\n"
    )

    with zipfile.ZipFile(
        bronze / "Empresas0.zip", "w"
    ) as arquivo_zip:
        arquivo_zip.writestr("Empresas0.csv", conteudo)

    monkeypatch.setattr(pipeline, "BRONZE", bronze)
    monkeypatch.setattr(pipeline, "SILVER", silver)
    monkeypatch.setattr(
        pipeline,
        "PARQUET_FILE",
        silver / "empresas.parquet"
    )
    monkeypatch.setattr(
        pipeline,
        "ARQUIVOS",
        ["Empresas0"]
    )

    total = pipeline.transform()

    resultado = pd.read_parquet(
        silver / "empresas.parquet"
    )

    assert total == 3
    assert resultado["cnpj_basico"].tolist() == [
        "12345678",
        "12ABC345",
        "12@BC345",
    ]
    assert resultado["cnpj_basico_valido"].tolist() == [
        True,
        True,
        False,
    ]