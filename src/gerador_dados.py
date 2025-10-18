#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gerador_dados.py
================

Popula o banco **edutech** (PostgreSQL) com dados realistas usando **Faker**,
seguindo as regras do mini-projeto.

Destaques:
- Garante dependências em tempo de execução (Faker, psycopg2-binary).
  *Se o ambiente for gerenciado (PEP 668), cria um `.venv` local e reexecuta.*
- Conecta via **DSN (Data Source Name)** — *string de conexão* (ex.: "dbname=... user=...").
- **Força TCP** por padrão com `hostaddr=127.0.0.1` para evitar "peer authentication".
- Insere categorias, instrutores, cursos, módulos, aulas, alunos, matrículas,
  progresso e avaliações, respeitando FKs/ENUMs/constraints do DDL.

Uso:
    python gerador_dados.py --dsn "dbname=edutech_dev user=postgres password=*** host=localhost port=5432" --reset
"""

from __future__ import annotations

import argparse
import importlib
import os
import random
import re
import subprocess
import sys
import venv
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Sequence, Tuple

# ---------------------------------------------------------------------
# Auto-instalação de dependências (com fallback para venv se PEP 668)
# ---------------------------------------------------------------------
def _ensure_pip() -> None:
    """Garante que `pip` esteja disponível no Python atual."""
    try:
        importlib.import_module("pip")  # noqa: F401
        return
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "ensurepip", "--upgrade"])
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])


def _install_and_import(module: str, pip_name: str | None = None) -> None:
    """
    Garante que um módulo esteja importável. Se não estiver, tenta instalar.
    Se o ambiente for gerenciado (PEP 668), cria `.venv` local e reexecuta.

    Args:
        module: nome do módulo para importar (ex.: "faker").
        pip_name: nome do pacote no pip (ex.: "Faker"). Se None, usa `module`.
    """
    try:
        importlib.import_module(module)
        return
    except ImportError:
        pkg = pip_name or module
        try:
            _ensure_pip()
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])
        except subprocess.CalledProcessError as e:
            # Ambiente gerenciado (PEP 668)? Cria .venv e reexecuta no venv
            if "externally-managed-environment" in str(e):
                base_dir = os.path.dirname(os.path.abspath(__file__))
                venv_dir = os.path.join(base_dir, ".venv")
                print(">> Ambiente gerenciado (PEP 668). Criando venv em:", venv_dir)
                if not os.path.exists(venv_dir):
                    venv.EnvBuilder(with_pip=True).create(venv_dir)
                py = os.path.join(venv_dir, "bin", "python")
                # instala dependências no venv
                subprocess.check_call([py, "-m", "pip", "install", "--upgrade", "pip"])
                subprocess.check_call([py, "-m", "pip", "install", "Faker", "psycopg2-binary"])
                # reexecuta este script dentro do venv, mantendo os args
                os.execv(py, [py, __file__] + sys.argv[1:])
            else:
                raise
        importlib.import_module(module)


# garante Faker e psycopg2 disponíveis (no sistema ou no .venv)
_install_and_import("faker", "Faker")
_install_and_import("psycopg2", "psycopg2-binary")

from faker import Faker  # type: ignore
import psycopg2  # type: ignore

# ---------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------
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
    - Se não houver 'hostaddr=' e 'host' estiver vazio ou for 'localhost',
      anexa 'hostaddr=127.0.0.1' ao DSN.
    """
    kv = dict(re.findall(r"(\w+)=([^\s]+)", dsn))
    host = kv.get("host", "").lower()
    has_hostaddr = "hostaddr" in kv
    if not has_hostaddr and (host == "" or host == "localhost"):
        dsn = (dsn.strip() + " hostaddr=127.0.0.1").strip()
    return dsn

