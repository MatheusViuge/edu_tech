#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gerador_dados.py
================
Popula o banco **edutech** (PostgreSQL) com dados realistas usando Faker.

Este arquivo **não** instala libs; use `env_bootstrap.py` antes (ou venv/pacman).
- Conexão via DSN (Data Source Name).
- Força TCP com `hostaddr=127.0.0.1` quando host é localhost (evita "peer authentication").
- Respeita FKs/ENUMs/constraints (como no DDL que montamos).

Uso típico:
  python env_bootstrap.py --run ./gerador_dados.py -- --dsn "dbname=edutech_dev user=postgres password=*** host=localhost port=5432" --reset
"""
from __future__ import annotations

import argparse
import os
import random
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Sequence, Tuple

from faker import Faker          # depende de env_bootstrap.py
import psycopg2                  # depende de env_bootstrap.py

# -------------------- Utilitários --------------------
faker = Faker("pt_BR")
_rand = random.Random()

def money(v: float) -> Decimal:
    """Converte float em Decimal(2 casas) com arredondamento comercial."""
    return Decimal(v).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def dias_atras(max_dias: int) -> datetime:
    """Retorna um datetime entre agora e (agora - max_dias)."""
    return datetime.now() - timedelta(days=_rand.randint(0, max_dias))

def mask_password(dsn: str) -> str:
    """Oculta a senha ao exibir o DSN no console."""
    return re.sub(r"(password=)[^\s]+", r"\1******", dsn)

def normalize_dsn(dsn: str) -> str:
    """
    Garante conexão via TCP:
    - Se não houver 'hostaddr=' e 'host' for vazio/localhost, anexa 'hostaddr=127.0.0.1'.
    """
    kv = dict(re.findall(r"(\w+)=([^\s]+)", dsn))
    host = kv.get("host", "").lower()
    has_hostaddr = "hostaddr" in kv
    if not has_hostaddr and (host == "" or host == "localhost"):
        dsn = (dsn.strip() + " hostaddr=127.0.0.1").strip()
    return dsn

# -------------------- Inserções --------------------
def criar_categorias(cur, n: int) -> List[int]:
    """Cria N categorias (>=5 recomendado) com nomes/descrições coerentes."""
    base = [
        ("Programação", "Linguagens e paradigmas"),
        ("Dados", "SQL, modelagem, análise"),
        ("DevOps", "Infra, CI/CD, cloud"),
        ("Frontend", "UI/UX e frameworks"),
        ("Backend", "APIs e arquitetura"),
        ("Carreira", "Soft skills e práticas"),
        ("Segurança", "AppSec e boas práticas"),
        ("Mobile", "iOS/Android e cross-platform"),
    ]
    _rand.shuffle(base)
    itens = base[: max(n, 5)]
    ids: List[int] = []
    for nome, desc in itens:
        cur.execute(
            "INSERT INTO edutech.categorias (nome, descricao) VALUES (%s, %s) RETURNING id",
            (nome, desc),
        )
        ids.append(cur.fetchone()[0])
    return ids

def criar_instrutores(cur, n: int) -> List[int]:
    """Cria N instrutores com nome, e-mail único, especialidade e biografia."""
    emails: set[str] = set()
    ids: List[int] = []
    especialidades = [
        "SQL & Dados", "Backend", "DevOps", "Frontend", "PostgreSQL",
        "Python & Dados", "Arquitetura", "Cloud", "Qualidade", "Segurança",
    ]
    for _ in range(n):
        nome = faker.name()
        email = faker.unique.email().lower()
        while email in emails:
            email = faker.unique.email().lower()
        emails.add(email)
        bio = faker.text(max_nb_chars=180)
        cur.execute(
            """
            INSERT INTO edutech.instrutores (nome, email, especialidade, biografia)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (nome, email, _rand.choice(especialidades), bio),
        )
        ids.append(cur.fetchone()[0])
    return ids

