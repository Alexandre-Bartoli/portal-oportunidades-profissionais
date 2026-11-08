"""Homologação local isolada: coleta de fontes habilitadas em SQLite separado.

A rotina de rede roda somente quando o operador executa stage-collect. A
interface stage-serve é somente de consulta e não inicia coletores.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import threading
import time

import core
from providers_extra import ListingBatch
from source_quality import audit_result, audit_summary, validate_sources
from source_validation import _check_jobs
from stage_storage import stage_paths, ensure_private, write_private_report
from source_reviews import review_report, pending_technical_review

STAGING_DB, STAGING_REPORT = stage_paths()
MAIN_DB = core.BASE / 'data' / 'jobs.sqlite3'
_LOCK = threading.RLock()


@contextmanager
def staging_database(db_path=None):
    """Isola operações do banco principal durante uma execução de linha de comando.

    O banco é configurado por processo. Não iniciar o servidor e a coleta
    simultaneamente na mesma instância de Python.
    """
    path = Path(db_path) if db_path is not None else STAGING_DB
    if path.resolve() in (MAIN_DB.resolve(), core.DB.resolve()):
        raise ValueError('O banco de homologação não pode ser o banco principal')
    ensure_private(path.parent)
    with _LOCK:
        old_db = core.DB
        core.DB = path
        try:
            yield path
        finally:
            core.DB = old_db


def _validate_inventory(provider, slug, items):
    if not isinstance(items, list):
        raise ValueError('Conector deve devolver uma lista')
    raw_count = getattr(items, 'raw_count', None)
    if raw_count is not None and (type(raw_count) is not int or raw_count < len(items)):
        raise ValueError('Contagem de anúncios originais inconsistente')
    if type(getattr(items, 'complete', True)) is not bool:
        raise ValueError('Indicador de inventário completo inválido')
    checked = _check_jobs(items)
    if checked['malformed'] or checked['duplicate_records']:
        raise ValueError('Inventário com anúncios inválidos ou duplicados')
    for job in items:
        if job.get('provider') != provider or job.get('source') != slug:
            raise ValueError('Proveniência não corresponde à fonte consultada')
        if job.get('demo'):
            raise ValueError('Anúncios fictícios não são aceitos na homologação')
    return checked


def collect_staging(config, *, fetcher=None, db_path=None, report_path=None, min_sources=2, now=None):
    """Consulta cada fonte uma única vez, valida e persiste anúncios elegíveis.

    Falha ou resposta inválida jamais é interpretada como inventário vazio.
    Só um inventário completo pode aumentar a contagem de anúncios ausentes.
    """
    validate_sources(config)
    if type(min_sources) is not int or not 1 <= min_sources <= 20:
        raise ValueError('min_sources deve estar entre 1 e 20')
    simulation = fetcher is not None
    if fetcher is None:
        fetcher = core.fetch_source
    results = []
    successful = 0
    saved = 0
    checked_at = now or datetime.now(timezone.utc).isoformat()
    with staging_database(db_path) as current_db:
        core.init()
        for source in config['sources']:
            if not source['enabled']:
                continue
            provider, slug = source['provider'], source['slug']
            if pending_technical_review(source):
                results.append({'source':provider+'/'+slug, 'status':'pending_review',
                    'reason':'technical_review_required', 'jobs':None, 'checked_at':checked_at,
                    'usage_review':source.get('usage_review','pending'), 'stored':0})
                continue
            started = time.perf_counter()
            try:
                items = fetcher(provider, slug)
                inventory = _validate_inventory(provider, slug, items)
                audit = audit_result(provider, slug, items=items)
                audit.update(inventory)
                # A verificação é feita ANTES de qualquer gravação no SQLite.
                # Persistir somente anúncios classificados e com procedência.
                core.save(items)
                complete = getattr(items, 'complete', True)
                audit['inactive_total'] = (
                    core.mark_missing(provider, slug, {x['id'] for x in items})
                    if complete else None
                )
                audit['stored'] = len(items)
                saved += len(items)
                if audit['status'] == 'ok':
                    successful += 1
            except Exception as exc:
                audit = audit_result(provider, slug, error=exc)
                audit['error_class'] = type(exc).__name__
                audit['stored'] = 0
                # Não publicar detalhes de rede no relatório de homologação.
            audit['elapsed_ms'] = round((time.perf_counter()-started) * 1000)
            audit['usage_review'] = source.get('usage_review', 'pending')
            # O relatório público não inclui anúncios, descrições ou URLs.
            audit.pop('examples', None)
            results.append(audit)
        with core.connect() as connection:
            active_real = connection.execute(
                'SELECT COUNT(*) FROM jobs WHERE active=1 AND demo=0'
            ).fetchone()[0]
            aliases = connection.execute('SELECT COUNT(*) FROM job_aliases').fetchone()[0]
            demonstrations = connection.execute(
                'SELECT COUNT(*) FROM jobs WHERE demo=1'
            ).fetchone()[0]
        if demonstrations:
            raise RuntimeError('O banco de homologação contém anúncios fictícios')
        try:
            from admin_history import record
            record({'checked_at':checked_at, 'mode':'homologacao', 'collected':saved,
                    'active':active_real, 'success':successful,
                    'errors':sum(r['status']=='error' for r in results)})
            history_error = False
        except Exception:
            history_error = True
    report = {
        'schema_version': 1,
        'phase': '0.9-homologacao-persistente',
        'mode': 'simulated_no_external_network' if simulation else 'external_network',
        'checked_at': checked_at,
        'criteria': {
            'min_sources_with_valid_jobs': min_sources,
            'sources_with_valid_jobs': successful,
            'met': successful >= min_sources,
        },
        'summary': audit_summary(results),
        'records_processed': saved,
        'history_error': history_error,
        'active_real_jobs_in_staging_db': active_real,
        'source_aliases_in_staging_db': aliases,
        'sources': results,
        'safety': {
            'isolated_db': True,
            'candidate_profiles_stored': False,
            'source_usage_review_complete': review_report(config)['status'] == 'all_enabled_reviewed',
            'persistent_volume_configured': bool(os.getenv('PORTAL_STAGING_DIR')),
            'backup_and_restore_automatically_run': False,
            'individual_apply_links_checked': False,
            'public_deployment_approved': False,
        },
    }
    write_private_report(report, report_path or STAGING_REPORT)
    return report


def collect_current_staging(*, min_sources=2):
    config = json.loads((core.BASE / 'sources.json').read_text(encoding='utf-8'))
    return collect_staging(config, min_sources=min_sources)


def staging_status(path=None):
    location = Path(path or STAGING_REPORT)
    if not location.exists():
        return {'status': 'not_run', 'phase': '0.9-homologacao-persistente'}
    return json.loads(location.read_text(encoding='utf-8'))
