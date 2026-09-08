"""Compatibilidade: cria/atualiza as tabelas (equivale a scripts/setup_db.py)."""
import runpy

runpy.run_path("scripts/setup_db.py", run_name="__main__")
