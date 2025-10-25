-- ============================================================
-- EduTech - Schema & DDL completo
-- PostgreSQL
-- ============================================================

-- Extensão para texto case-insensitive (e-mails)
CREATE EXTENSION IF NOT EXISTS citext;

-- Schema do projeto
CREATE SCHEMA IF NOT EXISTS edutech;
SET search_path TO edutech, public;

-- =========================
-- Tipos ENUM
-- =========================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'nivel_enum') THEN
        CREATE TYPE nivel_enum AS ENUM ('iniciante','intermediario','avancado');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'aula_tipo_enum') THEN
        CREATE TYPE aula_tipo_enum AS ENUM ('video','texto','quiz');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'status_matricula_enum') THEN
        CREATE TYPE status_matricula_enum AS ENUM ('ativa','concluida','cancelada');
    END IF;
END$$;

-- =========================
-- Tabelas principais
-- =========================

-- ALUNOS
CREATE TABLE IF NOT EXISTS alunos (
  id               BIGSERIAL PRIMARY KEY,
  nome             VARCHAR(100) NOT NULL
                     CHECK (btrim(nome) <> ''),
  email            CITEXT NOT NULL UNIQUE
                     CHECK (
                       email = btrim(email) AND
                       email ~ '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'
                     ),
  data_nascimento  DATE NOT NULL
                     CHECK (data_nascimento BETWEEN DATE '1900-01-01' AND CURRENT_DATE),
  data_cadastro    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE alunos IS 'Cadastro de alunos';
COMMENT ON COLUMN alunos.email IS 'Único (case-insensitive) e com formato válido';

-- INSTRUTORES
CREATE TABLE IF NOT EXISTS instrutores (
  id               BIGSERIAL PRIMARY KEY,
  nome             VARCHAR(100) NOT NULL
                     CHECK (btrim(nome) <> ''),
  email            CITEXT NOT NULL UNIQUE
                     CHECK (
                       email = btrim(email) AND
                       email ~ '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'
                     ),
  especialidade    VARCHAR(100) NOT NULL
                     CHECK (btrim(especialidade) <> ''),
  biografia        TEXT
);

-- CATEGORIAS
CREATE TABLE IF NOT EXISTS categorias (
  id               BIGSERIAL PRIMARY KEY,
  nome             VARCHAR(80)  NOT NULL UNIQUE
                     CHECK (btrim(nome) <> ''),
  descricao        TEXT
);

-- CURSOS
CREATE TABLE IF NOT EXISTS cursos (
  id               BIGSERIAL PRIMARY KEY,
  titulo           VARCHAR(150) NOT NULL
                     CHECK (btrim(titulo) <> ''),
  descricao        TEXT,
  categoria_id     BIGINT NOT NULL,
  instrutor_id     BIGINT NOT NULL,
  preco            NUMERIC(10,2) NOT NULL CHECK (preco >= 0),
  carga_horaria    INTEGER NOT NULL CHECK (carga_horaria > 0), -- em horas
  nivel            nivel_enum NOT NULL,
  data_criacao     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT fk_cursos_categoria  FOREIGN KEY (categoria_id) REFERENCES categorias(id) ON DELETE RESTRICT,
  CONSTRAINT fk_cursos_instrutor  FOREIGN KEY (instrutor_id) REFERENCES instrutores(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS ix_cursos_categoria  ON cursos(categoria_id);
CREATE INDEX IF NOT EXISTS ix_cursos_instrutor  ON cursos(instrutor_id);
CREATE INDEX IF NOT EXISTS ix_cursos_nivel      ON cursos(nivel);

-- MODULOS
CREATE TABLE IF NOT EXISTS modulos (
  id               BIGSERIAL PRIMARY KEY,
  curso_id         BIGINT NOT NULL,
  titulo           VARCHAR(150) NOT NULL
                     CHECK (btrim(titulo) <> ''),
  ordem            SMALLINT NOT NULL CHECK (ordem >= 1),
  descricao        TEXT,
  CONSTRAINT fk_modulos_curso FOREIGN KEY (curso_id) REFERENCES cursos(id) ON DELETE CASCADE,
  CONSTRAINT uq_modulos_curso_ordem UNIQUE (curso_id, ordem)
);
CREATE INDEX IF NOT EXISTS ix_modulos_curso ON modulos(curso_id);

-- AULAS
CREATE TABLE IF NOT EXISTS aulas (
  id                 BIGSERIAL PRIMARY KEY,
  modulo_id          BIGINT NOT NULL,
  titulo             VARCHAR(150) NOT NULL
                       CHECK (btrim(titulo) <> ''),
  ordem              SMALLINT NOT NULL CHECK (ordem >= 1),
  duracao_minutos    SMALLINT NOT NULL CHECK (duracao_minutos >= 1),
  tipo               aula_tipo_enum NOT NULL,
  CONSTRAINT fk_aulas_modulo FOREIGN KEY (modulo_id) REFERENCES modulos(id) ON DELETE CASCADE,
  CONSTRAINT uq_aulas_modulo_ordem UNIQUE (modulo_id, ordem)
);
CREATE INDEX IF NOT EXISTS ix_aulas_modulo ON aulas(modulo_id);

-- MATRICULAS
CREATE TABLE IF NOT EXISTS matriculas (
  id               BIGSERIAL PRIMARY KEY,
  aluno_id         BIGINT NOT NULL,
  curso_id         BIGINT NOT NULL,
  data_matricula   DATE NOT NULL,
  data_conclusao   DATE,
  status           status_matricula_enum NOT NULL,
  valor_pago       NUMERIC(10,2) NOT NULL CHECK (valor_pago >= 0),
  CONSTRAINT fk_matriculas_aluno FOREIGN KEY (aluno_id) REFERENCES alunos(id) ON DELETE RESTRICT,
  CONSTRAINT fk_matriculas_curso FOREIGN KEY (curso_id) REFERENCES cursos(id) ON DELETE RESTRICT,
  CONSTRAINT uq_matriculas_aluno_curso UNIQUE (aluno_id, curso_id),
  CONSTRAINT ck_conclusao_gte_matricula CHECK (data_conclusao IS NULL OR data_conclusao >= data_matricula)
);
CREATE INDEX IF NOT EXISTS ix_matriculas_aluno   ON matriculas(aluno_id);
CREATE INDEX IF NOT EXISTS ix_matriculas_curso   ON matriculas(curso_id);
CREATE INDEX IF NOT EXISTS ix_matriculas_status  ON matriculas(status);
CREATE INDEX IF NOT EXISTS ix_matriculas_data    ON matriculas(data_matricula);

-- PROGRESSO_AULAS
CREATE TABLE IF NOT EXISTS progresso_aulas (
  id                         BIGSERIAL PRIMARY KEY,
  matricula_id               BIGINT NOT NULL,
  aula_id                    BIGINT NOT NULL,
  concluida                  BOOLEAN NOT NULL DEFAULT FALSE,
  data_conclusao             TIMESTAMPTZ,
  tempo_assistido_minutos    INTEGER NOT NULL DEFAULT 0 CHECK (tempo_assistido_minutos >= 0),
  CONSTRAINT fk_prog_matricula FOREIGN KEY (matricula_id) REFERENCES matriculas(id) ON DELETE CASCADE,
  CONSTRAINT fk_prog_aula      FOREIGN KEY (aula_id)      REFERENCES aulas(id) ON DELETE CASCADE,
  CONSTRAINT uq_prog_matricula_aula UNIQUE (matricula_id, aula_id),
  CONSTRAINT ck_conclusao_coerente CHECK (
    (concluida = TRUE  AND data_conclusao IS NOT NULL) OR
    (concluida = FALSE AND data_conclusao IS NULL)
  )
);
CREATE INDEX IF NOT EXISTS ix_prog_matricula ON progresso_aulas(matricula_id);
CREATE INDEX IF NOT EXISTS ix_prog_aula      ON progresso_aulas(aula_id);

-- AVALIACOES
CREATE TABLE IF NOT EXISTS avaliacoes (
  id               BIGSERIAL PRIMARY KEY,
  matricula_id     BIGINT NOT NULL,
  curso_id         BIGINT NOT NULL,
  nota             SMALLINT NOT NULL CHECK (nota BETWEEN 1 AND 5),
  comentario       TEXT,
  data_avaliacao   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT fk_avaliacoes_matricula FOREIGN KEY (matricula_id) REFERENCES matriculas(id) ON DELETE CASCADE,
  CONSTRAINT fk_avaliacoes_curso     FOREIGN KEY (curso_id)     REFERENCES cursos(id) ON DELETE RESTRICT,
  CONSTRAINT uq_avaliacoes_matricula UNIQUE (matricula_id)
);
CREATE INDEX IF NOT EXISTS ix_avaliacoes_curso ON avaliacoes(curso_id);

-- ============================================================
-- Triggers de integridade de negócio
-- ============================================================

-- 1) Em avaliacoes: curso_id deve coincidir com o curso da matrícula
CREATE OR REPLACE FUNCTION fn_avaliacoes_match_curso()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE v_curso_id BIGINT;
BEGIN
  SELECT m.curso_id INTO v_curso_id FROM matriculas m WHERE m.id = NEW.matricula_id;
  IF v_curso_id IS NULL THEN
    RAISE EXCEPTION 'Matrícula % não encontrada', NEW.matricula_id;
  END IF;
  IF NEW.curso_id <> v_curso_id THEN
    RAISE EXCEPTION 'curso_id (%) não corresponde ao curso da matrícula (%)', NEW.curso_id, v_curso_id;
  END IF;
  RETURN NEW;
END$$;

DROP TRIGGER IF EXISTS trg_avaliacoes_match_curso ON avaliacoes;
CREATE TRIGGER trg_avaliacoes_match_curso
BEFORE INSERT OR UPDATE OF curso_id, matricula_id
ON avaliacoes
FOR EACH ROW EXECUTE FUNCTION fn_avaliacoes_match_curso();

-- 2) Em progresso_aulas: tempo_assistido_minutos não pode exceder a duração da aula
CREATE OR REPLACE FUNCTION fn_progresso_limita_tempo()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE v_dur SMALLINT;
BEGIN
  SELECT a.duracao_minutos INTO v_dur FROM aulas a WHERE a.id = NEW.aula_id;
  IF v_dur IS NULL THEN
    RAISE EXCEPTION 'Aula % não encontrada', NEW.aula_id;
  END IF;
  IF NEW.tempo_assistido_minutos > v_dur THEN
    RAISE EXCEPTION 'tempo_assistido_minutos (%) não pode exceder duracao_minutos da aula (%)',
                    NEW.tempo_assistido_minutos, v_dur;
  END IF;
  RETURN NEW;
END$$;

DROP TRIGGER IF EXISTS trg_progresso_limita_tempo ON progresso_aulas;
CREATE TRIGGER trg_progresso_limita_tempo
BEFORE INSERT OR UPDATE OF tempo_assistido_minutos, aula_id
ON progresso_aulas
FOR EACH ROW EXECUTE FUNCTION fn_progresso_limita_tempo();

-- ============================================================
-- Comentários (documentação)
-- ============================================================

COMMENT ON TABLE cursos          IS 'Catálogo de cursos (categoria, instrutor, nível, preço, etc.)';
COMMENT ON TABLE modulos         IS 'Estrutura hierárquica por curso (ordem única por curso)';
COMMENT ON TABLE aulas           IS 'Conteúdo por módulo (ordem única por módulo; tipo video/texto/quiz)';
COMMENT ON TABLE matriculas      IS 'Associa aluno ao curso, status e valor pago';
COMMENT ON TABLE progresso_aulas IS 'Progresso por aula dentro de uma matrícula';
COMMENT ON TABLE avaliacoes      IS 'Avaliação única por matrícula; coerência com o curso da matrícula';

-- FIM