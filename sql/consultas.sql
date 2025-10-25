SET search_path TO edutech, public;

-- =========================================================
-- (1) Listar todos os cursos com categoria e instrutor
-- =========================================================
SELECT c.id, c.titulo, cat.nome AS categoria, i.nome AS instrutor, c.nivel, c.preco
FROM cursos c
JOIN categorias  cat ON cat.id = c.categoria_id
JOIN instrutores i   ON i.id   = c.instrutor_id
ORDER BY c.titulo;

-- =========================================================
-- (2) Alunos matriculados em um curso específico
--     (altere :curso_id ou :titulo conforme necessidade)
-- =========================================================
-- por ID
SELECT a.id, a.nome, a.email, m.status, m.data_matricula
FROM matriculas m
JOIN alunos a ON a.id = m.aluno_id
WHERE m.curso_id = :curso_id
ORDER BY a.nome;

-- por título
SELECT a.id, a.nome, a.email, m.status, m.data_matricula
FROM matriculas m
JOIN alunos a ON a.id = m.aluno_id
JOIN cursos c ON c.id = m.curso_id
WHERE c.titulo ILIKE '%'||:titulo||'%'
ORDER BY a.nome;

-- =========================================================
-- (3) Aulas de um curso ordenadas por módulo e ordem
-- =========================================================
SELECT c.titulo AS curso, md.ordem AS ordem_modulo, md.titulo AS modulo,
       a.ordem AS ordem_aula, a.titulo AS aula, a.tipo, a.duracao_minutos
FROM cursos c
JOIN modulos md ON md.curso_id = c.id
JOIN aulas a    ON a.modulo_id = md.id
WHERE c.id = :curso_id
ORDER BY md.ordem, a.ordem;

-- =========================================================
-- (4) Média de avaliações de cada curso
-- =========================================================
SELECT c.id, c.titulo, ROUND(AVG(av.nota)::numeric,2) AS media_avaliacoes, COUNT(av.*) AS qtd_avaliacoes
FROM cursos c
LEFT JOIN avaliacoes av ON av.curso_id = c.id
GROUP BY c.id, c.titulo
ORDER BY media_avaliacoes DESC NULLS LAST;

-- =========================================================
-- (5) Quantos alunos por curso (matrículas)
-- =========================================================
SELECT c.id, c.titulo, COUNT(DISTINCT m.aluno_id) AS alunos_matriculados
FROM cursos c
LEFT JOIN matriculas m ON m.curso_id = c.id
GROUP BY c.id, c.titulo
ORDER BY alunos_matriculados DESC;

-- =========================================================
-- (6) Faturamento total por categoria (exclui canceladas)
-- =========================================================
SELECT cat.nome AS categoria, ROUND(SUM(m.valor_pago)::numeric,2) AS faturamento
FROM categorias cat
JOIN cursos c    ON c.categoria_id = cat.id
JOIN matriculas m ON m.curso_id = c.id AND m.status <> 'cancelada'
GROUP BY cat.nome
ORDER BY faturamento DESC;

-- =========================================================
-- (7) Curso com mais matrículas ativas
-- =========================================================
SELECT c.id, c.titulo, COUNT(*) AS matriculas_ativas
FROM cursos c
JOIN matriculas m ON m.curso_id = c.id AND m.status = 'ativa'
GROUP BY c.id, c.titulo
ORDER BY matriculas_ativas DESC, c.id
LIMIT 1;

-- =========================================================
-- (8) Alunos, cursos e % de conclusão por matrícula
-- % = aulas concluídas / total de aulas do curso
-- =========================================================
WITH total_aulas AS (
  SELECT md.curso_id, COUNT(a.id) AS total
  FROM modulos md JOIN aulas a ON a.modulo_id = md.id
  GROUP BY md.curso_id
),
conclusoes AS (
  SELECT p.matricula_id, COUNT(*) FILTER (WHERE p.concluida) AS concluidas
  FROM progresso_aulas p
  GROUP BY p.matricula_id
)
SELECT a.nome AS aluno, c.titulo AS curso,
       COALESCE(ROUND(100.0 * concl.concluidas / ta.total, 2), 0) AS perc_conclusao
FROM matriculas m
JOIN alunos a   ON a.id = m.aluno_id
JOIN cursos c   ON c.id = m.curso_id
JOIN total_aulas ta ON ta.curso_id = c.id
LEFT JOIN conclusoes concl ON concl.matricula_id = m.id
ORDER BY aluno, curso;

-- =========================================================
-- (9) Relatório completo do curso
-- instrutor, #alunos, média avaliações, faturamento (sem canceladas)
-- =========================================================
WITH base AS (
  SELECT c.id AS curso_id, c.titulo, i.nome AS instrutor
  FROM cursos c JOIN instrutores i ON i.id = c.instrutor_id
),
agg_m AS (
  SELECT m.curso_id, COUNT(DISTINCT m.aluno_id) AS alunos,
         SUM(m.valor_pago) FILTER (WHERE m.status <> 'cancelada') AS faturamento
  FROM matriculas m
  GROUP BY m.curso_id
),
agg_a AS (
  SELECT av.curso_id, AVG(av.nota) AS media
  FROM avaliacoes av
  GROUP BY av.curso_id
)
SELECT b.titulo, b.instrutor,
       COALESCE(am.alunos,0) AS alunos,
       COALESCE(ROUND(am.faturamento::numeric,2),0) AS faturamento,
       COALESCE(ROUND(aa.media::numeric,2), NULL) AS media_avaliacoes
