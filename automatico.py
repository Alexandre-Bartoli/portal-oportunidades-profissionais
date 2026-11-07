"""Consulta periódica de vagas em quadros públicos de empresas previamente selecionadas."""
import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from core import BASE, fetch_source, save, init

LOG = logging.getLogger('coleta')
STATE = BASE / 'data' / 'ultima_coleta.json'

def collect_once():
    init()
    config = json.loads((BASE / 'sources.json').read_text(encoding='utf-8'))
    results = []
    count = 0
    for source in config['sources']:
        if not source.get('enabled'):
            continue
        name = source['provider'] + '/' + source['slug']
        try:
            items = fetch_source(source['provider'], source['slug'])
            # País de abrangência da fonte não implica que todas as vagas sejam brasileiras.
            # Só se atribui Brasil quando constar nos dados da vaga.
            save(items)
            count += len(items)
            results.append({'source':name,'status':'ok','jobs':len(items)})
        except Exception as exc:
            LOG.warning('Falha consultando %s: %s',name,exc)
            results.append({'source':name,'status':'error','error':str(exc)[:250]})
    state={'finished_at':datetime.now(timezone.utc).isoformat(),'collected':count,'sources':results}
    STATE.parent.mkdir(parents=True,exist_ok=True)
    STATE.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
    return state

def status():
    return json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {'status':'not_run','sources':[]}

def start_scheduler(hours=None):
    """Uma consulta inicial e atualização periódica enquanto o servidor estiver ativo."""
    hours = int(hours or os.getenv('INTERVALO_COLETA_HORAS','6'))
    hours = max(1, min(hours,168))
    def loop():
        while True:
            collect_once()
            stop.wait(hours*3600)
    stop=threading.Event()
    worker=threading.Thread(target=loop,daemon=True,name='coleta-automatica')
    worker.start()
    return worker