def criar_cursos(cur, n: int, categoria_ids: Sequence[int], instrutor_ids: Sequence[int]) -> List[int]:
    """Cria N cursos, variando preço, nível e data de criação."""
    ids: List[int] = []
    for i in range(1, n + 1):
        titulo = f"{_rand.choice(['Curso', 'Formação', 'Trilha'])} {faker.word().capitalize()} {i}"
        descricao = faker.sentence(nb_words=10)
        preco = money(49.9 + _rand.random() * 450)   # 49.90..499.90
        carga_horaria = _rand.randint(8, 48)
        nivel = _rand.choice(["iniciante", "intermediario", "avancado"])
        cur.execute(
            """
            INSERT INTO edutech.cursos
              (titulo, descricao, categoria_id, instrutor_id, preco, carga_horaria, nivel, data_criacao)
            VALUES (%s, %s, %s, %s, %s, %s, %s::nivel_enum, %s)
            RETURNING id
            """,
            (
                titulo, descricao, _rand.choice(categoria_ids), _rand.choice(instrutor_ids),
                preco, carga_horaria, nivel, dias_atras(365),
            ),
        )
        ids.append(cur.fetchone()[0])
    return ids

def criar_modulos_e_aulas(
    cur, curso_ids: Sequence[int], min_mod: int = 3, max_mod: int = 5, min_aula: int = 3, max_aula: int = 6,
) -> Tuple[Dict[int, List[int]], Dict[int, List[Tuple[int, int]]]]:
    """Cria módulos (ordem 1..N) e aulas (ordem 1..K) por curso."""
    modulo_ids_por_curso: Dict[int, List[int]] = {}
    aulas_por_curso: Dict[int, List[Tuple[int, int]]] = {}
    for curso_id in curso_ids:
        q_mod = _rand.randint(min_mod, max_mod)
        modulo_ids: List[int] = []
        for ordem_m in range(1, q_mod + 1):
            titulo_m = f"Módulo {ordem_m} — {faker.word().capitalize()}"
            desc_m = faker.sentence(nb_words=8)
            cur.execute(
                """INSERT INTO edutech.modulos (curso_id, titulo, ordem, descricao)
                   VALUES (%s, %s, %s, %s) RETURNING id""",
                (curso_id, titulo_m, ordem_m, desc_m),
            )
            modulo_id = cur.fetchone()[0]
            modulo_ids.append(modulo_id)

            q_aulas = _rand.randint(min_aula, max_aula)
            for ordem_a in range(1, q_aulas + 1):
                titulo_a = f"Aula {ordem_m}.{ordem_a} — {faker.word().capitalize()}"
                duracao = _rand.randint(5, 45)
                tipo = _rand.choice(["video", "texto", "quiz"])
                cur.execute(
                    """INSERT INTO edutech.aulas (modulo_id, titulo, ordem, duracao_minutos, tipo)
                       VALUES (%s, %s, %s, %s, %s::aula_tipo_enum) RETURNING id""",
                    (modulo_id, titulo_a, ordem_a, duracao, tipo),
                )
                aula_id = cur.fetchone()[0]
                aulas_por_curso.setdefault(curso_id, []).append((aula_id, duracao))
        modulo_ids_por_curso[curso_id] = modulo_ids
    return modulo_ids_por_curso, aulas_por_curso

def criar_alunos(cur, n: int) -> List[int]:
    """Cria N alunos com e-mail único e datas coerentes."""
    emails: set[str] = set()
    ids: List[int] = []
    hoje = date.today()
    for _ in range(n):
        nome = faker.name()
        email = faker.unique.email().lower()
        while email in emails:
            email = faker.unique.email().lower()
        emails.add(email)
        nasc = hoje - timedelta(days=_rand.randint(18 * 365, 45 * 365))
        cadastro = dias_atras(730)
        cur.execute(
            """INSERT INTO edutech.alunos (nome, email, data_nascimento, data_cadastro)
               VALUES (%s, %s, %s, %s) RETURNING id""",
            (nome, email, nasc, cadastro),
        )
        ids.append(cur.fetchone()[0])
    return ids

