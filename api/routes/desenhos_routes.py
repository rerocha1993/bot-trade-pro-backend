# api/routes/desenhos_routes.py
"""
Desenhos da tela Gráfico (linhas, Fibonacci e o resto das ferramentas da TradingView), guardados no servidor para
aparecerem igual no PC e no celular. Um arquivo por moeda em data/desenhos/, mais os modelos (o "Salvar como padrão"
de cada ferramenta) num arquivo só.

O painel manda a lista inteira a cada mudança (como a TradingView salva o layout): o último a gravar vale. O servidor
não interpreta os desenhos, só confere o tamanho e que é uma lista de objetos com id e tipo.
"""
import json
import os
import re
import threading
import time

from fastapi import APIRouter, Body, HTTPException, Query

router = APIRouter()

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PASTA = os.path.join(RAIZ, "data", "desenhos")
ARQ_MODELOS = os.path.join(PASTA, "_modelos.json")
MAX_BYTES = 2_000_000
MAX_DESENHOS = 2000
SIMBOLO_OK = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")

_trava = threading.Lock()


def _arquivo(simbolo: str) -> str:
    if not SIMBOLO_OK.match(simbolo):
        raise HTTPException(400, "símbolo inválido")
    return os.path.join(PASTA, simbolo.replace(":", "__") + ".json")


def _ler(caminho: str, vazio):
    try:
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return vazio
    except (OSError, ValueError):
        return vazio


def _gravar(caminho: str, dados) -> None:
    texto = json.dumps(dados, ensure_ascii=False, separators=(",", ":"))
    if len(texto.encode("utf-8")) > MAX_BYTES:
        raise HTTPException(413, "desenhos demais para guardar")
    os.makedirs(PASTA, exist_ok=True)
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(texto)
    os.replace(tmp, caminho)


def validar_desenhos(lista) -> list:
    """Lista de objetos, cada um com id e tipo em texto curto; o resto é do painel."""
    if not isinstance(lista, list):
        raise HTTPException(422, "esperava uma lista de desenhos")
    if len(lista) > MAX_DESENHOS:
        raise HTTPException(413, f"mais de {MAX_DESENHOS} desenhos numa moeda")
    for d in lista:
        if not isinstance(d, dict) or not isinstance(d.get("id"), str) or not isinstance(d.get("tipo"), str):
            raise HTTPException(422, "cada desenho precisa de id e tipo")
        if len(d["id"]) > 40 or len(d["tipo"]) > 40:
            raise HTTPException(422, "id ou tipo grande demais")
    return lista


@router.get("")
def ler_desenhos(simbolo: str = Query(..., max_length=64)):
    caminho = _arquivo(simbolo)
    with _trava:
        d = _ler(caminho, {"desenhos": [], "atualizado": None})
    return {"simbolo": simbolo, "desenhos": d.get("desenhos", []), "atualizado": d.get("atualizado")}


@router.put("")
def gravar_desenhos(simbolo: str = Query(..., max_length=64), corpo: dict = Body(...)):
    caminho = _arquivo(simbolo)
    lista = validar_desenhos(corpo.get("desenhos"))
    agora = int(time.time() * 1000)
    with _trava:
        if lista:
            _gravar(caminho, {"desenhos": lista, "atualizado": agora})
        elif os.path.exists(caminho):
            os.remove(caminho)
    return {"simbolo": simbolo, "n": len(lista), "atualizado": agora}


@router.get("/modelos")
def ler_modelos():
    with _trava:
        return {"modelos": _ler(ARQ_MODELOS, {})}


@router.put("/modelos")
def gravar_modelos(corpo: dict = Body(...)):
    modelos = corpo.get("modelos")
    if not isinstance(modelos, dict) or not all(isinstance(k, str) and len(k) <= 40 for k in modelos):
        raise HTTPException(422, "esperava {ferramenta: configuração}")
    with _trava:
        _gravar(ARQ_MODELOS, modelos)
    return {"n": len(modelos)}
