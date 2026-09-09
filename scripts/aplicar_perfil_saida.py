"""
Aplica o perfil de saída por estilo (core/perfil_saida.py) aos robôs já cadastrados.

Antes, os três estilos usavam 0,50% para ligar o trailing e 0,30% de distância. No swing de 4h isso é apertado
demais: o pavio de um único candle tira a posição. Agora cada estilo usa a folga do seu timeframe.

O escalonamento é ligado só nos robôs direcionais. O Hedge Inverso monta uma grade própria (inverse_range) e
realizar por fora atrapalharia a grade dele.
"""
import sys

sys.path.insert(0, ".")

from api.database import SessionLocal, aguardar_banco  # noqa: E402
from core.perfil_saida import perfil  # noqa: E402

SEM_ESCALONAMENTO = ("inverse_range",)


def main():
    if not aguardar_banco():
        print("banco fora do ar")
        return 1

    from models.bot import Bot
    from models.posicao_bot import PosicaoBot

    db = SessionLocal()
    try:
        for b in db.query(Bot).order_by(Bot.id).all():
            p = perfil(b.estilo_trade)
            antes = (b.ativador_trailing, b.distancia_trailing, b.usar_trailing_stop, b.usar_saida_escalonada)
            b.ativador_trailing = p.ativador_trailing
            b.distancia_trailing = p.distancia_trailing
            b.saida_escalonada = p.saida_escalonada
            b.usar_trailing_stop = True
            b.mover_stop_para_entrada = True
            b.usar_saida_escalonada = getattr(b, "estrategia", None) not in SEM_ESCALONAMENTO
            print(f"  {b.id} {b.nome[:18]:<18} {b.estilo_trade:<9} "
                  f"trailing {antes[0]:.2%}/{antes[1]:.2%} -> {p.ativador_trailing:.2%}/{p.distancia_trailing:.2%}"
                  f"   escalonada={b.usar_saida_escalonada} ({p.saida_escalonada})")

        # posição aberta antes desta mudança não tem a quantidade original registrada: sem ela o plano não fecha
        for pos in db.query(PosicaoBot).filter_by(status="aberta").all():
            if not pos.quantidade_inicial:
                pos.quantidade_inicial = pos.quantidade
                print(f"  posição {pos.id}: quantidade_inicial = {pos.quantidade}")
        db.commit()
        print("\nOK")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
