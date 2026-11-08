"""Auditoria externa, somente leitura, das fontes habilitadas.

Não grava anúncios no SQLite, não desativa vagas e não habilita novas fontes.
Respostas válidas com zero resultados compatíveis são diferentes de fontes vazias.
"""

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from urllib.parse import urlsplit

from source_quality import audit_result, audit_summary, classify_error, validate_sources
from listing_identity import canonical_url
from source_reviews import pending_technical_review


REQUIRED = ('id', 'title', 'url', 'kind', 'provider', 'source')


def _check_jobs(items):
    """Validação estrutural sem abrir os endereços de anúncios externos."""
    seen_ids, seen_urls = set(), set()
    duplicates = 0
    malformed = 0
    examples = []
    categories = Counter()
    for job in items:
        if not isinstance(job, dict) or any(not job.get(field) for field in REQUIRED):
            malformed += 1
            continue
        url = job['url']
        try:
            parsed = urlsplit(url)
            canonical = canonical_url(url)
        except (TypeError, ValueError):
            malformed += 1
            continue
        if parsed.scheme != 'https' or not parsed.hostname or not canonical:
            malformed += 1
            continue
        if job['kind'] not in ('internship', 'employment', 'temporary'):
            malformed += 1
            continue
        jid = (job['provider'], job['source'], str(job['id']))
        if jid in seen_ids or canonical in seen_urls:
            duplicates += 1
        seen_ids.add(jid)
        seen_urls.add(canonical)
        categories[job['kind']] += 1
        if len(examples) < 2:
            examples.append({'title': str(job['title'])[:100], 'url': canonical})
    return {'malformed': malformed, 'duplicate_records': duplicates,
            'distinct_urls': len(seen_urls), 'by_category': dict(categories),
            'examples': examples}


def verify_config(config, *, fetcher=None, min_sources=2, now=None):
    """Consulta as fontes marcadas enabled, mas nunca modifica o banco de vagas.

    min_sources = mínimo de fontes COMPLETAS com anúncios compatíveis e sem erro.
    Resposta HTTP bem-sucedida não constitui autorização para republicação.
    """
    validate_sources(config)
    if type(min_sources) is not int or not 1 <= min_sources <= 20:
        raise ValueError('min_sources deve ser inteiro entre 1 e 20')
    if fetcher is None:
        from core import fetch_source
        fetcher = fetch_source
    results = []
    verified = 0
    for entry in config['sources']:
        if not entry['enabled']:
            continue
        provider, slug = entry['provider'], entry['slug']
        if pending_technical_review(entry):
            results.append({'source':f'{provider}/{slug}', 'status':'pending_review',
                'reason':'technical_review_required', 'jobs':None, 'http_observed':False,
                'usage_review':entry.get('usage_review','pending')})
            continue
        started = time.perf_counter()
        try:
            items = fetcher(provider, slug)
            if not isinstance(items, list):
                raise ValueError('Conector não retornou uma lista')
            raw = getattr(items, 'raw_count', None)
            if raw is not None and (type(raw) is not int or raw < len(items)):
                raise ValueError('Contagem original inconsistente')
            check = _check_jobs(items)
            result = audit_result(provider, slug, items=items)
            result.update(check)
            if check['malformed'] or check['duplicate_records']:
                result['status'] = 'invalid_data'
                result['reason'] = 'inconsistent_records'
            # Cobertura demonstrável exige inventário completo, fonte não vazia,
            # pelo menos uma vaga compatível e registros íntegros.
            if result['status'] == 'ok' and items:
                verified += 1
            result['http_observed'] = True
        except Exception as exc:
            result = audit_result(provider, slug, error=exc)
            result['error_class'] = type(exc).__name__
            result['http_observed'] = False
        result['elapsed_ms'] = round((time.perf_counter() - started) * 1000)
        # Informação não verificada deve permanecer marcada como pendente.
        result['usage_review'] = entry.get('usage_review', 'pending')
        results.append(result)

    summary = audit_summary(results)
    checked = datetime.now(timezone.utc).isoformat() if now is None else now
    return {
        'schema_version': 1, 'checked_at': checked,
        'mode': 'read_only_real_network_when_available',
        'criteria': {'min_sources_with_valid_jobs': min_sources,
                     'sources_with_valid_jobs': verified,
                     'met': verified >= min_sources},
        'summary': summary,
        'sources': results,
        'limitations': [
            'Não verifica autorização jurídica de reprodução dos dados.',
            'Não confirma que cada link individual permite inscrição.',
            'Não altera, exclui ou inclui vagas no banco local.',
        ],
    }


def write_report(report, path):
    """Escrita atômica de diagnóstico sem segredos nem conteúdo de currículos."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)
    return path


def verify_current_sources(*, min_sources=2):
    from core import BASE
    config = json.loads((BASE / 'sources.json').read_text(encoding='utf-8'))
    report = verify_config(config, min_sources=min_sources)
    write_report(report, BASE / 'data' / 'validacao_fontes.json')
    return report
