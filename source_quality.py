"""Auditoria conservadora das fontes do Portal de Oportunidades.

Inspirado nas práticas de diagnósticos de provedores de Career Ops.
Este módulo é uma implementação independente, sem dependências externas.
"""
from collections import Counter
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

PROVIDERS = frozenset({'greenhouse', 'lever', 'ashby', 'gupy', 'smartrecruiters', 'breezy', 'solides', 'remotive', 'workable', 'inhire'})
CATEGORY = frozenset({'internship', 'employment', 'temporary'})


def validate_sources(config):
    """Falha explicitamente diante de configurações inválidas ou duplicadas."""
    if not isinstance(config, dict) or not isinstance(config.get('sources'), list):
        raise ValueError('Configuração precisa conter a lista sources')
    seen = set()
    for index, item in enumerate(config['sources']):
        if not isinstance(item, dict):
            raise ValueError(f'Fonte {index} não é objeto')
        provider, slug = item.get('provider'), item.get('slug')
        if provider not in PROVIDERS or not isinstance(slug, str) or not slug.strip():
            raise ValueError(f'Fonte {index}: provedor ou identificador inválido')
        if len(slug) > 150 or any(c in slug for c in '\r\n/\\?#'):
            raise ValueError(f'Fonte {index}: identificador inseguro')
        if type(item.get('enabled')) is not bool:
            raise ValueError(f'Fonte {index}: enabled deve ser booleano')
        if 'experimental_access' in item and (provider not in {'gupy', 'inhire'} or type(item['experimental_access']) is not bool):
            raise ValueError(f'Fonte {index}: acesso experimental inválido')
        key = (provider, slug.casefold())
        if key in seen:
            raise ValueError(f'Fonte duplicada: {provider}/{slug}')
        seen.add(key)
        if provider in {'smartrecruiters','breezy'} and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', slug):
            raise ValueError('Identificador do provedor inválido')
        if provider == 'inhire' and not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,78}[A-Za-z0-9])?',slug):
            raise ValueError('Identificador InHire inválido')
        if provider == 'gupy':
            from gupy import source_parameters
            source_parameters(slug)
        if provider == 'solides' and slug not in {'estagio', 'emprego', 'temporario'}:
            raise ValueError('Pesquisa Sólides não está entre as categorias permitidas')
        if provider == 'remotive' and slug != 'feed':
            raise ValueError('Identificador Remotive inválido')
        if provider == 'workable' and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}',slug):
            raise ValueError('Identificador Workable inválido')
    return {'total': len(config['sources']), 'enabled': sum(s['enabled'] for s in config['sources'])}


def classify_error(exc):
    """Diagnóstico de falhas: nunca interpretar exceção como lista vazia."""
    import urllib.error
    import json
    from source_limits import RateLimited
    if isinstance(exc, RateLimited):
        return 'rate_limited'
    if isinstance(exc, urllib.error.HTTPError):
        if exc.code == 404:
            return 'not_found'
        if exc.code in (401, 403):
            return 'access_denied'
        if exc.code == 429:
            return 'rate_limited'
        if exc.code >= 500:
            return 'server_error'
        return 'http_error'
    if isinstance(exc, (urllib.error.URLError, TimeoutError, ConnectionError)):
        return 'network_error'
    if isinstance(exc, (ValueError, KeyError, TypeError, json.JSONDecodeError)):
        return 'invalid_response'
    return 'unknown_error'


def audit_result(provider, slug, items=None, error=None):
    """Distingue sucesso sem vagas de erro de coleta."""
    if error is not None:
        return {'source': f'{provider}/{slug}', 'status': 'error',
                'reason': classify_error(error), 'jobs': None,
                'checked_at': datetime.now(timezone.utc).isoformat()}
    if not isinstance(items, list):
        raise ValueError('Itens da coleta devem formar lista')
    raw_count = getattr(items, 'raw_count', None)
    complete = getattr(items, 'complete', True)
    if not complete:
        state = 'partial'
    elif raw_count is not None and raw_count > 0 and not items:
        state = 'no_match'
    else:
        state = 'empty' if not items else 'ok'
    result = {'source': f'{provider}/{slug}', 'status': state,
            'reason': None, 'jobs': len(items), 'raw_count': raw_count,
            'complete': complete,
            'by_category': dict(Counter(j.get('kind', 'unknown') for j in items)),
            'checked_at': datetime.now(timezone.utc).isoformat()}
    if hasattr(items, 'details_attempted'):
        result['details_attempted'] = items.details_attempted
        result['details_succeeded'] = items.details_succeeded
    for field in ('duplicate_items', 'skipped_invalid_url'):
        if hasattr(items, field):
            result[field] = getattr(items, field)
    return result


def audit_summary(results):
    counts = Counter(r['status'] for r in results)
    return {'ok': counts['ok'], 'empty': counts['empty'], 'no_match': counts['no_match'],
            'error': counts['error'], 'partial': counts['partial'],
            'pending_review': counts['pending_review'],
            'jobs': sum((r.get('jobs') or 0) for r in results), 'sources_checked': len(results)}
