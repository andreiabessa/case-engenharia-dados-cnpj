# Case Engenharia de Dados – CNPJ

## 1. Objetivo

Desenvolver um pipeline de Engenharia de Dados para ingestão, transformação, validação e análise dos dados públicos de empresas da Receita Federal.

A solução utiliza Python, DuckDB, Parquet e Docker, seguindo uma arquitetura organizada em camadas Bronze, Silver e Gold.

## 2. Fonte de dados e escopo

- **Fonte:** Dados Abertos do CNPJ – Receita Federal.
- **Competência:** Outubro de 2026 (`2026-10`).
- **Arquivo principal processado:** `Empresas0.zip`.
- **Tabela auxiliar:** `Naturezas.zip`, com os códigos e as descrições oficiais das naturezas jurídicas.
- **Formato original:** CSV delimitado por ponto e vírgula, codificação Latin-1.

A base de empresas é dividida em dez partições (`Empresas0` a `Empresas9`). Neste processamento foi utilizada somente a partição `Empresas0`. Portanto, os resultados não representam a totalidade das empresas brasileiras.

## 3. Arquitetura

```text
                    RECEITA FEDERAL
                          |
          +---------------+---------------+
          |               |               |
          v               v               v
    Empresas0.zip   Naturezas.zip   Qualificacoes.zip
          |               |               |
          v               v               v
       BRONZE          BRONZE          BRONZE
          |               |               |
          v               |               |
       SILVER             |               |
          |               |               |
          v               v               v
                    DUCKDB
          +---------------+---------------+
          |               |               |
          v               v               v
      empresas    naturezas_juridicas  qualificacoes_responsavel
          |               |               |
          +---------------+---------------+
                          |
                    LEFT JOIN
                          |
                          v
                         GOLD
                   Arquivos Parquet
```

**Bronze – Dados brutos**
- Download e armazenamento dos arquivos ZIP das empresas, das naturezas jurídicas e das qualificações dos responsáveis.
- Validação da integridade dos arquivos.
- Reutilização de arquivos válidos já existentes.

**Silver – Dados tratados**
- Leitura em lotes (*chunks*) de 250 mil registros.
- Padronização dos campos e conversão do capital social para decimal.
- Validação do CNPJ básico e identificação de dados inválidos ou ausentes.
- Armazenamento em Parquet com schema definido.

### Estrutura da tabela `empresas`

A tabela `empresas`, armazenada no DuckDB, contém os dados tratados na camada Silver, com a seguinte estrutura:

| Coluna | Descrição |
|---|---|
| `cnpj_basico` | Oito primeiros dígitos do CNPJ |
| `razao_social` | Nome empresarial da empresa |
| `natureza_juridica` | Código da natureza jurídica |
| `qualificacao_responsavel` | Código da qualificação do responsável |
| `capital_social` | Valor do capital social |
| `porte_empresa` | Código do porte da empresa |
| `ente_federativo_responsavel` | Ente federativo responsável, quando aplicável |

A tabela é utilizada como base para as consultas analíticas e para a geração dos arquivos da camada Gold.

**DuckDB – Armazenamento e relacionamento**
- Criação da tabela `empresas` a partir dos dados Silver.
- Criação da tabela `naturezas_juridicas` a partir do arquivo oficial `Naturezas.zip`.
- Criação da tabela `qualificacoes_responsavel` a partir do arquivo oficial `Qualificacoes.zip`.
- Relacionamento de `empresas` com `naturezas_juridicas` pelo código da natureza jurídica.
- Relacionamento de `empresas` com `qualificacoes_responsavel` pelo código da qualificação do responsável.

**Gold – Dados analíticos**

São gerados três arquivos Parquet:

| Caminho | Conteúdo |
|---|---|
| `data/2026-10/gold/empresas_por_natureza.parquet` | Código e descrição oficial da natureza jurídica, quantidade de empresas, capital total e capital médio. |
| `data/2026-10/gold/empresas_por_qualificacao.parquet` | Código e descrição da qualificação do responsável, quantidade de empresas, capital total e capital médio. |
| `data/2026-10/gold/capital_por_porte.parquet` | Quantidade de empresas, capital total e capital médio por porte. |

A consulta de natureza jurídica e a consulta de qualificação utilizam `LEFT JOIN`, preservando os registros de empresas mesmo quando não existe correspondência nas tabelas auxiliares.

Para naturezas jurídicas sem correspondência, é utilizada a identificação `Não encontrada`. Para qualificações sem correspondência oficial, é utilizada a identificação `Código não encontrado na tabela oficial`.


### Organização dos arquivos gerados

Os dados são organizados em diretórios separados por competência, evitando a mistura de resultados de períodos diferentes.

```text
data/
└── 2026-10/
    ├── bronze/
    │   ├── Empresas0.zip
    │   ├── Naturezas.zip
    │   └── Qualificacoes.zip
    ├── silver/
    │   └── empresas.parquet
    ├── gold/
    │   ├── empresas_por_natureza.parquet
    │   ├── empresas_por_qualificacao.parquet
    │   └── capital_por_porte.parquet
    ├── cnpj.duckdb
    └── auditoria.json
```

**Tabelas disponíveis no DuckDB (`data/2026-10/cnpj.duckdb`):**

| Tabela | Origem |
|---|---|
| `empresas` | Dados tratados da camada Silver |
| `naturezas_juridicas` | `data/2026-10/bronze/Naturezas.zip` |
| `qualificacoes_responsavel` | `data/2026-10/bronze/Qualificacoes.zip` |

A competência é definida pela variável `COMPETENCIA`. Quando configurada como `auto`, o pipeline utiliza automaticamente o mês anterior.


## 4. Tecnologias

