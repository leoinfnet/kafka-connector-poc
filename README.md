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

# No Compose Para elimiar warnings 
```sql

# ksqldb
  ksqldb:
    environment:
      KSQL_JMX_OPTS: "-Dcom.sun.management.jmxremote=false"

# connect
  connect:
    environment:
      KAFKA_JMX_OPTS: "-Dcom.sun.management.jmxremote=false"

# kafka broker (opcional)
  kafka:
    environment:
      KAFKA_JMX_OPTS: "-Dcom.sun.management.jmxremote=false"
```
## Ou
```sql
docker exec -it \
  -e KSQL_JMX_OPTS="-Dcom.sun.management.jmxremote=false" \
  poc-ksqldb ksql http://localhost:8088



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
### Entrar no Postgres
```bash
docker exec -it poc-pg-acesso psql -U poc -d acesso
```
---

# Criar tópicos 
```bash
docker exec -it poc-kafka kafka-topics \
  --bootstrap-server kafka:9092 \
  --create --topic pg.auth.usuario \
  --partitions 1 --replication-factor 1

docker exec -it poc-kafka kafka-topics \
  --bootstrap-server kafka:9092 \
  --create --topic pg.auth.contrato \
  --partitions 1 --replication-factor 1

docker exec -it poc-kafka kafka-topics \
  --bootstrap-server kafka:9092 \
  --create --topic pg.auth.usuario_contrato \
  --partitions 1 --replication-factor 1
```


# CONECTORES

## Criar conector via REST do POSTGRES
```bash
curl -s -X POST http://localhost:8083/connectors \
-H 'Content-Type: application/json' \
-d @connectors/debezium-postgres.json | jq .
```

## Criar conector via REST do REDIS
```bash
curl -s -X POST http://localhost:8084/connectors \
-H 'Content-Type: application/json' \
-d @connectors/redis-sink.json | jq .
```

## Criar conector via REST do REDIS para validar

```bash
curl -X POST http://localhost:8084/connectors \
  -H "Content-Type: application/json" \
  -d @connectors/redis-validar-sink.json
``` 



## Conferir status POTGRES
curl -s http://localhost:8083/connectors/pg-acesso-debezium/status | jq .

## Conferir status REDIS
curl -s http://localhost:8084/connectors/redis-invalidar-sink/status | jq .

# Testando CDC
```
docker exec -it poc-pg-acesso psql -U poc -d acesso
```
```sql
-- Ativar um contrato que estava inativo
UPDATE auth.contrato SET ativo = true, atualizado_em = now() WHERE id = 2;


-- Ligar um usuário a um contrato
INSERT INTO auth.usuario_contrato (usuario_id, contrato_id, ativo) VALUES (2, 1, true)
ON CONFLICT (usuario_id, contrato_id) DO UPDATE SET ativo = EXCLUDED.ativo, atualizado_em = now();


-- Desativar vínculo (sem deletar)
UPDATE auth.usuario_contrato SET ativo = false, atualizado_em = now() WHERE usuario_id = 1 AND contrato_id = 2;


-- Bloquear acesso lógico de um usuário
UPDATE auth.usuario SET pode_acessar = false, atualizado_em = now() WHERE id = 1;
```
---



# KSQLDB

```bash
docker exec -it poc-ksqldb ksql http://localhost:8088
```
# Criando STREAMS
```sql
CREATE STREAM USUARIO_SRC (
  op STRING,
  after STRUCT<
    id BIGINT,
    nome STRING,
    email STRING,
    pode_acessar BOOLEAN,
    ativo BOOLEAN
  >
) WITH (
  KAFKA_TOPIC='pg.auth.usuario',
  VALUE_FORMAT='JSON',
  KEY_FORMAT='JSON'
);

CREATE STREAM USUARIO_BY_ID
  WITH (KAFKA_TOPIC='pg.auth.usuario.by_id',
        VALUE_FORMAT='JSON',
        KEY_FORMAT='JSON') AS
SELECT
  after->id            AS id,          -- vira a CHAVE
  after->nome          AS nome,
  after->email         AS email,
  after->pode_acessar  AS pode_acessar,
  after->ativo         AS ativo
FROM USUARIO_SRC
WHERE after IS NOT NULL
PARTITION BY after->id
EMIT CHANGES;


