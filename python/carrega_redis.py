import os
import sys
import time
import argparse
from typing import List, Tuple

import psycopg2
from psycopg2.extras import RealDictCursor
import redis

QUERY_USUARIOS_QUE_PODEM_LOGAR = """
SELECT u.id AS usuario_id, u.nome
FROM auth.usuario u
WHERE u.ativo = true
  AND u.pode_acessar = true
  AND EXISTS (
    SELECT 1
    FROM auth.usuario_contrato uc
    JOIN auth.contrato c ON c.id = uc.contrato_id
    WHERE uc.usuario_id = u.id
      AND uc.ativo = true
      AND c.ativo = true
  )
ORDER BY u.id;
"""

def get_pg_conn():
    dsn = {
        "host": os.getenv("PGHOST", "poc-pg-acesso"),
        "port": int(os.getenv("PGPORT", "5432")),
        "dbname": os.getenv("PGDATABASE", "acesso"),
        "user": os.getenv("PGUSER", "poc"),
        "password": os.getenv("PGPASSWORD", "poc"),
    }
    conn = psycopg2.connect(**dsn)
    conn.autocommit = True
    return conn

def get_redis_client():
    host = os.getenv("REDIS_HOST", "poc-redis")
    port = int(os.getenv("REDIS_PORT", "6379"))
    db = int(os.getenv("REDIS_DB", "0"))
    return redis.Redis(host=host, port=port, db=db, decode_responses=True)


def fetch_users(conn) -> List[Tuple[int, str]]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(QUERY_USUARIOS_QUE_PODEM_LOGAR)
        rows = cur.fetchall()
        return [(int(r["usuario_id"]), r["nome"]) for r in rows]

def init_redis(users: List[Tuple[int, str]], r: redis.Redis, prefix: str, set_name: str, dry_run: bool = False):
    """
    Escreve em Redis:
      - SET {prefix}{id} -> "1"
      - SADD {set_name}  -> id
    Usa pipeline para performance.
    """
    if not users:
        print("Nenhum usuário elegível encontrado (n=0).")
        return

    pipe = r.pipeline(transaction=False)
    for uid, _nome in users:
        key = f"{prefix}{uid}"
        if dry_run:
            print(f"[dry-run] SET {key} 1 ; SADD {set_name} {uid}")
        else:
            pipe.set(key, "1")
            pipe.sadd(set_name, uid)
    if not dry_run:
        pipe.execute()
        print(f"Inicialização concluída: {len(users)} usuários marcados no Redis.")
    else:
        print(f"[dry-run] Simulação concluída: {len(users)} comandos.")

def parse_args():
    p = argparse.ArgumentParser(description="Inicializa Redis com usuários que podem logar (a partir do Postgres).")
    p.add_argument("--dry-run", action="store_true", help="Não escreve no Redis; apenas imprime comandos.")
    p.add_argument("--prefix", default=os.getenv("REDIS_PREFIX", "access:"), help="Prefixo das chaves SET (default: access:)")
    p.add_argument("--set-name", default=os.getenv("REDIS_SET_NAME", "acesso:ativos"), help="Nome do SET agregado (default: acesso:ativos)")
    return p.parse_args()


def main():
    args = parse_args()

    print("→ Conectando ao Postgres...")
    conn = get_pg_conn()
    try:
        users = fetch_users(conn)
        print(f"✔ Encontrados {len(users)} usuários que podem logar.")
    finally:
        conn.close()

    print("→ Conectando ao Redis...")
    r = get_redis_client()

    started = time.time()
    init_redis(users, r, prefix=args.prefix, set_name=args.set_name, dry_run=args.dry_run)
    elapsed = time.time() - started
    print(f"Tempo total: {elapsed:.2f}s")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Erro: {e}", file=sys.stderr)
        sys.exit(1)