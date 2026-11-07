# Case Engenharia de Dados – CNPJ

## 1. Objetivo

Desenvolver um pipeline de Engenharia de Dados para ingestão, transformação, validação e disponibilização analítica dos Dados Abertos do CNPJ da Receita Federal.

A solução utiliza Python, Pandas, DuckDB, PyArrow, Parquet e Docker, organizada em camadas Bronze, Silver e Gold.

## 2. Fonte de dados e escopo

- Fonte: Dados Abertos do CNPJ – Receita Federal.
- Competência processada: Outubro de 2026 (`2026-10`).
- Arquivo principal: `Empresas0.zip`.
- Tabelas auxiliares: `Naturezas.zip` e `Qualificacoes.zip`.
- Formato original: CSV delimitado por ponto e vírgula, codificação Latin-1.

A base de empresas possui dez partições (`Empresas0` a `Empresas9`). Neste projeto foi processada somente a partição `Empresas0`, conforme o escopo do case.

Os resultados não representam a totalidade das empresas brasileiras.

## 3. Fonte e URLs dos arquivos

O endereço-base é configurado pela variável `SOURCE_BASE_URL`.

O pipeline monta automaticamente os caminhos utilizando a competência e o nome de cada arquivo:

`{SOURCE_BASE_URL}/{COMPETENCIA}/{NOME_DO_ARQUIVO}.zip`

Para outubro de 2026, os caminhos são:

- `{SOURCE_BASE_URL}/2026-10/Empresas0.zip`
- `{SOURCE_BASE_URL}/2026-10/Naturezas.zip`
- `{SOURCE_BASE_URL}/2026-10/Qualificacoes.zip`

A URL-base deve ser configurada no arquivo `.env`. Não inclua credenciais ou parâmetros privados no README ou no repositório.


## 4. Arquitetura da solução

O pipeline é organizado em três camadas (Bronze, Silver e Gold), seguindo um fluxo de ingestão, transformação e disponibilização analítica:

- Bronze: armazenamento dos arquivos ZIP originais da Receita Federal.
- Silver: dados tratados, padronizados e armazenados em Parquet.
- Gold: tabelas analíticas e dados consolidados, prontos para consulta.

O DuckDB é utilizado para validações, transformações e geração das tabelas analíticas.

## 5. Dados disponibilizados

- `empresas_por_natureza.parquet`: quantidade de empresas e indicadores de capital por natureza jurídica.
- `capital_por_porte.parquet`: distribuição de empresas e capital por porte.
- `empresas_por_qualificacao.parquet`: indicadores por qualificação do responsável.
- `empresas_consolidada.parquet`: dados das empresas enriquecidos com descrições das tabelas auxiliares.

## 6. Como executar

### Pré-requisitos

- GitHub Codespaces ou ambiente com Docker e Docker Compose.
- Arquivo `.env` configurado na raiz do projeto.

### Configuração do ambiente

Configure as variáveis no arquivo `.env`:

- `SOURCE_BASE_URL`: endereço-base dos arquivos oficiais.
- `COMPETENCIA`: competência dos dados, por exemplo `2026-10`.
- `ARQUIVOS`: partição de empresas a processar, neste case `Empresas0`.

### Execução

Para construir a imagem:

`docker compose build`

Para executar o pipeline:

`docker compose run --rm pipeline`

Para executar os testes automatizados:

`docker compose run --rm pipeline pytest -v tests/`

Os dados são persistidos no diretório `data/`, montado como volume do contêiner.

## 7. Decisões técnicas e trade-offs

- **Python:** orquestração do processo de ingestão e transformação.
- **Pandas:** leitura e tratamento dos dados de origem.
- **DuckDB:** processamento analítico local, validações e consultas SQL.
- **Parquet:** armazenamento colunar e eficiente para leitura analítica.
- **Docker:** padronização do ambiente e reprodutibilidade da execução.
- **Processamento em partição:** escolha da `Empresas0` para atender ao escopo do case e limitar o consumo de recursos.
- **Processamento em blocos:** leitura dos arquivos CSV em blocos de 250 mil registros, reduzindo o consumo de memória durante a transformação da camada Silver.
- **Controle de memória:** limitação de memória e paralelismo do DuckDB, além de diretório temporário para operações que excedam a memória disponível.
- **Joins com tabelas auxiliares:** utilização de LEFT JOIN para preservar registros mesmo quando não existe correspondência na tabela de referência.

## 8. Qualidade dos dados

Na execução da competência `2026-10`, foram processados 30.063.698 registros da partição `Empresas0`.

Resultados das verificações:

- 30.063.698 registros processados.
- 30.063.698 CNPJs básicos únicos.
- Nenhum CNPJ básico inválido identificado.
- Nenhum capital social inválido ou negativo identificado.
- Nenhuma natureza jurídica ausente.
- 4.109 registros sem informação de porte.
- 337 empresas sem descrição de qualificação correspondente na tabela auxiliar.

Os registros sem correspondência nas tabelas auxiliares são preservados, com indicação de ausência de descrição, em vez de serem descartados.

Os resultados são registrados no arquivo `auditoria.json`.

## 9. Limitações conhecidas

- O processamento contempla somente a partição `Empresas0`, e não a base completa de empresas.
- Os resultados representam um subconjunto da base nacional, correspondente à partição `Empresas0`, e não o universo completo de CNPJs.
- A qualidade e a disponibilidade dos dados dependem da fonte oficial da Receita Federal.
- Um código de qualificação sem correspondência na tabela auxiliar permanece sem descrição, sem perda do registro original.

## 10. Evoluções futuras

- Processar as dez partições de empresas.
- Implementar processamento incremental por competência.
- Ampliar os testes automatizados e as regras de qualidade.
- Implementar monitoramento de execução e alertas.
- Avaliar particionamento dos arquivos Parquet para melhorar consultas em volumes maiores.

