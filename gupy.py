"""Adaptador experimental do catálogo público Gupy.

Inspirado na organização do job-pindorama (MIT), mas implementado em Python
para o nosso sistema. Antes de ativar a coleta real, verificar condições de
utilização e a disponibilidade documentada da rota do provedor.
"""
from urllib.parse import urlencode, urljoin, urlparse

ENDPOINT = 'https://portal.gupy.io/api/job-search/jobs'
CONTRACTS = {
    'internship': 'vacancy_type_internship',
    'employment': 'vacancy_type_effective',
    'temporary': 'vacancy_type_temporary',
}
MODES = {'remote': 'remote', 'hybrid': 'hybrid', 'on-site': 'onsite'}


def build_url(query, contract='internship', limit=25, offset=0, city='', state=''):
    if contract not in CONTRACTS:
        raise ValueError('Categoria não permitida')
    if not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError('Limite inválido')
    if not isinstance(offset, int) or offset < 0:
        raise ValueError('Deslocamento inválido')
    params = {'jobName': str(query)[:80], 'type': CONTRACTS[contract],
              'limit': str(limit), 'offset': str(offset)}
    if city:
        params['city'] = city
    if state:
        params['state'] = state
    return ENDPOINT + '?' + urlencode(params)


def safe_job_url(value):
    if not isinstance(value, str) or not value:
        return ''
    url = urljoin('https://portal.gupy.io/', value)
    parsed = urlparse(url)
    if parsed.scheme != 'https' or not parsed.hostname:
        return ''
    host = parsed.hostname.lower()
    if host != 'gupy.io' and not host.endswith('.gupy.io'):
        return ''
    return url


def normalize_item(raw, requested_kind):
    """Nunca marca requisitos e localização ausentes como informação verificada."""
    if not isinstance(raw, dict) or not raw.get('id') or not raw.get('name'):
        return None
    code = raw.get('type')
    mapping = {v: k for k, v in CONTRACTS.items()}
    kind = mapping.get(code)
    if kind is None or kind != requested_kind:
        return None
    url = safe_job_url(raw.get('jobUrl'))
    if not url:
        return None
    city = str(raw.get('city') or '').strip()
    state = str(raw.get('state') or '').strip()
    return {
        'id': str(raw['id']), 'title': str(raw['name']),
        'company': str(raw.get('careerPageName') or ''),
        'description': str(raw.get('description') or ''),
        'location': ', '.join(v for v in (city, state) if v),
        'country': 'BR' if state else None,
        'mode': MODES.get(raw.get('workplaceType'), 'unknown'),
        'kind': kind, 'url': url,
        'date': raw.get('publishedDate'),
    }


def fetch(query, contract='internship', pages=1, get_json=None, **filters):
    if get_json is None:
        from core import get_json as get_json_impl
        get_json = get_json_impl
    if not isinstance(pages, int) or not 1 <= pages <= 5:
        raise ValueError('Limite de páginas inválido')
    result = []
    raw_count = 0
    for page in range(pages):
        payload = get_json(build_url(query, contract=contract, offset=page*25, **filters))
        if not isinstance(payload, dict) or not isinstance(payload.get('data'), list):
            raise ValueError('Resposta inesperada da Gupy')
        batch = payload['data']
        raw_count += len(batch)
        result.extend(item for row in batch if (item := normalize_item(row, contract)) is not None)
        if len(batch) < 25:
            break
    from providers_extra import ListingBatch
    # A consulta usa filtros e pode cobrir apenas uma fração do catálogo.
    return ListingBatch(result, complete=False, raw_count=raw_count)