CREATE STREAM USUARIOS_INVALIDAR
  WITH (
    KAFKA_TOPIC='usuarios.invalidar',
    VALUE_FORMAT='JSON',
    KEY_FORMAT='JSON'
  ) AS
SELECT
  id       AS user_id,     -- vira coluna de valor
  'inactive' AS reason
FROM USUARIO_BY_ID          -- <- STREAM!
WHERE ativo = FALSE or pode_acessar = FALSE
EMIT CHANGES;

CREATE STREAM USUARIOS_VALIDAR
  WITH (
    KAFKA_TOPIC='usuarios.validar',
    VALUE_FORMAT='JSON',
    KEY_FORMAT='JSON'
  ) AS
SELECT
  id       AS user_id,     -- vira coluna de valor
  'active' AS reason
FROM USUARIO_BY_ID          -- <- STREAM!
WHERE ativo = TRUE AND pode_acessar = TRUE
EMIT CHANGES;


CREATE STREAM USUARIOS_PODE_LOGAR
  WITH (
    KAFKA_TOPIC='usuarios.pode_logar',
    VALUE_FORMAT='JSON',
    KEY_FORMAT='JSON'
  ) AS
SELECT
  id        AS user_id,
  nome      AS nome,
  email     AS email,
  pode_acessar,
  ativo
FROM USUARIO_BY_ID
WHERE pode_acessar = TRUE
  AND ativo = TRUE
EMIT CHANGES;



CREATE STREAM USUARIOS_STATUS_STREAM
  WITH (
    KAFKA_TOPIC='usuarios.status.stream',
    VALUE_FORMAT='JSON',
    KEY_FORMAT='JSON'
  ) AS
SELECT user_id, reason FROM USUARIOS_VALIDAR
EMIT CHANGES;


INSERT INTO USUARIOS_STATUS_STREAM
SELECT user_id, reason FROM USUARIOS_INVALIDAR
EMIT CHANGES;


CREATE STREAM CONTRATO_SRC (
  op STRING,
  after STRUCT<
    id BIGINT,
    descricao STRING,
    ativo BOOLEAN
  >
) WITH (
  KAFKA_TOPIC='pg.auth.contrato',
  VALUE_FORMAT='JSON',
  KEY_FORMAT='JSON'
);


CREATE STREAM UC_SRC (
  op STRING,
  after STRUCT<
    usuario_id BIGINT,
    contrato_id BIGINT,
    ativo BOOLEAN
  >
) WITH (
  KAFKA_TOPIC='pg.auth.usuario_contrato',
  VALUE_FORMAT='JSON',
  KEY_FORMAT='JSON'
);


```


# Criando KTables
```sql

-- garante leitura desde o início no console
SET 'auto.offset.reset' = 'earliest';



CREATE TABLE USUARIO
WITH (KAFKA_TOPIC='USUARIO', VALUE_FORMAT='JSON') AS
  SELECT
    CAST(after->id AS BIGINT) AS usuario_id,
    LATEST_BY_OFFSET(
      CAST(after->ativo AS BOOLEAN)
      AND
      CAST(after->pode_acessar AS BOOLEAN)
    ) AS pode
  FROM USUARIO_SRC
  WHERE op IN ('c','u','r') AND after IS NOT NULL
  GROUP BY CAST(after->id AS BIGINT);

CREATE TABLE USUARIO_TBL (
  id BIGINT PRIMARY KEY,
  nome STRING,
  email STRING,
  pode_acessar BOOLEAN,
  ativo BOOLEAN
) WITH (
  KAFKA_TOPIC='pg.auth.usuario.by_id',
  VALUE_FORMAT='JSON',
  KEY_FORMAT='JSON'
);


CREATE TABLE USUARIOS_STATUS
  WITH (
    KAFKA_TOPIC='usuarios.status',
    VALUE_FORMAT='JSON',
    KEY_FORMAT='JSON'
  ) AS
SELECT
  user_id,
  LATEST_BY_OFFSET(reason) AS reason
FROM USUARIOS_STATUS_STREAM
GROUP BY user_id
EMIT CHANGES;


DESCRIBE USUARIO;

-- ver algumas linhas (lembrando: é TABLE, mas dá pra espiar mudanças)
SELECT usuario_id, pode FROM USUARIO EMIT CHANGES LIMIT 10;


SELECT * FROM USUARIOS_INVALIDAR EMIT CHANGES LIMIT 5;
