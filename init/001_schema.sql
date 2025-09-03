CREATE SCHEMA IF NOT EXISTS auth;

-- 1. Usuário
CREATE TABLE IF NOT EXISTS auth.usuario (
  id BIGSERIAL PRIMARY KEY,
  nome TEXT NOT NULL,
  email TEXT UNIQUE,
  pode_acessar BOOLEAN NOT NULL DEFAULT true,
  ativo BOOLEAN NOT NULL DEFAULT true, -- ativo/inativo em vez de exclusão
  criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
  atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2. Contrato
CREATE TABLE IF NOT EXISTS auth.contrato (
  id BIGSERIAL PRIMARY KEY,
  descricao TEXT,
  ativo BOOLEAN NOT NULL DEFAULT true,
  criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
  atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3. Relação Usuário-Contrato
CREATE TABLE IF NOT EXISTS auth.usuario_contrato (
  usuario_id BIGINT NOT NULL REFERENCES auth.usuario(id),
  contrato_id BIGINT NOT NULL REFERENCES auth.contrato(id),
  ativo BOOLEAN NOT NULL DEFAULT true, -- vínculo ativo/inativo
  criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
  atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (usuario_id, contrato_id)
);

-- 4. Dados iniciais
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

-- vínculo inicial
INSERT INTO auth.usuario_contrato (usuario_id, contrato_id, ativo) VALUES
  (1, 1, true),  -- Alice → Premium (ativo)
  (1, 2, false), -- Alice → Trial (inativo)
  (2, 2, true),  -- Bruno → Trial (mas contrato inativo → acesso não vale)
  (3, 3, true)   -- Carla → Padrão (ativo) mas Carla tem pode_acessar=false
ON CONFLICT DO NOTHING;
