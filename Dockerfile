FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Instala o DuckDB CLI para consultas SQL no terminal
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && curl -L https://install.duckdb.org | sh \
    && ln -s /root/.duckdb/cli/latest/duckdb /usr/local/bin/duckdb \
    && apt-get remove -y curl \
    && rm -rf /var/lib/apt/lists/*

COPY src/ ./src/
COPY tests/ ./tests/

CMD ["python", "-m", "src.pipeline"]
