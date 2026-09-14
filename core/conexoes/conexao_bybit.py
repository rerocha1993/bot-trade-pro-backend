# core/conexoes/conexao_bybit.py
"""
Conector Bybit (API v5 via ccxt) para contratos perpétuos USDT (categoria "linear").

Modos de execução:
    simulador -> usa SOMENTE dados públicos da mainnet; nunca envia ordens (paper trading).
    demo      -> DEMO TRADING da conta oficial: dinheiro fictício, mas infraestrutura real (api-demo.bybit.com).
                 Chaves BYBIT_API_KEY_DEMO / BYBIT_SECRET_KEY_DEMO, criadas dentro de bybit.com com o modo
                 Demo Trading ligado. É o caminho para quem o testnet bloqueia por jurisdição: o testnet é um
                 cadastro separado, sem o KYC nem o status da conta oficial, e por isso responde 10024 por IP.
    testnet   -> chaves BYBIT_API_KEY_TESTNET / BYBIT_SECRET_KEY_TESTNET, ordens vão para testnet.bybit.com.
    real      -> chaves BYBIT_API_KEY_REAL / BYBIT_SECRET_KEY_REAL, ordens vão para a mainnet.

SUBCONTAS: na Bybit cada símbolo tem UMA posição por conta. Dois robôs no mesmo par dentro da mesma conta se
atrapalham (em one-way uma ordem fecha a outra; em hedge as duas viram uma posição só, com um stop só). Por isso
cada robô opera na sua própria subconta, com chave própria:

    BYBIT_SUB_<NOME>_API_KEY_TESTNET / BYBIT_SUB_<NOME>_SECRET_KEY_TESTNET
    BYBIT_SUB_<NOME>_API_KEY_REAL    / BYBIT_SUB_<NOME>_SECRET_KEY_REAL

<NOME> é o campo `subconta` do robô em maiúsculas, com qualquer caractere fora de A-Z0-9 virando "_"
(ex.: subconta "scalp-fluxo" -> BYBIT_SUB_SCALP_FLUXO_API_KEY_TESTNET). A subconta "principal" (ou vazia) usa as
chaves da conta principal. Se a subconta estiver configurada no robô mas a chave não existir, o conector FALHA em
vez de cair para a conta principal: operar na conta errada é pior que não operar.

Símbolos: aceita "BTCUSDT", "BTC/USDT" ou "BTC/USDT:USDT" e converte para o formato ccxt
correto da categoria ("BTC/USDT:USDT" para linear, "BTC/USDT" para spot).
"""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional

import ccxt
from dotenv import load_dotenv

from core.utils_indicadores import (
    arredondar_para_step,
    normalizar_timeframe,
    ultimo_candle_fechado,
)

load_dotenv()
logger = logging.getLogger(__name__)

MODOS_VALIDOS = ("simulador", "demo", "testnet", "real")
MODOS_COM_ORDEM = ("demo", "testnet", "real")
SUBCONTA_PRINCIPAL = ("principal", "main", "", None)


def _slug(subconta: str) -> str:
    """'scalp-fluxo' -> 'SCALP_FLUXO' (nome usado nas variáveis de ambiente)."""
    return "".join(c if c.isalnum() else "_" for c in str(subconta).strip().upper()).strip("_")


SUFIXO_POR_MODO = {"real": "REAL", "demo": "DEMO", "testnet": "TESTNET"}


