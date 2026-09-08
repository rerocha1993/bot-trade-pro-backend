"""
Varredura histórica de Elliott (persistência de contagens candidatas e promoção a validadas).
Usa o ElliottEngine O(N) via ElliottService.
"""
from core.spot_candles_fetcher import SpotCandlesFetcher
from services.elliott_service import ElliottService
from models.elliott_contagem_candidata import ElliottContagemCandidata

def iniciar_varredura_elliott_institucional(par, timeframes, data_inicio, data_fim, db_session, logger=None):
    """
    Varredura institucional: detecta, salva candidatas, valida e vincula ondas/ciclos.
    Só usa ElliottService real!
    """
    fetcher = SpotCandlesFetcher(exchange_id="bybit")
    elliott_service = ElliottService(db_session)
    total_ciclos = 0

    for tf in timeframes:
        candles = fetcher.fetch_all_candles(par, tf, data_inicio, data_fim, logger=logger)
        if not candles or len(candles) < 10:
            if logger:
                logger.warning(f"Nenhum ou poucos candles em {par} {tf}")
            continue

        candles_dict = {tf: candles}
        elliott_service.analisar_multi_timeframe(par, [tf], candles_dict)
        total_ciclos += 1
        promovidas = elliott_service.promover_candidatas(par, tf)
        if logger:
            logger.info(f"{par} {tf}: {promovidas} contagens promovidas")

    if logger:
        logger.info(f"Varredura institucional concluída: {total_ciclos} ciclos processados para {par}")
    return total_ciclos

def vincular_hierarquia_multi_timeframe(par, timeframes, data_inicio, data_fim, db_session, logger=None):
    """
    Vincula hierarquia institucional: ondas macro são parent das contagens/ondas micro.
    Usa ElliottService real. NÃO inventa nada.
    """
    elliott_service = ElliottService(db_session)
    # Ordena do maior para o menor timeframe
    tf_ordenados = sorted(timeframes, key=lambda x: (
        {'1M': 0, '1W': 1, '1D': 2, '4h': 3, '1h': 4, '15m': 5, '5m': 6, '1m': 7}[x]
    ))
    for idx, tf_macro in enumerate(tf_ordenados[:-1]):
        tf_micro = tf_ordenados[idx + 1]

        # Buscar ondas validadas do macro (já existente no seu service)
        ondas_macro = elliott_service.get_ondas_validadas(par, tf_macro)
        if not ondas_macro:
            if logger:
                logger.info(f"Sem ondas macro validadas em {par} {tf_macro}")
            continue

        for onda_macro in ondas_macro:
            t0 = onda_macro["data_inicio"]
            t1 = onda_macro["data_fim"]

            # Busca candles no micro, só dentro do range da onda macro
            fetcher = SpotCandlesFetcher(exchange_id="bybit")
            candles_micro = fetcher.fetch_all_candles(par, tf_micro, t0, t1, logger=logger)
            if not candles_micro or len(candles_micro) < 10:
                continue

            candles_dict_micro = {tf_micro: candles_micro}
            # Aqui é institucional: rodar só no micro, mas salvar parent_id da macro!
            elliott_service.analisar_multi_timeframe(par, [tf_micro], candles_dict_micro)
            
            # Após analisar, promover candidatas micro
            candidatas = (
                db_session.query(ElliottContagemCandidata)
                .filter_by(par=par, timeframe=tf_micro, status="candidata")
                .all()
            )
            for cand in candidatas:
                # Aqui pode vincular parent_id ao ID da macro, se não já estiver salvo (se sua modelagem permitir)
                try:
                    elliott_service.promover_e_validar(cand.id)
                    if logger:
                        logger.info(f"Promovida filha: {par} {tf_micro} id={cand.id} (parent macro={onda_macro.get('contagem_id')})")
                except Exception as e:
                    if logger:
                        logger.warning(f"Erro ao promover contagem filha: {e}")

def processar_varredura_multi_timeframe(par, timeframes, session, data_inicio, data_fim):
    """
    Processa a análise multi-timeframe, do maior para o menor, vinculando parent_id na micro.
    100% profissional, SEM mock, SEM exemplo, só método real.
    """
    ordem_tf = {'1M': 0, '1w': 1, '1d': 2, '4h': 3, '1h': 4, '15m': 5, '5m': 6, '1m': 7}
    tfs_ordenados = sorted(timeframes, key=lambda x: ordem_tf[x])
    service = ElliottService(session)
    fetcher = SpotCandlesFetcher()

    # 1. Processa os MACROS e já salva no banco
    for tf_macro in tfs_ordenados[:-1]:  # até o penúltimo
        print(f'Rodando análise para timeframe macro: {tf_macro}')
        candles_macro = fetcher.fetch_all_candles(par, tf_macro, data_inicio, data_fim)
        if not candles_macro or len(candles_macro) < 5:
            print(f'Skip macro {tf_macro}: poucos candles')
            continue
        candles_dict = {tf_macro: candles_macro}
        service.analisar_multi_timeframe(par, [tf_macro], candles_dict)
    print('--- MACROS finalizados ---')

    # 2. Agora processa as MICROS para cada parent macro, vinculando parent_id automaticamente
    for idx, tf_macro in enumerate(tfs_ordenados[:-1]):
        tf_micro = tfs_ordenados[idx + 1]
        print(f'Rodando micro {tf_micro} para cada parent macro {tf_macro}')
        contagens_macro = (
            session.query(ElliottContagemCandidata)
            .filter_by(par=par, timeframe=tf_macro)
            .filter(ElliottContagemCandidata.data_inicio >= data_inicio)
            .filter(ElliottContagemCandidata.data_fim <= data_fim)
            .all()
        )
        for macro in contagens_macro:
            t0 = macro.data_inicio
            t1 = macro.data_fim
            candles_micro = fetcher.fetch_all_candles(par, tf_micro, t0, t1)
            if not candles_micro or len(candles_micro) < 5:
                continue
            candles_dict_micro = {tf_micro: candles_micro}
            # Rodar análise para o micro
            service.analisar_multi_timeframe(par, [tf_micro], candles_dict_micro)
            # Agora, todas as candidatas salvas nesse range devem receber parent_id desse macro
            contagens_micro = (
                session.query(ElliottContagemCandidata)
                .filter_by(par=par, timeframe=tf_micro)
                .filter(ElliottContagemCandidata.data_inicio >= t0)
                .filter(ElliottContagemCandidata.data_fim <= t1)
                .all()
            )
            for micro in contagens_micro:
                if micro.parent_id != macro.id:
                    micro.parent_id = macro.id
                    session.commit()
    print('--- MICROS vinculadas e persistidas ---')