def criar_matriculas(cur, alunos_ids: Sequence[int], curso_ids: Sequence[int], qtd: int = 80) -> List[int]:
    """Cria matrículas aluno×curso (únicas), com status variados e valor pago coerente."""
    cur.execute("SELECT id, preco FROM edutech.cursos")
    precos: Dict[int, Decimal] = {cid: Decimal(str(p)) for cid, p in cur.fetchall()}
    pares: set[Tuple[int, int]] = set()
    ids: List[int] = []
    tentativas_max = qtd * 6
    while len(ids) < qtd and tentativas_max > 0:
        tentativas_max -= 1
        aluno = _rand.choice(alunos_ids)
        curso = _rand.choice(curso_ids)
        if (aluno, curso) in pares:
            continue
        pares.add((aluno, curso))
        data_m = (datetime.now().date() - timedelta(days=_rand.randint(0, 240)))
        r = _rand.random()
        if r < 0.45:
            status = "concluida"; data_c = data_m + timedelta(days=_rand.randint(7, 120))
        elif r < 0.80:
            status = "ativa"; data_c = None
        else:
            status = "cancelada"; data_c = None
        desconto = Decimal(str(_rand.uniform(0, 0.2))).quantize(Decimal("0.00"))
        valor_pago = (precos[curso] * (Decimal("1.00") - desconto)).quantize(Decimal("0.01"))
        cur.execute(
            """INSERT INTO edutech.matriculas
                 (aluno_id, curso_id, data_matricula, data_conclusao, status, valor_pago)
               VALUES (%s, %s, %s, %s, %s::status_matricula_enum, %s) RETURNING id""",
            (aluno, curso, data_m, data_c, status, valor_pago),
        )
        ids.append(cur.fetchone()[0])
    return ids

def criar_progresso(cur, matricula_ids: Sequence[int], aulas_por_curso: Dict[int, List[Tuple[int, int]]]) -> int:
    """Cria progresso de aulas para cada matrícula (tempo ≤ duração, conclui quando tempo==duração e não cancelada)."""
    cur.execute("SELECT id, curso_id, data_matricula, status FROM edutech.matriculas")
    info = {m_id: (curso_id, data_m, status) for m_id, curso_id, data_m, status in cur.fetchall()}
    total_rows = 0
    for m_id in matricula_ids:
        curso_id, data_m, status = info[m_id]
        aulas = aulas_por_curso.get(curso_id, [])
        if not aulas:
            continue
        k = _rand.randint(3, min(10, len(aulas)))
        for aula_id, dur in _rand.sample(aulas, k):
            t = _rand.randint(0, int(dur))
            concluida = (t == int(dur)) and (status != "cancelada")
            data_c = (datetime.combine(data_m, datetime.min.time()) + timedelta(days=_rand.randint(1, 90))) if concluida else None
            cur.execute(
                """INSERT INTO edutech.progresso_aulas
                     (matricula_id, aula_id, concluida, data_conclusao, tempo_assistido_minutos)
                   VALUES (%s, %s, %s, %s, %s)""",
                (m_id, aula_id, concluida, data_c, t),
            )
            total_rows += 1
    return total_rows

def criar_avaliacoes(cur) -> int:
    """Cria 1 avaliação por matrícula concluída (nota 1..5)."""
    cur.execute("""SELECT id, curso_id, data_conclusao FROM edutech.matriculas WHERE status='concluida'""")
    concluidas = cur.fetchall()
    inseridas = 0
    for mat_id, curso_id, data_c in concluidas:
        nota = _rand.randint(1, 5)
        data_av = (data_c or datetime.now().date()) + timedelta(days=_rand.randint(0, 60))
        cur.execute(
            """INSERT INTO edutech.avaliacoes (matricula_id, curso_id, nota, comentario, data_avaliacao)
               VALUES (%s, %s, %s, %s, %s) ON CONFLICT (matricula_id) DO NOTHING""",
            (mat_id, curso_id, nota, faker.sentence(nb_words=8), data_av),
        )
        inseridas += cur.rowcount
    return inseridas

