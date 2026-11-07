# Case Engenharia de Dados – CNPJ

## 1. Objetivo

Desenvolver um pipeline de Engenharia de Dados para ingestão, transformação, validação e análise dos dados públicos de empresas da Receita Federal.

A solução utiliza Python, DuckDB, Parquet e Docker, seguindo uma arquitetura organizada em camadas Bronze, Silver e Gold.

## 2. Fonte de dados e escopo

- **Fonte:** Dados Abertos do CNPJ – Receita Federal.
- **Competência:** Outubro de 2026 (`2026-10`).
- **Arquivo processado:** `Empresas0.zip`.
- **Formato original:** CSV delimitado por ponto e vírgula, codificação Latin-1.

A base de empresas é dividida em dez partições (`Empresas0` a `Empresas9`). Neste processamento foi utilizada somente a partição `Empresas0`. Portanto, os resultados não representam a totalidade das empresas brasileiras.

## 3. Arquitetura

```text
Receita Federal
      |
      v
   BRONZE
 Arquivos ZIP
      |
      v
   SILVER
 Dados tratados
    Parquet
      |
      v
    GOLD
 Indicadores
```

**Bronze – Dados brutos**
- Download e armazenamento dos arquivos ZIP.
- Validação da integridade dos arquivos.

**Silver – Dados tratados**
- Leitura em lotes (*chunks*).
- Padronização dos campos e conversão do capital social para decimal.
- Validação do CNPJ básico e identificação de dados inválidos ou ausentes.
- Armazenamento em Parquet com schema definido.

**Gold – Dados analíticos**

São gerados dois arquivos Parquet:
- Arquivo	- Conteúdo
- empresas_por_natureza.parquet - Quantidade de empresas, capital total e médio por natureza jurídica.
- capital_por_porte.parquet	- Quantidade de empresas, capital total e médio por porte.

Além dos arquivos analíticos, os dados detalhados são disponibilizados em uma tabela chamada empresas, armazenada no banco DuckDB (data/cnpj.duckdb). Essa tabela permite realizar consultas SQL diretamente sobre os registros tratados, sem necessidade de gerar novos arquivos para cada análise.

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

O processamento executa download, transformação, validação, geração da Gold e auditoria.

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
| Naturezas ausentes | 0 |
| Portes ausentes | 4.109 |

Os 4.109 registros sem porte informado foram preservados e classificados como `Não informado`. Todos apresentam capital social igual a zero.

### Classificação por porte

| Código | Descrição |
|---|---|
| 01 | Microempresa |
| 03 | Empresa de Pequeno Porte |
| 05 | Demais |
| Vazio | Não informado |

## 7. Resultados da camada Gold

| Arquivo | Registros |
|---|---:|
| `empresas_por_natureza.parquet` | 84 |
| `capital_por_porte.parquet` | 4 |

Os indicadores contemplam quantidade de empresas, capital total e capital médio por agrupamento.

## 8. Auditoria

Ao final da execução, é gerado `data/auditoria.json`, contendo:

- Competência e arquivos processados;
- Data e hora da execução em UTC;
- Total de registros;
- Indicadores de qualidade;
- Status do pipeline.

Na execução validada, o status foi `SUCESSO`.

## 9. Decisões técnicas e melhorias futuras

**Decisões técnicas:**
- Processamento em lotes para reduzir o consumo de memória.
- Parquet para armazenamento colunar e comprimido.
- DuckDB para consultas e agregações analíticas.
- Docker para padronização do ambiente.
- Schema explícito para garantir consistência dos dados.

**Melhorias futuras:**
- Processar as dez partições da base.
- Incorporar tabelas auxiliares, como a descrição das naturezas jurídicas.
- Implementar testes automatizados com Pytest.
- Adicionar checksum e monitoramento da execução.
- Implementar histórico e particionamento por competência.

## 10. Considerações finais

O projeto demonstra a implementação de um pipeline de Engenharia de Dados com ingestão, processamento em lotes, validação de qualidade, modelagem analítica e auditoria.

A solução prioriza simplicidade, organização, reprodutibilidade e uso de ferramentas open source.

**Escopo dos resultados:** partição `Empresas0.zip`, competência outubro de 2026. Os indicadores não representam a totalidade da base nacional de CNPJs.