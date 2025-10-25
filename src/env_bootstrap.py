#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
env_bootstrap.py
================
Prepara o ambiente para o projeto:
- Garante pip;
- Instala dependências (Faker, psycopg2-binary);
- Se o ambiente for gerenciado (PEP 668), cria um `.venv` local e instala lá;
- (Opcional) Executa outro script (ex.: gerador_dados.py) dentro do venv.

Uso:
  # Apenas preparar o ambiente (cria .venv se necessário)
  python env_bootstrap.py

  # Preparar e rodar o gerador automaticamente (passar args após --)
  python env_bootstrap.py --run ./gerador_dados.py -- --dsn "..." --reset
"""
from __future__ import annotations

import argparse
import importlib
import os
import subprocess
import sys
import venv
from typing import List

DEFAULT_PACKAGES = ["Faker", "psycopg2-binary"]

def ensure_pip(py: str) -> None:
    """Garante que 'pip' esteja disponível no interpretador 'py'."""
    try:
        subprocess.check_call([py, "-m", "pip", "--version"], stdout=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        subprocess.check_call([py, "-m", "ensurepip", "--upgrade"])
        subprocess.check_call([py, "-m", "pip", "install", "--upgrade", "pip"])

def pip_install(py: str, packages: List[str]) -> None:
    """Instala 'packages' com pip do interpretador 'py'."""
    ensure_pip(py)
    subprocess.check_call([py, "-m", "pip", "install", "--upgrade"] + packages)

def make_venv(venv_dir: str) -> str:
    """Cria venv em 'venv_dir' (se não existir) e retorna caminho do python dentro do venv."""
    if not os.path.exists(venv_dir):
        print(f">> Criando venv em: {venv_dir}")
        venv.EnvBuilder(with_pip=True).create(venv_dir)
    bin_dir = "Scripts" if os.name == "nt" else "bin"
    py = os.path.join(venv_dir, bin_dir, "python")
    return py

def install_packages(packages: List[str], venv_dir: str = ".venv") -> str:
    """
    Tenta instalar pacotes no Python do sistema; se falhar por PEP 668,
    cria .venv e instala lá. Retorna o caminho do python (sistema ou venv).
    """
    py = sys.executable
    try:
        pip_install(py, packages)
        print(">> Dependências instaladas no Python do sistema.")
        return py
    except subprocess.CalledProcessError as e:
        if "externally-managed-environment" in str(e):
            print(">> Ambiente gerenciado (PEP 668). Usando venv local.")
            vpy = make_venv(venv_dir)
            pip_install(vpy, packages)
            print(f">> Dependências instaladas no venv: {venv_dir}")
            return vpy
        raise

def main():
    parser = argparse.ArgumentParser(description="Bootstrap de dependências e execução opcional")
    parser.add_argument("--venv", default=".venv", help="Diretório do venv (default: .venv)")
    parser.add_argument("--run", metavar="SCRIPT", help="Script a executar após instalar deps (ex.: ./gerador_dados.py)")
    parser.add_argument("--packages", nargs="*", default=DEFAULT_PACKAGES, help="Lista de pacotes a instalar")
    # Tudo após '--' será repassado ao script em --run
    if "--" in sys.argv:
        idx = sys.argv.index("--")
        args, passthrough = parser.parse_args(sys.argv[1:idx]), sys.argv[idx + 1:]
    else:
        args, passthrough = parser.parse_args(), []

    py = install_packages(args.packages, venv_dir=args.venv)

    if args.run:
        print(f">> Executando: {args.run} {' '.join(passthrough)}")
        os.execv(py, [py, args.run] + passthrough)
    else:
        print("✅ Ambiente pronto.")
        print("Dica: para rodar o gerador agora:")
        if py.endswith("python") and args.venv in py:
            print(f"  {py} ./gerador_dados.py --dsn \"dbname=edutech_dev user=postgres password=SUA_SENHA hostaddr=127.0.0.1 port=5432\" --reset")
        else:
            print("  python ./gerador_dados.py --dsn \"dbname=edutech_dev user=postgres password=SUA_SENHA hostaddr=127.0.0.1 port=5432\" --reset")

if __name__ == "__main__":
    main()
