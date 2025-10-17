-- CURSOS (FKs e filtros frequentes)
CREATE INDEX IF NOT EXISTS ix_cursos_categoria  ON edutech.cursos (categoria_id);
CREATE INDEX IF NOT EXISTS ix_cursos_instrutor  ON edutech.cursos (instrutor_id);
-- Nível tem baixa cardinalidade; indexe só se você realmente filtrar muito por nivel:
-- CREATE INDEX IF NOT EXISTS ix_cursos_nivel      ON edutech.cursos (nivel);

-- MODULOS
CREATE INDEX IF NOT EXISTS ix_modulos_curso     ON edutech.modulos (curso_id);
-- (UNIQUE já cobre (curso_id, ordem))

-- AULAS
CREATE INDEX IF NOT EXISTS ix_aulas_modulo      ON edutech.aulas (modulo_id);
-- (UNIQUE já cobre (modulo_id, ordem))

-- MATRICULAS (FKs + datas/status)
CREATE INDEX IF NOT EXISTS ix_matriculas_aluno  ON edutech.matriculas (aluno_id);
CREATE INDEX IF NOT EXISTS ix_matriculas_curso  ON edutech.matriculas (curso_id);
CREATE INDEX IF NOT EXISTS ix_matriculas_data   ON edutech.matriculas (data_matricula);
-- Status é enum de baixa cardinalidade; use parcial se "ativa" for muito consultada:
CREATE INDEX IF NOT EXISTS ix_matriculas_ativas
  ON edutech.matriculas (curso_id, data_matricula)
  WHERE status = 'ativa';

-- PROGRESSO_AULAS
CREATE INDEX IF NOT EXISTS ix_prog_matricula    ON edutech.progresso_aulas (matricula_id);
CREATE INDEX IF NOT EXISTS ix_prog_aula         ON edutech.progresso_aulas (aula_id);
-- (UNIQUE já cobre (matricula_id, aula_id))

-- AVALIACOES
CREATE INDEX IF NOT EXISTS ix_avaliacoes_curso  ON edutech.avaliacoes (curso_id);
-- (UNIQUE já cobre (matricula_id))

-- ALUNOS / INSTRUTORES / CATEGORIAS
-- e-mails e nomes únicos já têm índice por causa do UNIQUE.
-- Se você fizer buscas por nome com ILIKE, considere pg_trgm:
-- CREATE EXTENSION IF NOT EXISTS pg_trgm;
-- CREATE INDEX IF NOT EXISTS ix_alunos_nome_trgm      ON edutech.alunos      USING gin (nome gin_trgm_ops);
-- CREATE INDEX IF NOT EXISTS ix_instrutores_nome_trgm ON edutech.instrutores USING gin (nome gin_trgm_ops);
-- CREATE INDEX IF NOT EXISTS ix_categorias_nome_trgm  ON edutech.categorias  USING gin (nome gin_trgm_ops);