# ---------------------------------------------------------------------
# Inserções por entidade
# ---------------------------------------------------------------------
def criar_categorias(cur, n: int) -> List[int]:
    """
    Cria N categorias (>=5 recomendado) com nomes/descrições coerentes.

    Regras:
        - Usa base fixa de nomes para evitar colisão de UNIQUE.
        - Garante ao menos 5 categorias mesmo que N seja menor.
    """
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
    """
    Cria N instrutores com nome, e-mail único, especialidade e biografia.
    """
    emails: set[str] = set()
    ids: List[int] = []
    especialidades = [
        "SQL & Dados",
        "Backend",
        "DevOps",
        "Frontend",
        "PostgreSQL",
        "Python & Dados",
        "Arquitetura",
        "Cloud",
        "Qualidade",
        "Segurança",
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


def criar_cursos(
    cur,
    n: int,
    categoria_ids: Sequence[int],
    instrutor_ids: Sequence[int],
) -> List[int]:
    """
    Cria N cursos distribuindo categoria/instrutor e variando preço/nível.
    """
    ids: List[int] = []
    for i in range(1, n + 1):
        titulo = f"{_rand.choice(['Curso', 'Formação', 'Trilha'])} {faker.word().capitalize()} {i}"
        descricao = faker.sentence(nb_words=10)
        preco = money(49.9 + _rand.random() * 450)   # 49.90..499.90
        carga_horaria = _rand.randint(8, 48)         # horas
        nivel = _rand.choice(["iniciante", "intermediario", "avancado"])
        cur.execute(
            """
            INSERT INTO edutech.cursos
              (titulo, descricao, categoria_id, instrutor_id, preco, carga_horaria, nivel, data_criacao)
            VALUES (%s, %s, %s, %s, %s, %s, %s::nivel_enum, %s)
            RETURNING id
            """,
            (
                titulo,
                descricao,
                _rand.choice(categoria_ids),
                _rand.choice(instrutor_ids),
                preco,
                carga_horaria,
                nivel,
                dias_atras(365),
            ),
        )
        ids.append(cur.fetchone()[0])
    return ids


def criar_modulos_e_aulas(
    cur,
    curso_ids: Sequence[int],
    min_mod: int = 3,
    max_mod: int = 5,
    min_aula: int = 3,
    max_aula: int = 6,
) -> Tuple[Dict[int, List[int]], Dict[int, List[Tuple[int, int]]]]:
    """
    Cria módulos e aulas para cada curso.
    Retorna:
        - mapa curso -> [modulo_ids]
        - mapa curso -> [(aula_id, duracao_minutos)]
    """
    modulo_ids_por_curso: Dict[int, List[int]] = {}
    aulas_por_curso: Dict[int, List[Tuple[int, int]]] = {}

    for curso_id in curso_ids:
        q_mod = _rand.randint(min_mod, max_mod)
        modulo_ids: List[int] = []
        for ordem_m in range(1, q_mod + 1):
            titulo_m = f"Módulo {ordem_m} — {faker.word().capitalize()}"
            desc_m = faker.sentence(nb_words=8)
            cur.execute(
                """
                INSERT INTO edutech.modulos (curso_id, titulo, ordem, descricao)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
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
                    """
                    INSERT INTO edutech.aulas (modulo_id, titulo, ordem, duracao_minutos, tipo)
                    VALUES (%s, %s, %s, %s, %s::aula_tipo_enum)
                    RETURNING id
                    """,
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
            """
            INSERT INTO edutech.alunos (nome, email, data_nascimento, data_cadastro)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (nome, email, nasc, cadastro),
        )
        ids.append(cur.fetchone()[0])

    return ids


def criar_matriculas(
    cur,
    alunos_ids: Sequence[int],
    curso_ids: Sequence[int],
    qtd: int = 80,
) -> List[int]:
    """
    Cria matrículas únicas aluno×curso com status distribuído e valor pago coerente.
    """
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
            status = "concluida"
            data_c = data_m + timedelta(days=_rand.randint(7, 120))
        elif r < 0.80:
            status = "ativa"
            data_c = None
        else:
            status = "cancelada"
            data_c = None

        desconto = Decimal(str(_rand.uniform(0, 0.2))).quantize(Decimal("0.00"))
        valor_pago = (precos[curso] * (Decimal("1.00") - desconto)).quantize(Decimal("0.01"))

        cur.execute(
            """
            INSERT INTO edutech.matriculas
              (aluno_id, curso_id, data_matricula, data_conclusao, status, valor_pago)
            VALUES (%s, %s, %s, %s, %s::status_matricula_enum, %s)
            RETURNING id
            """,
            (aluno, curso, data_m, data_c, status, valor_pago),
        )
        ids.append(cur.fetchone()[0])

    return ids


def criar_progresso(
    cur,
    matricula_ids: Sequence[int],
    aulas_por_curso: Dict[int, List[Tuple[int, int]]],
) -> int:
    """
    Cria progresso de aulas para cada matrícula, respeitando duração e regras:
    - tempo_assistido ∈ [0, duracao];
    - concluída quando tempo == duração e matrícula não cancelada.
    """
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
            data_c = (
                datetime.combine(data_m, datetime.min.time()) + timedelta(days=_rand.randint(1, 90))
                if concluida
                else None
            )
            cur.execute(
                """
                INSERT INTO edutech.progresso_aulas
                  (matricula_id, aula_id, concluida, data_conclusao, tempo_assistido_minutos)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (m_id, aula_id, concluida, data_c, t),
            )
            total_rows += 1

    return total_rows


def criar_avaliacoes(cur) -> int:
    """
    Cria uma avaliação por matrícula **concluída** (nota 1..5).
    Trigger do DDL garante coerência do curso.
    """
    cur.execute(
        """
        SELECT id, curso_id, data_conclusao
        FROM edutech.matriculas
        WHERE status = 'concluida'
        """
    )
    concluidas = cur.fetchall()
    inseridas = 0
    for mat_id, curso_id, data_c in concluidas:
        nota = _rand.randint(1, 5)
        data_av = (data_c or datetime.now().date()) + timedelta(days=_rand.randint(0, 60))
        cur.execute(
            """
            INSERT INTO edutech.avaliacoes (matricula_id, curso_id, nota, comentario, data_avaliacao)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (matricula_id) DO NOTHING
            """,
            (mat_id, curso_id, nota, faker.sentence(nb_words=8), data_av),
        )
        inseridas += cur.rowcount
    return inseridas

# ---------------------------------------------------------------------
# Orquestração / CLI
# ---------------------------------------------------------------------
def popular(dsn: str, args: argparse.Namespace) -> None:
    """
    Executa a pipeline de população do banco edutech numa única transação.
    """
    conn = psycopg2.connect(dsn)
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            cur.execute("SET search_path TO edutech, public;")

            if args.reset:
                print(">> Limpando tabelas (TRUNCATE … RESTART IDENTITY CASCADE)")
                cur.execute(
                    """
                    TRUNCATE edutech.avaliacoes, edutech.progresso_aulas, edutech.matriculas,
                             edutech.aulas, edutech.modulos, edutech.cursos,
                             edutech.categorias, edutech.instrutores, edutech.alunos
                    RESTART IDENTITY CASCADE;
                    """
                )

            print(">> Criando categorias…")
            cat_ids = criar_categorias(cur, args.categorias)
            print(f"   - {len(cat_ids)} categorias")

            print(">> Criando instrutores…")
            inst_ids = criar_instrutores(cur, args.instrutores)
            print(f"   - {len(inst_ids)} instrutores")

            print(">> Criando cursos…")
            curso_ids = criar_cursos(cur, args.cursos, cat_ids, inst_ids)
            print(f"   - {len(curso_ids)} cursos")

            print(">> Criando módulos e aulas…")
            _, aulas_por_curso = criar_modulos_e_aulas(
                cur, curso_ids, args.min_modulos, args.max_modulos, args.min_aulas, args.max_aulas
            )
            total_aulas = sum(len(v) for v in aulas_por_curso.values())
            print(f"   - {total_aulas} aulas")

            print(">> Criando alunos…")
            aluno_ids = criar_alunos(cur, args.alunos)
            print(f"   - {len(aluno_ids)} alunos")

            print(">> Criando matrículas…")
            mat_ids = criar_matriculas(cur, aluno_ids, curso_ids, args.matriculas)
            print(f"   - {len(mat_ids)} matrículas")

            print(">> Criando progresso de aulas…")
            prog_rows = criar_progresso(cur, mat_ids, aulas_por_curso)
            print(f"   - {prog_rows} registros de progresso")

            print(">> Criando avaliações…")
            av_count = criar_avaliacoes(cur)
            print(f"   - {av_count} avaliações")

        conn.commit()
        print("\n✅ População concluída com sucesso!")
    except Exception as e:
        conn.rollback()
        print("\n💥 ERRO — transação revertida:")
        print(e)
        raise
    finally:
        conn.close()


def parse_args() -> argparse.Namespace:
    """
    Lê os argumentos de CLI.
    Por padrão, força TCP adicionando `hostaddr=127.0.0.1` ao DSN.
    """
    p = argparse.ArgumentParser(description="População do banco edutech com Faker")

    host = os.getenv("PGHOST", "localhost")
    hostaddr = os.getenv("PGHOSTADDR", "127.0.0.1")
    port = os.getenv("PGPORT", "5432")
    db = os.getenv("PGDATABASE", "edutech_dev")
    user = os.getenv("PGUSER", "postgres")
    pwd = os.getenv("PGPASSWORD", "123456")

    default_dsn = f"dbname={db} user={user} password={pwd} host={host} hostaddr={hostaddr} port={port}"

    p.add_argument(
        "--dsn",
        default=os.getenv("PG_DSN") or default_dsn,
        help=("DSN de conexão (ex.: "
              "'dbname=edutech_dev user=postgres password=... host=localhost hostaddr=127.0.0.1 port=5432')"),
    )
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
