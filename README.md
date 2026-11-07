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
              Receita Federal
                    |
          +---------+---------+
          |                   |
          v                   v
     Empresas0.zip       Naturezas.zip
          |                   |
          +---------+---------+
                    |
                    v
                  BRONZE
               Dados brutos
                    |
                    v
                  SILVER
             Empresas tratadas
                 Parquet
                    |
                    v
                  DUCKDB
             +------+------+
             |             |
             v             v
          empresas   naturezas_juridicas
             |             |
             +------+------+
                    |
                 LEFT JOIN
                    |
                    v
                   GOLD
             Indicadores analíticos
                  Parquet
```

**Bronze – Dados brutos**
- Download e armazenamento dos arquivos ZIP das empresas e das naturezas jurídicas.
- Validação da integridade dos arquivos.
- Reutilização de arquivos válidos já existentes.

**Silver – Dados tratados**
- Leitura em lotes (*chunks*) de 250 mil registros.
- Padronização dos campos e conversão do capital social para decimal.
- Validação do CNPJ básico e identificação de dados inválidos ou ausentes.
- Armazenamento em Parquet com schema definido.

**DuckDB – Armazenamento e relacionamento**
- Criação da tabela `empresas` a partir dos dados Silver.
- Criação da tabela `naturezas_juridicas` a partir do arquivo oficial `Naturezas.zip`.
- Relacionamento entre as tabelas pelo código da natureza jurídica.

**Gold – Dados analíticos**

São gerados dois arquivos Parquet:

| Arquivo | Conteúdo |
|---|---|
| `empresas_por_natureza.parquet` | Código e descrição oficial da natureza jurídica, quantidade de empresas, capital total e capital médio. |
| `capital_por_porte.parquet` | Quantidade de empresas, capital total e capital médio por porte. |

A consulta de natureza jurídica utiliza `LEFT JOIN`, preservando os registros de empresas mesmo quando não existe correspondência na tabela auxiliar. Quando uma descrição não é encontrada, o resultado recebe o texto `Não encontrada`.

Além dos arquivos analíticos, os dados detalhados são disponibilizados na tabela `empresas`, armazenada no banco DuckDB (`data/cnpj.duckdb`). A tabela auxiliar fica disponível em `naturezas_juridicas`.

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

Ao final da execução, é gerado `data/auditoria.json`, contendo:

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
- LEFT JOIN para enriquecer os dados sem descartar registros de empresas.
- Download automático da tabela oficial de naturezas jurídicas.
- Docker para padronização do ambiente.
- Schema explícito para garantir consistência dos dados.

**Melhorias futuras:**
- Processar as dez partições da base.
- Implementar testes automatizados com Pytest.
- Adicionar checksum e monitoramento da execução.
- Implementar histórico e particionamento por competência.

## 10. Considerações finais

O projeto demonstra a implementação de um pipeline de Engenharia de Dados com ingestão, processamento em lotes, validação de qualidade, modelagem analítica e auditoria.

A solução prioriza simplicidade, organização, reprodutibilidade e uso de ferramentas open source.

**Escopo dos resultados:** partição `Empresas0.zip`, competência outubro de 2026. Os indicadores não representam a totalidade da base nacional de CNPJs.
