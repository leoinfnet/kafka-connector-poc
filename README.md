# POC Debezium + Kafka Connect — Passo a passo completo

Este README.md documenta a prova de conceito (POC) com **Postgres + Debezium + Kafka Connect + Kafka UI**. Ele guia desde a criação do banco até o registro dos conectores.

## 1) Preparar o Postgres (com CDC habilitado)

### Estrutura de pastas
```
poc-pg/
 ├─ docker-compose.yml
 └─ initdb/
     └─ 001_schema.sql
```

### docker-compose.yml (somente Postgres + rede POC)
```yaml
version: "3.9"

networks:
  POC:
    name: POC

services:
  postgres:
    image: postgres:16
    container_name: poc-pg-acesso
    environment:
      POSTGRES_USER: poc
      POSTGRES_PASSWORD: poc
      POSTGRES_DB: acesso
    ports:
      - "5432:5432"
    command:
      - "postgres"
      - "-c"
      - "wal_level=logical"
      - "-c"
      - "max_wal_senders=10"
      - "-c"
      - "max_replication_slots=10"
      - "-c"
      - "wal_keep_size=256MB"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U poc -d acesso"]
      interval: 5s
      timeout: 3s
      retries: 20
    volumes:
      - ./initdb:/docker-entrypoint-initdb.d
    networks: [POC]
```

### initdb/001_schema.sql (modelo de dados atualizado)
```sql
CREATE SCHEMA IF NOT EXISTS auth;

CREATE TABLE IF NOT EXISTS auth.usuario (
  id BIGSERIAL PRIMARY KEY,
  nome TEXT NOT NULL,
  email TEXT UNIQUE,
  pode_acessar BOOLEAN NOT NULL DEFAULT true,
  ativo BOOLEAN NOT NULL DEFAULT true,
  criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
  atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS auth.contrato (
  id BIGSERIAL PRIMARY KEY,
  descricao TEXT,
  ativo BOOLEAN NOT NULL DEFAULT true,
  criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
  atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS auth.usuario_contrato (
  usuario_id BIGINT NOT NULL REFERENCES auth.usuario(id),
  contrato_id BIGINT NOT NULL REFERENCES auth.contrato(id),
  ativo BOOLEAN NOT NULL DEFAULT true,
  criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
  atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (usuario_id, contrato_id)
);

INSERT INTO auth.usuario (nome, email, pode_acessar) VALUES
  ('Alice', 'alice@example.com', true),
  ('Bruno', 'bruno@example.com', true),
  ('Carla', 'carla@example.com', false)
ON CONFLICT DO NOTHING;

INSERT INTO auth.contrato (descricao, ativo) VALUES
  ('Contrato Premium', true),
  ('Contrato Trial', false),
  ('Contrato Padrão', true)
ON CONFLICT DO NOTHING;

INSERT INTO auth.usuario_contrato (usuario_id, contrato_id, ativo) VALUES
  (1, 1, true),
  (1, 2, false),
  (2, 2, true),
  (3, 3, true);
```

### Query de acesso consolidado
```sql
SELECT
  u.id   AS usuario_id,
  u.nome,
  (u.ativo AND u.pode_acessar AND COALESCE(BOOL_OR(uc.ativo AND c.ativo), FALSE)) AS acesso
FROM auth.usuario u
LEFT JOIN auth.usuario_contrato uc ON uc.usuario_id = u.id
LEFT JOIN auth.contrato c          ON c.id = uc.contrato_id
GROUP BY u.id, u.nome, u.ativo, u.pode_acessar
ORDER BY u.id;
```