- Python 3.12
- Pandas
- DuckDB
- PyArrow
- Requests
- Python-dateutil
- Docker e Docker Compose
- GitHub Codespaces

## 5. Configuração e execução

Configure o arquivo `.env`:

```env
SOURCE_BASE_URL=<URL_BASE_DOS_ARQUIVOS>
COMPETENCIA=auto
ARQUIVOS=Empresas0
```

**Parâmetros:**
- `COMPETENCIA=auto`: utiliza automaticamente o mês anterior ao da execução. Também aceita uma competência manual no formato `AAAA-MM`.
- `ARQUIVOS=Empresas0`: seleciona uma partição.
- `ARQUIVOS=Empresas0,Empresas1`: permite selecionar múltiplas partições.
- `ARQUIVOS=todos`: seleciona as dez partições.

A URL-base deve apontar para a origem dos arquivos da Receita Federal. O `.env` não deve ser versionado, pois contém informações de acesso.

**Construir a imagem:**

```bash
docker compose build pipeline
```

**Executar o pipeline completo:**

```bash
docker compose run --rm pipeline
```

O processamento executa:
1. Download dos arquivos de empresas.
2. Download da tabela oficial de naturezas jurídicas.
3. Transformação dos dados em lotes.
4. Validação da qualidade.
5. Carga das tabelas no DuckDB.
6. Relacionamento das empresas com as descrições oficiais.
7. Geração dos arquivos Gold.
8. Geração da auditoria.

Após alterações no código-fonte, reconstrua a imagem Docker.

## 6. Qualidade dos dados

Foram implementadas verificações de volume, unicidade e validade do CNPJ básico, validade do capital social, capitais negativos e campos ausentes.

**Resultados da execução:**

| Indicador | Resultado |
|---|---:|
| Total de registros | 30.063.698 |
| CNPJs únicos | 30.063.698 |
| CNPJs inválidos | 0 |
| Capitais inválidos | 0 |
| Capitais negativos | 0 |
| Naturezas ausentes no cadastro de empresas | 0 |
| Portes ausentes | 4.109 |

Os 4.109 registros sem porte informado foram preservados e classificados como `Não informado`. Todos apresentam capital social igual a zero.

### Validação da tabela de naturezas jurídicas

A tabela auxiliar oficial foi carregada automaticamente a partir de `Naturezas.zip`.

| Indicador | Resultado |
|---|---:|
| Registros na tabela oficial | 92 |
| Naturezas presentes no Gold | 84 |
| Naturezas com descrição | 84 |
| Naturezas sem correspondência | 0 |
| Cobertura das descrições no Gold | 100% |

A cobertura de 100% refere-se às 84 naturezas jurídicas presentes na amostra processada, e não aos 92 códigos existentes na tabela auxiliar.

### Classificação por porte

| Código | Descrição |
|---|---|
| 01 | Microempresa |
| 03 | Empresa de Pequeno Porte |
| 05 | Demais |
| Vazio | Não informado |

## 7. Resultados da camada Gold

São gerados dois arquivos Parquet:

| Arquivo | Registros |
|---|---:|
| `empresas_por_natureza.parquet` | 84 |
| `capital_por_porte.parquet` | 4 |

**empresas_por_natureza.parquet**

Apresenta a distribuição das empresas por natureza jurídica, incluindo:
- Código da natureza jurídica.
- Descrição oficial da natureza jurídica.
- Quantidade de empresas.
- Capital social total.
- Capital social médio.

**capital_por_porte.parquet**

Apresenta a distribuição das empresas por porte, incluindo:
- Código e descrição do porte.
- Quantidade de empresas.
- Capital social total.
- Capital social médio.

Os resultados correspondem exclusivamente à partição `Empresas0.zip`, na competência analisada.

## 8. Auditoria

Ao final da execução, é gerado `data/2026-10/auditoria.json`, contendo:

- Competência e arquivos de empresas processados, incluindo a tabela auxiliar `Naturezas.zip`;
- Data e hora da execução em UTC;
- Total de registros;
- Indicadores de qualidade;
- Status do pipeline.

Na execução validada, o status foi `SUCESSO`.

## 9. Decisões técnicas e melhorias futuras

**Decisões técnicas:**
- Processamento em lotes para reduzir o consumo de memória.
- Parquet para armazenamento colunar e comprimido.
- DuckDB para consultas, relacionamentos e agregações analíticas.
- `LEFT JOIN` para enriquecer os dados sem descartar registros de empresas.
- Download automático das tabelas oficiais de naturezas jurídicas e qualificações dos responsáveis.
- Docker para padronização e reprodutibilidade do ambiente.
- Schema explícito para garantir consistência dos dados.
- Pytest para testes automatizados das regras de qualidade e da geração da camada Gold.

**Escopo do processamento:**

O case foi desenvolvido considerando a competência `2026-10` e a partição `Empresas0.zip`, conforme solicitado no enunciado. A arquitetura permite parametrizar a competência e os arquivos de entrada.

**Melhorias futuras:**
- Adicionar checksum para validação da integridade dos arquivos baixados.
- Implementar monitoramento e alertas de falhas.
- Implementar histórico e particionamento dos dados por competência.
- Ampliar a cobertura dos testes automatizados para outras etapas do pipeline.

## 10. Considerações finais

O projeto demonstra a implementação de um pipeline de Engenharia de Dados com ingestão, processamento em lotes, validação de qualidade, modelagem analítica e auditoria.

A solução prioriza simplicidade, organização, reprodutibilidade e uso de ferramentas open source.

**Escopo dos resultados:** partição `Empresas0.zip`, competência outubro de 2026. Os indicadores não representam a totalidade da base nacional de CNPJs.
