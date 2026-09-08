# core/orquestrador/__init__.py
"""Camada 2 da arquitetura: o orquestrador que lê como um trader humano e emite o PLANO DE MERCADO do par."""
from core.orquestrador.plano import MODOS, montar_plano

__all__ = ["montar_plano", "MODOS"]
