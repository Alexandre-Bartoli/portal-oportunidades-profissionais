"""Identidade estável de anúncios e identificação conservadora de duplicidades.

Conceito inspirado no Career Ops e no Job Pindorama. Implementação original.
Não usa similaridade de descrições como prova de identidade.
"""
import hashlib
import json
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

TRACKING_KEYS = {'utm_source', 'utm_medium', 'utm_campaign', 'utm_content',
                 'utm_term', 'fbclid', 'gclid', 'ref', 'source'}


def canonical_url(value):
    if not isinstance(value, str):
        return None
    try:
        u = urlsplit(value.strip())
        if u.scheme.lower() != 'https' or not u.hostname or u.username or u.password:
            return None
        host = u.hostname.lower().rstrip('.')
        port = '' if u.port in (None, 443) else f':{u.port}'
        query = urlencode(sorted((k, v) for k, v in parse_qsl(u.query, keep_blank_values=True)
                                 if k.lower() not in TRACKING_KEYS and not k.lower().startswith('utm_')))
        path = u.path.rstrip('/') or '/'
        return urlunsplit(('https', host + port, path, query, ''))
    except (ValueError, TypeError):
        return None


def stable_identity(provider, board_slug, posting_id):
    """ID forte: provedor, quadro e ID nativo; não inferir entre fontes."""
    parts = (provider, board_slug, str(posting_id) if posting_id is not None else '')
    if not all(isinstance(x, str) and x.strip() for x in parts):
        raise ValueError('Identidade exige provedor, quadro e ID da vaga')
    return 'listing_v1_' + hashlib.sha256(json.dumps(parts, ensure_ascii=False,
                         separators=(',', ':')).encode('utf-8')).hexdigest()


def deduplicate_listings(items):
    """Remove duplicidade exata por ID forte ou URL canônica.

    Duas vagas com título/empresa iguais podem ser legítimas: não mesclar.
    """
    result, seen_ids, seen_urls = [], set(), set()
    for item in items:
        provider, source, extid = item.get('provider'), item.get('source'), item.get('external_id')
        uid = None
        if provider and source and extid:
            uid = stable_identity(provider, source, extid)
        url = canonical_url(item.get('url'))
        if (uid and uid in seen_ids) or (url and url in seen_urls):
            continue
        if uid:
            seen_ids.add(uid)
        if url:
            seen_urls.add(url)
        result.append(item)
    return result