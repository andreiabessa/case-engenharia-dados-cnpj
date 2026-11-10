# Case Engenharia de Dados – CNPJ

Este projeto foi desenvolvido com o apoio de ferramentas de Inteligência Artificial (IA), utilizadas como suporte à elaboração, revisão e aprimoramento da documentação e do código, conforme permitido pelo enunciado do case. As decisões técnicas, validações e resultados foram revisados durante o desenvolvimento.

## 1. Objetivo

Desenvolver um pipeline de Engenharia de Dados para ingestão, transformação, validação e disponibilização analítica dos Dados Abertos do CNPJ da Receita Federal.

A solução utiliza Python, Pandas, DuckDB, PyArrow, Parquet e Docker, organizada em camadas Bronze, Silver e Gold.

## 2. Fonte de dados e escopo

- Fonte: Dados Abertos do CNPJ – Receita Federal.
- Competência processada: Outubro de 2026 (`2026-10`).
- Arquivo principal: `Empresas0.zip`.
- Tabelas auxiliares: `Naturezas.zip` e `Qualificacoes.zip`.
- Formato original: CSV delimitado por ponto e vírgula, codificação Latin-1.

A base de empresas possui dez partições (`Empresas0` a `Empresas9`). Neste projeto foi processada somente a partição `Empresas0`, conforme o escopo do case, sendo assim,  os resultados não representam a totalidade das empresas brasileiras.

## 3. Fonte e URLs dos arquivos

O endereço-base é configurado pela variável `SOURCE_BASE_URL`, definida no arquivo `.env`, localizado na raiz do projeto.

O pipeline monta automaticamente os caminhos utilizando a competência e o nome de cada arquivo no seguinte formato:

`{SOURCE_BASE_URL}/{COMPETENCIA}/{NOME_DO_ARQUIVO}.zip`

Para outubro de 2026, os caminhos são:

- `https://arquivos.receitafederal.gov.br/public.php/dav/files/YggdBLfdninEJX9/2026-10/Empresas0.zip`
- `https://arquivos.receitafederal.gov.br/public.php/dav/files/YggdBLfdninEJX9/2026-10/Naturezas.zip`
- `https://arquivos.receitafederal.gov.br/public.php/dav/files/YggdBLfdninEJX9/2026-10/Qualificacoes.zip`

A URL-base pode ser configurada no arquivo `.env`, conforme explicado no item 6.

## 4. Arquitetura da solução

O pipeline é organizado em três camadas (Bronze, Silver e Gold), seguindo um fluxo de ingestão, transformação e disponibilização analítica:

- Bronze: armazenamento dos arquivos ZIP originais da Receita Federal.
- Silver: dados tratados, padronizados e armazenados em Parquet.
- Gold: arquivos analíticos e dados consolidados em formato Parquet, preparados para consultas e consumo por outras ferramentas.

O DuckDB é utilizado para validações, transformações e geração das tabelas analíticas.

## 5. Dados disponibilizados e armazenamento

O projeto utiliza o **DuckDB** como mecanismo de banco de dados analítico, armazenando os dados processados no arquivo `cnpj.duckdb`, localizado no diretório da competência (`data/2026-10/cnpj.duckdb`).

Dentro desse banco é criada a tabela:

- `empresas`: tabela principal, contendo os dados cadastrais tratados e validados da Receita Federal.

A partir dos dados tratados e das tabelas auxiliares de naturezas jurídicas e qualificações, o pipeline gera quatro conjuntos de dados analíticos na camada Gold, armazenados em arquivos independentes no formato Parquet:

- `empresas_por_natureza.parquet`: indicadores de empresas agrupados por natureza jurídica.
- `capital_por_porte.parquet`: distribuição de empresas e capital social por porte.
- `empresas_por_qualificacao.parquet`: indicadores agrupados por qualificação do responsável.
- `empresas_consolidada.parquet`: visão consolidada dos dados cadastrais, enriquecida com as descrições das tabelas auxiliares.

O DuckDB é utilizado para processamento analítico e consultas SQL, enquanto os arquivos Parquet disponibilizam os resultados consolidados para consumo por outras ferramentas.

## 6. Como executar

### Pré-requisitos

- GitHub Codespaces ou ambiente com Docker e Docker Compose.
- Arquivo `.env` disponível na raiz do projeto.

### Configuração do ambiente

No repositório, acesse Code → Codespaces → Create codespace on main.

O arquivo `.env` já está incluído no repositório e contém as configurações necessárias para executar o pipeline.

Caso queira alterar alguma configuração, edite diretamente o arquivo `.env`:

- `SOURCE_BASE_URL`: endereço-base dos arquivos oficiais da Receita Federal.
- `COMPETENCIA`: use `auto` para buscar automaticamente a competência anterior (M-1) ou informe uma competência específica no formato `AAAA-MM`.
- `ARQUIVOS`: use `Empresas0` para processar a partição deste case, `todos` para processar as dez partições ou informe partições específicas separadas por vírgula.

O Docker Compose disponibiliza as variáveis no contêiner por meio de `env_file`.

**Observação:** o arquivo `.env` está versionado neste projeto e contém apenas configurações de execução, sem credenciais ou senhas.

### Execução

Abra um novo terminal:
1. Construa a imagem Docker do projeto. Esse processo prepara o ambiente de execução, instala as dependências e incorpora o código-fonte e os testes à imagem:

`docker compose build`

2. Execute o pipeline para que o código faça a leitura e extração dos arquivos e gere as camadas de arquitetura:

`docker compose run --rm pipeline`

Atenção: Esta etapa pode demorar um pouco devido ao tamanho do arquivo que está sendo processado.

3. Execute os testes automatizados:

`docker compose run --rm pipeline pytest -v tests/`

Os dados são salvos no diretório `data/`, montado como volume do contêiner.

Observação: A reconstrução da imagem é necessária quando houver alterações no Dockerfile, nas dependências ou nos arquivos incorporados à imagem, como src/ e tests/. Alterações apenas no .env não exigem uma nova construção.

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

Os indicadores apresentados abaixo correspondem à execução da competência `2026-10`, utilizando exclusivamente a partição `Empresas0`.

Resultados das verificações:

- 30.063.698 registros processados.
- 30.063.698 CNPJs básicos únicos.
- Nenhum CNPJ básico inválido identificado.
- Nenhum capital social inválido ou negativo identificado.
- Nenhuma natureza jurídica ausente.
- 4.109 registros sem informação de porte.
- 337 empresas sem descrição de qualificação correspondente na tabela auxiliar.

Os registros sem correspondência nas tabelas auxiliares são preservados, com indicação de ausência de descrição, em vez de serem descartados.

Os resultados das verificações são registrados no arquivo auditoria.json, que documenta a competência processada, os arquivos utilizados, a quantidade de registros, os indicadores de qualidade e o status da execução.

## 9. Limitações conhecidas

- O processamento e os resultados contemplam somente a partição `Empresas0`, e não a base completa de empresas.
- A qualidade e a disponibilidade dos dados dependem da fonte oficial da Receita Federal.
- Um código de qualificação sem correspondência na tabela auxiliar permanece sem descrição, sem perda do registro original.

## 10. Evoluções futuras

- Processar as dez partições de empresas.
- Implementar processamento incremental por competência.
- Ampliar os testes automatizados e as regras de qualidade.
- Implementar monitoramento de execução e alertas.
- Avaliar particionamento dos arquivos Parquet para melhorar consultas em volumes maiores.

