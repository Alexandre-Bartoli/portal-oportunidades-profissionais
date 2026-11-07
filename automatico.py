"""Coleta periódica, auditoria de provedores e preservação de vagas na falha."""
import json
import logging
import os
import threading
from datetime import datetime, timezone
from core import BASE, fetch_source, save, init, mark_missing, stats
from source_quality import validate_sources, audit_result, audit_summary

LOG = logging.getLogger('coleta')
STATE = BASE / 'data' / 'ultima_coleta.json'


def collect_once():
    init()
    config = json.loads((BASE / 'sources.json').read_text(encoding='utf-8'))
    validate_sources(config)
    results = []
    count = 0
    successful = 0
    failed = 0
    for source in config['sources']:
        if not source['enabled']:
            continue
        provider, slug = source['provider'], source['slug']
        name = provider + '/' + slug
        try:
            items = fetch_source(provider, slug)
            if not isinstance(items, list):
                raise ValueError('O conector não retornou uma lista de vagas')
            # Somente uma resposta válida permite marcar anúncios como ausentes.
            save(items)
            inactive = mark_missing(provider, slug, {x['id'] for x in items})
            audit = audit_result(provider, slug, items=items)
            audit['inactive_total'] = inactive
            successful += 1
            count += len(items)
            results.append(audit)
        except Exception as exc:
            failed += 1
            LOG.warning('Falha consultando %s: %s', name, exc)
            audit = audit_result(provider, slug, error=exc)
            audit['error'] = str(exc)[:250]
            results.append(audit)
    state = {'finished_at': datetime.now(timezone.utc).isoformat(),
             'collected': count, 'successful_sources': successful,
             'failed_sources': failed, 'real_jobs_active': stats().get(1, 0),
             'audit_summary': audit_summary(results), 'sources': results}
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    return state


def status():
    return json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {'status': 'not_run', 'sources': []}


def start_scheduler(hours=None):
    """Uma consulta inicial e atualização periódica enquanto o servidor estiver ativo."""
    hours = int(hours or os.getenv('INTERVALO_COLETA_HORAS', '6'))
    hours = max(1, min(hours, 168))
    def loop():
        while True:
            collect_once()
            stop.wait(hours*3600)
    stop = threading.Event()
    worker = threading.Thread(target=loop, daemon=True, name='coleta-automatica')
    worker.start()
    return worker