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
```sql
---

#Criar tópicos 
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

## Criar conector via REST
```bash
curl -s -X POST http://localhost:8083/connectors \
-H 'Content-Type: application/json' \
-d @connectors/debezium-postgres.json | jq .
```
## Conferir status
curl -s http://localhost:8083/connectors/pg-acesso-debezium/status | jq .

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

CREATE TABLE USUARIO AS
  SELECT
    CAST(USUARIO_SRC->after->id AS BIGINT) AS usuario_id,
    LATEST_BY_OFFSET(
      CAST(USUARIO_SRC->after->ativo AS BOOLEAN)
      AND
      CAST(USUARIO_SRC->after->pode_acessar AS BOOLEAN)
    ) AS pode
  FROM USUARIO_SRC
  WHERE USUARIO_SRC->op IN ('c','u','r')   -- ignora tombstones
  GROUP BY CAST(USUARIO_SRC->after->id AS BIGINT);



```
