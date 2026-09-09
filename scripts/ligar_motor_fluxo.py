"""
Liga o motor de fluxo nos robôs de scalp (core/motor_fluxo.py).

    python scripts/setup_db.py            # cria as colunas novas, se ainda não existirem
    python scripts/ligar_motor_fluxo.py   # mostra o que vai mudar
    python scripts/ligar_motor_fluxo.py --aplicar

O que muda no robô de scalp:
    usar_motor_fluxo = 1     decide por barra de volume, não por candle de 1m
    usar_websocket   = 1     sem stream de negócios não existe barra de fluxo
    tipo_entrada     = limite  a absorção é uma ordem ESPERANDO no nível, não uma corrida atrás do preço.
                               No backtest, entrar a mercado torrava o resultado em taxa: num dia o motor
                               fez −15 de resultado bruto e pagou 147 de taxa.

Robôs de daytrade e swing não são tocados: nos graus maiores o candle de tempo é uma régua honesta, e o
Hedge Inverso tem motor próprio.
"""
import sys

sys.path.insert(0, ".")

from api.database import SessionLocal, aguardar_banco  # noqa: E402

SEM_FLUXO = ("inverse_range",)


def main():
    aplicar = "--aplicar" in sys.argv
    if not aguardar_banco():
        print("banco fora do ar")
        return 1

    from models.bot import Bot

    db = SessionLocal()
    try:
        alvos = [b for b in db.query(Bot).order_by(Bot.id).all()
                 if "scalp" in (b.estilo_trade or "").lower() and getattr(b, "estrategia", None) not in SEM_FLUXO]
        if not alvos:
            print("nenhum robô de scalp cadastrado")
            return 0
        for b in alvos:
            print(f"  {b.id} {b.nome[:20]:<20} motor_fluxo {bool(getattr(b, 'usar_motor_fluxo', False))} -> True | "
                  f"websocket {bool(b.usar_websocket)} -> True | entrada {b.tipo_entrada} -> limite | "
                  f"barra {getattr(b, 'barra_tipo', 'volume')} "
                  f"{'automática' if not getattr(b, 'barra_tamanho', 0) else getattr(b, 'barra_tamanho')} "
                  f"a cada {getattr(b, 'barra_segundos_alvo', 30) or 30:.0f}s")
            if aplicar:
                b.usar_motor_fluxo = True
                b.usar_websocket = True
                b.tipo_entrada = "limite"
                b.barra_tipo = getattr(b, "barra_tipo", None) or "volume"
                b.barra_tamanho = float(getattr(b, "barra_tamanho", 0) or 0)
                b.barra_segundos_alvo = float(getattr(b, "barra_segundos_alvo", 0) or 30.0)
        if aplicar:
            db.commit()
            print(f"\n{len(alvos)} robô(s) de scalp no motor de fluxo. Reinicie o servidor para valer.")
        else:
            print("\n(simulação: rode com --aplicar para gravar)")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
