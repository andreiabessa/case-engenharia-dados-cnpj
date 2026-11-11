import duckdb

from src import pipeline


def preparar_banco_teste(tmp_path, monkeypatch):
    banco = tmp_path / "teste.duckdb"
    pasta_gold = tmp_path / "gold"

    pasta_gold.mkdir()

    monkeypatch.setattr(pipeline, "BASE", tmp_path)
    monkeypatch.setattr(pipeline, "GOLD", pasta_gold)
    monkeypatch.setattr(pipeline, "DB_FILE", banco)

    con = duckdb.connect(str(banco))

    con.execute("""
        CREATE TABLE empresas (
            cnpj_basico VARCHAR,
            razao_social VARCHAR,
            natureza_juridica VARCHAR,
            qualificacao_responsavel VARCHAR,
            capital_social DOUBLE,
            porte_empresa VARCHAR,
            porte_descricao VARCHAR,
            ente_federativo_responsavel VARCHAR,
            cnpj_basico_valido BOOLEAN,
            capital_social_valido BOOLEAN,
            competencia VARCHAR
        )
    """)

    con.execute("""
        INSERT INTO empresas VALUES
            ('11111111', 'Empresa A', '2135', '05', 100.0, '01',
             'Microempresa', '', TRUE, TRUE, '2026-10'),
            ('22222222', 'Empresa B', '2135', '05', 200.0, '01',
             'Microempresa', '', TRUE, TRUE, '2026-10'),
            ('33333333', 'Empresa C', '2062', '10', 500.0, '03',
             'Demais', '', TRUE, TRUE, '2026-10'),
            ('44444444', 'Empresa D', '9999', '36', 200.0, '03',
             'Demais', '', TRUE, TRUE, '2026-10')
    """)

    con.execute("""
        CREATE TABLE naturezas_juridicas AS
        SELECT *
        FROM (
            VALUES
                ('2135', 'Sociedade Empresária'),
                ('2062', 'Sociedade Limitada')
        ) AS t(natureza_juridica, descricao_natureza)
    """)

    con.execute("""
        CREATE TABLE qualificacoes_responsavel AS
        SELECT *
        FROM (
            VALUES
                ('05', 'Administrador'),
                ('10', 'Diretor')
        ) AS t(codigo_qualificacao, descricao_qualificacao)
    """)

    con.close()


def test_create_gold_gera_cinco_arquivos(tmp_path, monkeypatch):
    preparar_banco_teste(tmp_path, monkeypatch)

    pipeline.create_gold()

    pasta_gold = tmp_path / "gold"

    arquivos = [
        "empresas_por_natureza.parquet",
        "capital_por_porte.parquet",
        "empresas_por_qualificacao.parquet",
        "empresas_consolidada.parquet",
        "capital_social_atipicos.parquet",
    ]

    for arquivo in arquivos:
        assert (pasta_gold / arquivo).exists()


def test_gold_calcula_indicadores_corretamente(tmp_path, monkeypatch):
    preparar_banco_teste(tmp_path, monkeypatch)

    pipeline.create_gold()

    con = duckdb.connect()

    try:
        natureza = con.execute("""
            SELECT
                quantidade_empresas,
                capital_total,
                capital_medio
            FROM read_parquet(?)
            WHERE natureza_juridica = '2135'
        """, [str(tmp_path / "gold/empresas_por_natureza.parquet")]).fetchone()

        assert natureza == (2, 300.0, 150.0)

        porte = con.execute("""
            SELECT
                quantidade_empresas,
                capital_total,
                capital_medio
            FROM read_parquet(?)
            WHERE porte_empresa = '03'
        """, [str(tmp_path / "gold/capital_por_porte.parquet")]).fetchone()

        assert porte == (2, 700.0, 350.0)

    finally:
        con.close()


def test_gold_preserva_codigos_sem_correspondencia(tmp_path, monkeypatch):
    preparar_banco_teste(tmp_path, monkeypatch)

    pipeline.create_gold()

    con = duckdb.connect()

    try:
        natureza = con.execute("""
            SELECT descricao_natureza
            FROM read_parquet(?)
            WHERE natureza_juridica = '9999'
        """, [str(tmp_path / "gold/empresas_por_natureza.parquet")]).fetchone()

        assert natureza == ("Não encontrada",)

        qualificacao = con.execute("""
            SELECT descricao_qualificacao, quantidade_empresas
            FROM read_parquet(?)
            WHERE codigo_qualificacao = '36'
        """, [str(tmp_path / "gold/empresas_por_qualificacao.parquet")]).fetchone()

        assert qualificacao == (
            "Código não encontrado na tabela oficial",
            1
        )

    finally:
        con.close()


def test_gold_gera_tabela_consolidada_completa(tmp_path, monkeypatch):
    preparar_banco_teste(tmp_path, monkeypatch)

    pipeline.create_gold()

    con = duckdb.connect()

    try:
        arquivo = str(tmp_path / "gold/empresas_consolidada.parquet")

        total = con.execute(
            "SELECT COUNT(*) FROM read_parquet(?)",
            [arquivo]
        ).fetchone()[0]

        assert total == 4

        dados = con.execute("""
            SELECT
                cnpj_basico,
                descricao_natureza,
                descricao_qualificacao
            FROM read_parquet(?)
            WHERE cnpj_basico = '44444444'
        """, [arquivo]).fetchone()

        assert dados == (
            "44444444",
            "Não encontrada",
            "Código não encontrado na tabela oficial"
        )

    finally:
        con.close()


def test_gold_registra_cinco_views_no_duckdb(tmp_path, monkeypatch):
    preparar_banco_teste(tmp_path, monkeypatch)

    pipeline.create_gold()

    con = duckdb.connect(str(tmp_path / "teste.duckdb"))

    try:
        tabelas = {
            linha[0]
            for linha in con.execute("SHOW TABLES").fetchall()
        }

        views_gold = {
            "empresas_por_natureza",
            "capital_por_porte",
            "empresas_por_qualificacao",
            "empresas_consolidada",
            "capital_social_atipicos",
        }

        assert views_gold.issubset(tabelas)

        total = con.execute(
            "SELECT COUNT(*) FROM empresas_consolidada"
        ).fetchone()[0]

        assert total == 4

    finally:
        con.close()