# -------------------- Orquestração/CLI --------------------
def popular(dsn: str, args: argparse.Namespace) -> None:
    """Executa toda a pipeline de população numa única transação."""
    import psycopg2  # local import para deixar claro o contrato de dependência
    conn = psycopg2.connect(dsn)
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            cur.execute("SET search_path TO edutech, public;")
            if args.reset:
                print(">> Limpando tabelas (TRUNCATE … RESTART IDENTITY CASCADE)")
                cur.execute("""
                    TRUNCATE edutech.avaliacoes, edutech.progresso_aulas, edutech.matriculas,
                             edutech.aulas, edutech.modulos, edutech.cursos,
                             edutech.categorias, edutech.instrutores, edutech.alunos
                    RESTART IDENTITY CASCADE;
                """)
            print(">> Criando categorias…"); cat_ids = criar_categorias(cur, args.categorias)
            print(">> Criando instrutores…"); inst_ids = criar_instrutores(cur, args.instrutores)
            print(">> Criando cursos…");     curso_ids = criar_cursos(cur, args.cursos, cat_ids, inst_ids)
            print(">> Criando módulos e aulas…")
            _, aulas_por_curso = criar_modulos_e_aulas(cur, curso_ids, args.min_modulos, args.max_modulos, args.min_aulas, args.max_aulas)
            total_aulas = sum(len(v) for v in aulas_por_curso.values()); print(f"   - {total_aulas} aulas")
            print(">> Criando alunos…");     aluno_ids = criar_alunos(cur, args.alunos)
            print(">> Criando matrículas…"); mat_ids = criar_matriculas(cur, aluno_ids, curso_ids, args.matriculas)
            print(">> Criando progresso…");  prog_rows = criar_progresso(cur, mat_ids, aulas_por_curso); print(f"   - {prog_rows} registros")
            print(">> Criando avaliações…"); av_count = criar_avaliacoes(cur); print(f"   - {av_count} avaliações")
        conn.commit()
        print("\n✅ População concluída com sucesso!")
    except Exception as e:
        conn.rollback()
        print("\n💥 ERRO — transação revertida:"); print(e); raise
    finally:
        conn.close()

def parse_args() -> argparse.Namespace:
    """Lê argumentos de CLI (usa env PG* como default) e força TCP no DSN."""
    p = argparse.ArgumentParser(description="População do banco edutech com Faker")
    host = os.getenv("PGHOST", "localhost")
    hostaddr = os.getenv("PGHOSTADDR", "127.0.0.1")
    port = os.getenv("PGPORT", "5432")
    db = os.getenv("PGDATABASE", "edutech_dev")
    user = os.getenv("PGUSER", "postgres")
    pwd = os.getenv("PGPASSWORD", "")
    default_dsn = f"dbname={db} user={user} password={pwd} host={host} hostaddr={hostaddr} port={port}"
    p.add_argument("--dsn", default=os.getenv("PG_DSN") or default_dsn,
                   help="DSN (ex.: 'dbname=edutech_dev user=postgres password=... host=localhost hostaddr=127.0.0.1 port=5432')")
    p.add_argument("--reset", action="store_true", help="Apaga dados existentes antes de popular")
    p.add_argument("--categorias", type=int, default=6)
    p.add_argument("--instrutores", type=int, default=10)
    p.add_argument("--cursos", type=int, default=20)
    p.add_argument("--alunos", type=int, default=30)
    p.add_argument("--matriculas", type=int, default=80)
    p.add_argument("--min-modulos", type=int, default=3)
    p.add_argument("--max-modulos", type=int, default=5)
    p.add_argument("--min-aulas", type=int, default=3)
    p.add_argument("--max-aulas", type=int, default=6)
    return p.parse_args()

if __name__ == "__main__":
    args = parse_args()
    dsn = normalize_dsn(args.dsn)
    print("Conectando com DSN:", mask_password(dsn))
    popular(dsn, args)