FROM base b
LEFT JOIN agg_m am ON am.curso_id = b.curso_id
LEFT JOIN agg_a aa ON aa.curso_id = b.curso_id
WHERE b.curso_id = :curso_id;

-- =========================================================
-- (10) Instrutores: qte de cursos, total de alunos e média geral
-- =========================================================
WITH cursos_por_inst AS (
  SELECT i.id AS instrutor_id, COUNT(c.id) AS qtd_cursos
  FROM instrutores i LEFT JOIN cursos c ON c.instrutor_id = i.id
  GROUP BY i.id
),
alunos_por_inst AS (
  SELECT c.instrutor_id, COUNT(DISTINCT m.aluno_id) AS alunos_total
  FROM cursos c LEFT JOIN matriculas m ON m.curso_id = c.id
  GROUP BY c.instrutor_id
),
media_por_inst AS (
  SELECT c.instrutor_id, AVG(av.nota) AS media
  FROM cursos c JOIN avaliacoes av ON av.curso_id = c.id
  GROUP BY c.instrutor_id
)
SELECT i.nome AS instrutor,
       COALESCE(ci.qtd_cursos,0) AS cursos,
       COALESCE(ai.alunos_total,0) AS alunos_total,
       COALESCE(ROUND(mp.media::numeric,2), NULL) AS media_avaliacoes
FROM instrutores i
LEFT JOIN cursos_por_inst ci ON ci.instrutor_id = i.id
LEFT JOIN alunos_por_inst ai ON ai.instrutor_id = i.id
LEFT JOIN media_por_inst mp  ON mp.instrutor_id = i.id
ORDER BY alunos_total DESC, cursos DESC;

-- =========================================================
-- (11) Top 5 cursos mais rentáveis (sem canceladas)
-- =========================================================
SELECT c.titulo, ROUND(SUM(m.valor_pago)::numeric,2) AS receita
FROM cursos c
JOIN matriculas m ON m.curso_id = c.id AND m.status <> 'cancelada'
GROUP BY c.titulo
ORDER BY receita DESC
LIMIT 5;

-- =========================================================
-- (12) Alunos que não concluíram NENHUM curso nos últimos 6 meses
-- =========================================================
SELECT a.id, a.nome, a.email
FROM alunos a
WHERE NOT EXISTS (
  SELECT 1
  FROM matriculas m
  WHERE m.aluno_id = a.id
    AND m.status = 'concluida'
    AND m.data_conclusao >= (CURRENT_DATE - INTERVAL '6 months')
)
ORDER BY a.nome;

-- =========================================================
-- RELATÓRIOS (1.4)
-- =========================================================

-- R1) Dashboard geral
SELECT
  (SELECT COUNT(*) FROM alunos)      AS total_alunos,
  (SELECT COUNT(*) FROM cursos)      AS total_cursos,
  (SELECT COUNT(*) FROM matriculas WHERE status='ativa') AS matriculas_ativas,
  (SELECT ROUND(SUM(valor_pago)::numeric,2)
     FROM matriculas WHERE status <> 'cancelada')        AS receita_total;

-- R2) Cursos com baixa taxa de conclusão (< 30%)
WITH
tot_aulas AS (
  SELECT md.curso_id, COUNT(a.id) AS total
  FROM modulos md JOIN aulas a ON a.modulo_id = md.id
  GROUP BY md.curso_id
),
tot_conc AS (
  SELECT m.curso_id, COUNT(*) FILTER (WHERE p.concluida) AS concluidas
  FROM matriculas m
  JOIN progresso_aulas p ON p.matricula_id = m.id
  GROUP BY m.curso_id
)
SELECT c.titulo,
       COALESCE(ROUND(100.0 * tc.concluidas / NULLIF(ta.total * GREATEST(COUNT(DISTINCT m.id),1),0), 2), 0) AS taxa_perc
FROM cursos c
JOIN tot_aulas ta ON ta.curso_id = c.id
LEFT JOIN matriculas m ON m.curso_id = c.id
LEFT JOIN tot_conc tc ON tc.curso_id = c.id
GROUP BY c.id, c.titulo, ta.total, tc.concluidas
HAVING COALESCE(1.0 * tc.concluidas / NULLIF(ta.total * GREATEST(COUNT(DISTINCT m.id),1),0), 0) < 0.30
ORDER BY taxa_perc ASC;

-- R3) Instrutores mais bem avaliados (média >= 4.5)
SELECT i.nome AS instrutor, ROUND(AVG(av.nota)::numeric,2) AS media, COUNT(*) AS avaliacoes
FROM instrutores i
JOIN cursos c   ON c.instrutor_id = i.id
JOIN avaliacoes av ON av.curso_id = c.id
GROUP BY i.nome
HAVING AVG(av.nota) >= 4.5
ORDER BY media DESC;

-- R4) Categorias mais populares (por # de matrículas)
SELECT cat.nome AS categoria, COUNT(m.*) AS matriculas
FROM categorias cat
JOIN cursos c ON c.categoria_id = cat.id
LEFT JOIN matriculas m ON m.curso_id = c.id
GROUP BY cat.nome
ORDER BY matriculas DESC;

-- R5) Matrículas por mês (ano atual)
SELECT to_char(date_trunc('month', m.data_matricula), 'YYYY-MM') AS mes,
       COUNT(*) AS qtd
FROM matriculas m
WHERE EXTRACT(YEAR FROM m.data_matricula) = EXTRACT(YEAR FROM CURRENT_DATE)
GROUP BY 1
ORDER BY 1;
