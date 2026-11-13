"""Coleta periódica, auditoria de provedores e preservação de vagas na falha."""
import json
import logging
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from core import BASE, fetch_source, save, init, mark_missing, stats, connect
from source_quality import validate_sources, audit_result, audit_summary
from discover_sources import from_database
from source_reviews import pending_technical_review

LOG = logging.getLogger('coleta')
STATE = BASE / 'data' / 'ultima_coleta.json'


def _write_private_json(path, value):
    """Substitui o destino sem seguir links simbólicos, usando arquivo temporário privado."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.parent.is_symlink():
        raise ValueError('Diretório de dados não pode ser link simbólico')
    if os.name == 'posix':
        path.parent.chmod(0o700)
    fd, name = tempfile.mkstemp(prefix='.portal-', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


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
        if pending_technical_review(source):
            results.append({'source':name, 'status':'pending_review',
                'reason':'technical_review_required', 'jobs':None,
                'checked_at':datetime.now(timezone.utc).isoformat()})
            continue
        try:
            items = fetch_source(provider, slug)
            if not isinstance(items, list):
                raise ValueError('O conector não retornou uma lista de vagas')
            # Somente uma resposta válida permite marcar anúncios como ausentes.
            save(items)
            # Nunca expirar vagas se o conector retornou apenas parte do catálogo.
            complete = getattr(items, 'complete', True)
            inactive = mark_missing(provider, slug, {x['id'] for x in items}) if complete else None
            audit = audit_result(provider, slug, items=items)
            audit['inactive_total'] = inactive
            audit['complete'] = complete
            successful += 1
            count += len(items)
            results.append(audit)
        except Exception as exc:
            failed += 1
            LOG.warning('Falha consultando %s: %s', name, exc)
            audit = audit_result(provider, slug, error=exc)
            audit['error'] = str(exc)[:250]
            results.append(audit)
    # Sugestões extraídas passivamente dos anúncios já armazenados.
    # Nunca ativar automaticamente um provedor recém-descoberto.
    with connect() as db:
        candidates = from_database(db, configured=config['sources'])
    candidates_path = BASE / 'data' / 'fontes_sugeridas.json'
    candidates_path.parent.mkdir(parents=True, exist_ok=True)
    _write_private_json(candidates_path, {'candidates': candidates})
    state = {'suggested_sources': len(candidates), 'finished_at': datetime.now(timezone.utc).isoformat(),
             'collected': count, 'successful_sources': successful,
             'failed_sources': failed, 'real_jobs_active': stats().get(1, 0),
             'audit_summary': audit_summary(results), 'sources': results}
    try:
        from admin_history import record
        record({'checked_at':state['finished_at'], 'mode':'local', 'collected':count,
                'active':state['real_jobs_active'], 'success':successful, 'errors':failed})
    except Exception:
        LOG.exception('Não foi possível registrar o histórico da coleta')
        state['history_error'] = True
    STATE.parent.mkdir(parents=True, exist_ok=True)
    _write_private_json(STATE, state)
    return state


def status():
    return json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {'status': 'not_run', 'sources': []}


def start_scheduler(hours=None):
    """Uma consulta inicial e atualização periódica enquanto o servidor estiver ativo."""
    hours = int(hours or os.getenv('INTERVALO_COLETA_HORAS', '6'))
    hours = max(1, min(hours, 168))
    def loop():
        while True:
            try:collect_once()
            except Exception:LOG.exception('Coleta periódica interrompida; nova tentativa no próximo intervalo')
            stop.wait(hours*3600)
    stop = threading.Event()
    worker = threading.Thread(target=loop, daemon=True, name='coleta-automatica')
    worker.start()
    return worker
