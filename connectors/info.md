## Modos principais do `snapshot.mode` (Debezium)

| Modo          | Faz snapshot inicial? | Continua lendo WAL? | Uso típico |
|---------------|-----------------------|---------------------|------------|
| **initial** (default) | Sim, sempre | Sim | Preencher destino do zero e depois acompanhar mudanças |
| **initial_only** | Sim, sempre | Não | Migração/ETL pontual (somente carga inicial) |
| **never** | Não | Sim | Destino já está cheio, só aplicar deltas futuros |
| **exported** (Postgres) | Sim, via `EXPORT SNAPSHOT` | Sim | Garantir consistência forte entre snapshot e WAL |
| **when_needed** | Apenas se offset não existir | Sim | Reprocessar só se não houver posição anterior |
| **custom** | Depende da implementação | Depende | Casos avançados com snapshot sob medida |