def nomes_variaveis(subconta: Optional[str], modo: str) -> tuple:
    """
    Nomes das variáveis de ambiente esperadas para essa subconta e modo.

    Uma OUTRA conta principal (com as subcontas dela) entra como grupo: "tradeiros:scalp" -> BYBIT_SUB_SCALP_API_KEY_DEMO_TRADEIROS
    e "tradeiros:principal" -> BYBIT_API_KEY_DEMO_TRADEIROS (as chaves dos robôs do portal Tradeiros).
    """
    if subconta is not None and ":" in str(subconta):
        grupo, sub = str(subconta).split(":", 1)
        k, s = nomes_variaveis(sub, modo)
        return (f"{k}_{_slug(grupo)}", f"{s}_{_slug(grupo)}")
    sufixo = SUFIXO_POR_MODO.get(modo, "TESTNET")
    if subconta is None or str(subconta).strip().lower() in SUBCONTA_PRINCIPAL:
        return (f"BYBIT_API_KEY_{sufixo}", f"BYBIT_SECRET_KEY_{sufixo}")
    s = _slug(subconta)
    return (f"BYBIT_SUB_{s}_API_KEY_{sufixo}", f"BYBIT_SUB_{s}_SECRET_KEY_{sufixo}")


def credenciais(subconta: Optional[str], modo: str) -> tuple:
    """(api_key, api_secret) da subconta, ou (None, None) se não estiverem no ambiente."""
    k, s = nomes_variaveis(subconta, modo)
    return (os.getenv(k), os.getenv(s))


def subcontas_configuradas(modo: str = "testnet") -> List[Dict[str, Any]]:
    """Quais subcontas têm chave no ambiente (para diagnóstico no painel; nunca devolve o valor da chave)."""
    sufixo = SUFIXO_POR_MODO.get(modo, "TESTNET")
    prefixo, fim = "BYBIT_SUB_", f"_API_KEY_{sufixo}"
    out: List[Dict[str, Any]] = []
    principal_k, principal_s = credenciais("principal", modo)
    out.append({"subconta": "principal", "configurada": bool(principal_k and principal_s),
                "variavel": f"BYBIT_API_KEY_{sufixo}"})
    for nome in os.environ:
        if nome.startswith(prefixo) and nome.endswith(fim):
            slug = nome[len(prefixo):-len(fim)]
            k, s = os.getenv(nome), os.getenv(f"{prefixo}{slug}_SECRET_KEY_{sufixo}")
            out.append({"subconta": slug.lower(), "configurada": bool(k and s), "variavel": nome})
    return out


# LIMITADOR DE UMA VEZ SO PARA O PROCESSO INTEIRO.
#
# O `enableRateLimit` da ccxt e por INSTANCIA e nao e seguro entre threads: cada robo tem o seu conector, os
# quatro rodam em threads separadas, e todos saem pelo MESMO IP. Cada um respeitava um limite proprio e
# somados estouravam o da corretora -- o 10006 aparecia em rajada nas viradas de 15 minutos e de hora, que e
# quando os robos fazem a decisao pesada ao mesmo tempo.
#
# Aqui o espacamento e global: nao importa quantos conectores ou threads existam, as LEITURAS publicas saem
# no maximo `BYBIT_REQ_POR_S` por segundo. Envio de ordem nao passa por aqui: atraso em ordem custa preco.
_REQ_POR_S = float(os.getenv("BYBIT_REQ_POR_S", "5") or 5)
_trava_taxa = threading.Lock()
_proximo_livre = 0.0


def _esperar_vez():
    """Pega o proximo lugar na fila global e dorme so o que falta para ele."""
    global _proximo_livre
    if _REQ_POR_S <= 0:
        return
    intervalo = 1.0 / _REQ_POR_S
    with _trava_taxa:
        agora = time.monotonic()
        meu_horario = max(_proximo_livre, agora)
        _proximo_livre = meu_horario + intervalo
    # dorme FORA da trava: senao as threads se serializariam na propria trava, e nao na fila
    espera = meu_horario - time.monotonic()
    if espera > 0:
        time.sleep(espera)


def _erro_de_rede(e: Exception) -> bool:
    """
    Vale a pena repetir? Timeout, queda de conexão e limite de chamadas, sim — são transitórios. Erro de
    parâmetro, de credencial ou de saldo, não: repetir só gasta chamada e atrasa o ciclo.
    """
    try:
        if isinstance(e, (ccxt.NetworkError, ccxt.RequestTimeout, ccxt.ExchangeNotAvailable,
                          ccxt.DDoSProtection, ccxt.RateLimitExceeded)):
            return True
    except AttributeError:
        pass
    texto = str(e).lower()
    return any(t in texto for t in ("timeout", "timed out", "10006", "too many visits",
                                    "temporarily unavailable", "connection", "bad gateway"))


class BybitConnector:
    exchange_name = "bybit"

    def __init__(self, modo_execucao: str = "simulador", categoria: str = "linear",
                 api_key: Optional[str] = None, api_secret: Optional[str] = None,
                 recv_window: int = 20000, subconta: Optional[str] = None):
        modo_execucao = (modo_execucao or "simulador").lower().strip()
        if modo_execucao not in MODOS_VALIDOS:
            raise ValueError(f"modo_execucao inválido: {modo_execucao}. Use um de {MODOS_VALIDOS}")
        self.modo_execucao = modo_execucao
        self.categoria = categoria if categoria in ("spot", "linear", "inverse") else "linear"
        self._markets_loaded = False

        self.subconta = (subconta or "principal") if str(subconta or "principal").strip() else "principal"
        if modo_execucao in MODOS_COM_ORDEM:
            sandbox = modo_execucao == "testnet"
            if api_key and api_secret:
                self.api_key, self.api_secret = api_key, api_secret
            else:
                self.api_key, self.api_secret = credenciais(self.subconta, modo_execucao)
                if not (self.api_key and self.api_secret) and str(self.subconta).lower() not in SUBCONTA_PRINCIPAL:
                    k, sec = nomes_variaveis(self.subconta, modo_execucao)
                    raise ValueError(
                        f"subconta '{self.subconta}' sem credenciais em modo {modo_execucao}: defina {k} e {sec} "
                        f"no .env. O conector não usa a conta principal no lugar da subconta.")
        else:  # simulador: dados públicos da mainnet, sem credenciais
            self.subconta = "principal"
            self.api_key = None
            self.api_secret = None
            sandbox = False

        config: Dict[str, Any] = {
            "enableRateLimit": True,
            "timeout": 20000,
            "options": {
                "defaultType": "spot" if self.categoria == "spot" else "swap",
                "recvWindow": recv_window,
                "adjustForTimeDifference": True,
            },
        }
        if self.api_key and self.api_secret:
            config["apiKey"] = self.api_key
            config["secret"] = self.api_secret

        self.exchange = ccxt.bybit(config)
        self.exchange.set_sandbox_mode(sandbox)
        # Demo Trading vive na conta oficial (api-demo.bybit.com), não no testnet: outra base de URL, mesma conta.
        self.demo = modo_execucao == "demo"
        if self.demo:
            self.exchange.enable_demo_trading(True)
        self.sandbox = sandbox

    # ------------------------------------------------------------------ utils
    @property
    def tem_credenciais(self) -> bool:
        return bool(self.api_key and self.api_secret)

    @property
    def pode_enviar_ordens(self) -> bool:
        return self.modo_execucao in MODOS_COM_ORDEM and self.tem_credenciais

    def info_chave(self) -> Dict[str, Any]:
        """
        Quem é o dono desta chave, segundo a própria Bybit: UID, tipo (principal ou subconta), permissões e validade.

        É o que prova que a separação por subconta está de pé: dois robôs com UID diferente não disputam a mesma
        posição. Se dois robôs mostrarem o MESMO uid, as chaves apontam para a mesma conta, e um vai fechar a
        posição do outro.
        """
        self._exigir_credenciais("info_chave")
        r = self.exchange.privateGetV5UserQueryApi({}) or {}
        d = (r.get("result") or {}) if isinstance(r, dict) else {}
        permissoes = {k: v for k, v in (d.get("permissions") or {}).items() if v}
        # a Bybit devolve parentUid "0" para a conta principal: isso não é um pai, é a ausência de pai
        pai = str(d.get("parentUid") or "").strip()
        pai = pai if pai not in ("", "0") else None
        return {
            "uid": str(d.get("userID") or d.get("uid") or ""),
            "tipo": "subconta" if pai else "principal",
            "uid_pai": pai,
            "nota": d.get("note"),
            "permissoes": permissoes,
            "somente_leitura": d.get("readOnly") in (1, True),
            "expira_em": d.get("expiredAt") or None,
            "ips": d.get("ips") or [],
        }

    def pedir_fundos_demo(self, moeda: str = "USDT", quantidade: float = 100_000) -> Dict[str, Any]:
        """Só no modo demo: pede saldo fictício para a conta de Demo Trading."""
        if not self.demo:
            raise ValueError("pedir_fundos_demo só funciona no modo demo")
        self._exigir_credenciais("pedir_fundos_demo")
        return self.exchange.privatePostV5AccountDemoApplyMoney(
            {"adjustType": 0, "utaDemoApplyMoney": [{"coin": moeda, "amountStr": str(quantidade)}]})

    def _load_markets(self):
        if not self._markets_loaded:
            self.exchange.load_markets()
            self._markets_loaded = True

    def simbolo(self, par: str) -> str:
        """Converte 'BTCUSDT' / 'BTC/USDT' para o símbolo ccxt da categoria."""
        p = (par or "").upper().replace("-", "").strip()
        if ":" in p:
            base_quote = p.split(":")[0]
        else:
            base_quote = p
        base_quote = base_quote.replace("/", "")
        if self.categoria == "inverse":
            # perpétuo inverso: BTCUSD / BTCUSDT / BTC -> BTC/USD:BTC (margem e P&L na moeda base)
            for quote in ("USDT", "USDC", "USD"):
                if base_quote.endswith(quote) and len(base_quote) > len(quote):
                    base_quote = base_quote[: -len(quote)]
                    break
            return f"{base_quote}/USD:{base_quote}"
        for quote in ("USDT", "USDC", "USD", "BTC", "ETH"):
            if base_quote.endswith(quote) and len(base_quote) > len(quote):
                base = base_quote[: -len(quote)]
                if self.categoria == "linear":
                    return f"{base}/{quote}:{quote}" if quote in ("USDT", "USDC") else f"{base}/{quote}"
                return f"{base}/{quote}"
        return par

    def simbolo_bybit(self, par: str) -> str:
        """Id nativo da Bybit (ex.: BTCUSDT)."""
        return self.simbolo(par).split(":")[0].replace("/", "")

    def info_mercado(self, par: str) -> Dict[str, Any]:
        self._load_markets()
        m = self.exchange.market(self.simbolo(par))
        limites = m.get("limits", {}) or {}
        return {
            "symbol": m["symbol"],
            "id": m["id"],
            "qty_step": m.get("precision", {}).get("amount") or 0.001,
            "price_step": m.get("precision", {}).get("price") or 0.1,
            "min_qty": (limites.get("amount") or {}).get("min") or 0.001,
            "max_qty": (limites.get("amount") or {}).get("max"),
            "min_cost": (limites.get("cost") or {}).get("min"),
            "contract_size": m.get("contractSize") or 1,
            "max_leverage": (limites.get("leverage") or {}).get("max"),
        }

    def arredondar_quantidade(self, par: str, qty: float) -> float:
        info = self.info_mercado(par)
        q = arredondar_para_step(qty, info["qty_step"], "down")
        if q < info["min_qty"]:
            return 0.0
        if info.get("max_qty") and q > info["max_qty"]:
            q = info["max_qty"]
        return q

    def arredondar_preco(self, par: str, preco: float) -> float:
        info = self.info_mercado(par)
        return arredondar_para_step(preco, info["price_step"], "nearest")

    # ------------------------------------------------------------ dados públicos
    def _com_repeticao(self, descricao: str, chamada, tentativas: int = 3, espera: float = 1.0):
        """
        Repete uma LEITURA que falhou por rede. Só leitura: reenviar ordem por timeout duplicaria posição.

        Sem isso, um timeout virava ciclo perdido. E ciclo perdido não é só um dado que falta: é a gestão da
        posição que não roda — stop não sobe, parcial não sai, saída estrutural não é avaliada. Num episódio
        real, 235 timeouts em dez minutos deixaram os quatro robôs cegos o tempo todo, e nenhum deles tentou
        de novo dentro do próprio ciclo.

        A espera cresce a cada tentativa, e o 10006 (limite de chamadas da corretora) espera mais: insistir
        rápido num rate limit é a forma mais certa de continuar limitado.
        """
        ultimo = None
        for n in range(1, tentativas + 1):
            try:
                _esperar_vez()
                return chamada()
            except Exception as e:
                ultimo = e
                if not _erro_de_rede(e) or n == tentativas:
                    raise
                pausa = espera * n * (5.0 if "10006" in str(e) else 1.0)
                logger.warning("%s falhou (%d/%d), repetindo em %.1fs: %s",
                               descricao, n, tentativas, pausa, f"{type(e).__name__}: {e}"[:140])
                time.sleep(pausa)
        raise ultimo

    def obter_preco_atual(self, par: str) -> float:
        ticker = self._com_repeticao(f"preço de {par}",
                                     lambda: self.exchange.fetch_ticker(self.simbolo(par)))
        return float(ticker["last"])

    def obter_ohlcv(self, par: str, timeframe: str = "15m", limite: int = 200,
                    somente_fechados: bool = False, since_ms: Optional[int] = None) -> List[list]:
        tf = normalizar_timeframe(timeframe)
        candles = self._com_repeticao(
            f"candles {par} {tf}",
            lambda: self.exchange.fetch_ohlcv(self.simbolo(par), timeframe=tf, limit=limite, since=since_ms))
        candles = [[int(c[0]), float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[5] or 0)] for c in candles]
        candles.sort(key=lambda c: c[0])
        if somente_fechados:
            candles = ultimo_candle_fechado(candles, tf)
        return candles

    def obter_ohlcv_historico(self, par: str, timeframe: str, since_ms: int,
                              until_ms: Optional[int] = None, pausa: float = 0.2) -> List[list]:
        """Baixa candles em blocos de 1000 até `until_ms` (ou agora)."""
        tf = normalizar_timeframe(timeframe)
        until_ms = until_ms or int(time.time() * 1000)
        todos: List[list] = []
        cursor = since_ms
        while cursor < until_ms:
            bloco = self.exchange.fetch_ohlcv(self.simbolo(par), timeframe=tf, since=cursor, limit=1000)
            if not bloco:
                break
            todos.extend(bloco)
            ultimo = bloco[-1][0]
            if ultimo <= cursor or len(bloco) < 2:
                break
            cursor = ultimo + 1
            time.sleep(pausa)
        vistos = set()
        saida = []
        for c in todos:
            if c[0] in vistos or c[0] > until_ms:
                continue
            vistos.add(c[0])
            saida.append([int(c[0]), float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[5] or 0)])
        saida.sort(key=lambda c: c[0])
        return saida

    def obter_order_book(self, par: str, profundidade: int = 50) -> Dict[str, list]:
        book = self._com_repeticao(
            f"livro de {par}",
            lambda: self.exchange.fetch_order_book(self.simbolo(par), limit=profundidade))
        return {
            "bids": [(float(p), float(q)) for p, q in book["bids"][:profundidade]],
            "asks": [(float(p), float(q)) for p, q in book["asks"][:profundidade]],
            "timestamp": book.get("timestamp"),
        }

    def obter_trades(self, par: str, limit: int = 500) -> List[Dict[str, Any]]:
        """Últimos negócios públicos, no formato usado pelo OrderFlowAnalyzerPro."""
        raw = self._com_repeticao(
            f"negócios de {par}",
            lambda: self.exchange.fetch_trades(self.simbolo(par), limit=limit))
        trades = []
        for t in raw:
            side = t.get("side") or "buy"
            trades.append({
                "price": float(t["price"]),
                "qty": float(t["amount"]),
                "side": "buy" if side == "buy" else "sell",
                "timestamp": int(t["timestamp"]),
            })
        return trades

    # ------------------------------------------------------------ conta/posição
    def _exigir_credenciais(self, acao: str):
        if not self.pode_enviar_ordens:
            raise PermissionError(
                f"{acao}: modo '{self.modo_execucao}' não envia ordens ou não há credenciais configuradas"
            )

    def obter_saldo(self, moeda: str = "USDT") -> Dict[str, float]:
        self._exigir_credenciais("obter_saldo")
        bal = self.exchange.fetch_balance()
        item = bal.get(moeda, {}) or {}
        return {
            "free": float(item.get("free") or 0),
            "used": float(item.get("used") or 0),
            "total": float(item.get("total") or 0),
        }

    def obter_posicao(self, par: str) -> Optional[Dict[str, Any]]:
        """Retorna a posição aberta (ou None). Só faz sentido para linear."""
        self._exigir_credenciais("obter_posicao")
        posicoes = self.exchange.fetch_positions([self.simbolo(par)])
        for p in posicoes:
            contratos = float(p.get("contracts") or 0)
            if contratos > 0:
                info = p.get("info", {}) or {}
                return {
                    "side": "buy" if (p.get("side") == "long") else "sell",
                    "quantidade": contratos,
                    "preco_entrada": float(p.get("entryPrice") or 0),
                    "pnl_nao_realizado": float(p.get("unrealizedPnl") or 0),
                    "alavancagem": p.get("leverage"),
                    "sl": float(info.get("stopLoss") or 0) or None,
                    "tp": float(info.get("takeProfit") or 0) or None,
                    "position_idx": int(info.get("positionIdx") or 0),
                    "liquidacao": p.get("liquidationPrice"),
                }
        return None

    def configurar_conta(self, par: str, alavancagem: Optional[int] = None,
                         margin_mode: Optional[str] = None, position_mode: Optional[str] = None) -> Dict[str, str]:
        """
        Ajusta alavancagem, modo de margem (cross/isolated) e modo de posição (one-way/hedged).
        Erros "não modificado" da Bybit são ignorados (já está configurado).
        """
        self._exigir_credenciais("configurar_conta")
        symbol = self.simbolo(par)
        resultado = {}
        if position_mode:
            hedged = position_mode.lower() in ("hedged", "hedge", "both")
            try:
                self.exchange.set_position_mode(hedged, symbol)
                resultado["position_mode"] = "ok"
            except Exception as e:  # 110025 = já está no modo
                resultado["position_mode"] = f"ignorado: {str(e)[:80]}"
        if margin_mode:
            try:
                self.exchange.set_margin_mode(margin_mode.lower(), symbol,
                                              params={"leverage": alavancagem or 1})
                resultado["margin_mode"] = "ok"
            except Exception as e:
                resultado["margin_mode"] = f"ignorado: {str(e)[:80]}"
        if alavancagem:
            try:
                self.exchange.set_leverage(int(alavancagem), symbol)
                resultado["alavancagem"] = "ok"
            except Exception as e:  # 110043 = leverage not modified
                resultado["alavancagem"] = f"ignorado: {str(e)[:80]}"
        return resultado

    # ------------------------------------------------------------------ ordens
    def criar_ordem(self, par: str, side: str, quantidade: float, tipo: str = "market",
                    preco: Optional[float] = None, stop_loss: Optional[float] = None,
                    take_profit: Optional[float] = None, reduce_only: bool = False,
                    position_idx: int = 0, post_only: bool = False,
                    client_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Envia ordem para a Bybit com SL/TP anexados à posição (um único request).
        side: 'buy' | 'sell'. quantidade em contratos (BTC para BTCUSDT linear).
        """
        self._exigir_credenciais("criar_ordem")
        side = side.lower()
        if side not in ("buy", "sell"):
            raise ValueError(f"side inválido: {side}")
        symbol = self.simbolo(par)
        qty = self.arredondar_quantidade(par, quantidade)
        if qty <= 0:
            raise ValueError(f"quantidade {quantidade} abaixo do mínimo da exchange para {par}")

        params: Dict[str, Any] = {"positionIdx": position_idx}
        if reduce_only:
            params["reduceOnly"] = True
        if post_only and tipo == "limit":
            params["postOnly"] = True
        if self.categoria in ("linear", "inverse"):
            if stop_loss:
                params["stopLoss"] = {"triggerPrice": self.arredondar_preco(par, stop_loss)}
            if take_profit:
                params["takeProfit"] = {"triggerPrice": self.arredondar_preco(par, take_profit)}
        if client_id:
            params["orderLinkId"] = client_id[:36]

        preco_final = self.arredondar_preco(par, preco) if (tipo == "limit" and preco) else None
        ordem = self.exchange.create_order(symbol, tipo, side, qty, preco_final, params)
        logger.info("Ordem enviada %s %s %s qty=%s sl=%s tp=%s id=%s",
                    self.modo_execucao, symbol, side, qty, stop_loss, take_profit, ordem.get("id"))
        return ordem

    def criar_ordem_stop(self, par: str, side: str, quantidade: float, gatilho: float,
                         position_idx: int = 0) -> Dict[str, Any]:
        """
        Stop CONDICIONAL reduce-only a mercado, independente do SL da posição: vale para uma parte só (a escada de hedge
        do portal Tradeiros tem um stop por escada) e continua na corretora com o servidor desligado.
        side 'buy' dispara quando o preço SOBE até o gatilho; 'sell', quando cai.
        """
        self._exigir_credenciais("criar_ordem_stop")
        side = side.lower()
        qty = self.arredondar_quantidade(par, quantidade)
        if qty <= 0:
            raise ValueError(f"quantidade {quantidade} abaixo do mínimo da exchange para {par}")
        params = {"positionIdx": position_idx, "reduceOnly": True, "triggerPrice": self.arredondar_preco(par, gatilho),
                  "triggerDirection": 1 if side == "buy" else 2}
        ordem = self.exchange.create_order(self.simbolo(par), "market", side, qty, None, params)
        logger.info("Stop condicional %s %s %s qty=%s gatilho=%s id=%s", self.modo_execucao, self.simbolo(par), side, qty,
                    gatilho, ordem.get("id"))
        return ordem

    def atualizar_stop_posicao(self, par: str, stop_loss: Optional[float] = None,
                               take_profit: Optional[float] = None, position_idx: int = 0) -> Dict[str, Any]:
        """Altera SL/TP da posição aberta (endpoint /v5/position/trading-stop)."""
        self._exigir_credenciais("atualizar_stop_posicao")
        self._load_markets()
        req = {
            "category": self.categoria if self.categoria != "spot" else "linear",
            "symbol": self.simbolo_bybit(par),
            "positionIdx": position_idx,
            "tpslMode": "Full",
        }
        if stop_loss is not None:
            req["stopLoss"] = str(self.arredondar_preco(par, stop_loss))
        if take_profit is not None:
            req["takeProfit"] = str(self.arredondar_preco(par, take_profit))
        return self.exchange.privatePostV5PositionTradingStop(req)

    def fechar_posicao(self, par: str) -> Optional[Dict[str, Any]]:
        """Fecha a posição aberta a mercado (reduceOnly)."""
        pos = self.obter_posicao(par)
        if not pos:
            return None
        lado_saida = "sell" if pos["side"] == "buy" else "buy"
        return self.criar_ordem(par, lado_saida, pos["quantidade"], tipo="market",
                                reduce_only=True, position_idx=pos.get("position_idx", 0))

    def cancelar_ordens_abertas(self, par: str) -> int:
        self._exigir_credenciais("cancelar_ordens_abertas")
        abertas = self.exchange.fetch_open_orders(self.simbolo(par))
        for o in abertas:
            try:
                self.exchange.cancel_order(o["id"], self.simbolo(par))
            except Exception as e:
                logger.warning("Falha ao cancelar ordem %s: %s", o.get("id"), e)
        return len(abertas)

    def cancelar_entradas_abertas(self, par: str) -> int:
        """
        Cancela só as ordens de ENTRADA abertas no par: nem reduce-only (saídas), nem condicionais (SL/TP).
        Devolve quantas cancelou. É o que um robô recém-iniciado não pode herdar sem saber.
        """
        self._exigir_credenciais("cancelar_entradas_abertas")
        n = 0
        for o in self.exchange.fetch_open_orders(self.simbolo(par)):
            info = o.get("info") or {}
            reduz = o.get("reduceOnly") or str(info.get("reduceOnly")).lower() == "true"
            condicional = bool(info.get("stopOrderType")) or bool(o.get("triggerPrice") or o.get("stopPrice"))
            if reduz or condicional:
                continue
            try:
                self.exchange.cancel_order(o["id"], self.simbolo(par))
                n += 1
                logger.warning("ordem de entrada esquecida cancelada: %s %s %s @ %s", o.get("id"), o.get("side"),
                               o.get("amount"), o.get("price"))
            except Exception as e:
                logger.warning("Falha ao cancelar ordem %s: %s", o.get("id"), e)
        return n

    def obter_pnl_fechado(self, par: str, desde_ms: Optional[int] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Histórico de P&L realizado da Bybit (linear)."""
        self._exigir_credenciais("obter_pnl_fechado")
        req = {"category": self.categoria if self.categoria != "spot" else "linear", "symbol": self.simbolo_bybit(par), "limit": limit}
        if desde_ms:
            req["startTime"] = int(desde_ms)
        resp = self.exchange.privateGetV5PositionClosedPnl(req)
        lista = (resp.get("result") or {}).get("list") or []
        saida = []
        for item in lista:
            saida.append({
                "order_id": item.get("orderId"),
                "side": (item.get("side") or "").lower(),
                "qty": float(item.get("qty") or 0),
                "preco_entrada": float(item.get("avgEntryPrice") or 0),
                "preco_saida": float(item.get("avgExitPrice") or 0),
                "pnl": float(item.get("closedPnl") or 0),
                "timestamp": int(item.get("updatedTime") or 0),
            })
        return saida

    def testar_conexao(self) -> Dict[str, Any]:
        """Diagnóstico rápido: horário, ticker e (se houver chaves) saldo."""
        out: Dict[str, Any] = {"modo": self.modo_execucao, "sandbox": self.sandbox, "categoria": self.categoria,
                               "subconta": self.subconta, "demo": getattr(self, "demo", False)}
        try:
            out["server_time"] = self.exchange.fetch_time()
            out["ticker_btc"] = self.obter_preco_atual("BTCUSDT")
            out["publico"] = "ok"
        except Exception as e:
            out["publico"] = f"erro: {e}"
        if self.tem_credenciais and self.modo_execucao in MODOS_COM_ORDEM:
            try:
                out["saldo_usdt"] = self.obter_saldo("USDT")
                out["privado"] = "ok"
                try:
                    out["chave"] = self.info_chave()
                except Exception as e:
                    out["chave"] = {"erro": str(e)[:120]}
            except Exception as e:
                out["privado"] = f"erro: {e}"
        else:
            out["privado"] = "sem credenciais (modo simulador)"
        return out


if __name__ == "__main__":
    import json
    con = BybitConnector(modo_execucao="simulador")
    print(json.dumps(con.testar_conexao(), indent=2, default=str))
    print("Últimos 3 candles 15m:", con.obter_ohlcv("BTCUSDT", "15m", 3))
