"""Adaptador experimental do catálogo público Gupy.

Inspirado na organização do job-pindorama (MIT), mas implementado em Python
para o nosso sistema. Antes de ativar a coleta real, verificar condições de
utilização e a disponibilidade documentada da rota do provedor.
"""
import re
import json
from html.parser import HTMLParser
from urllib.parse import urlencode, urljoin, urlparse

ENDPOINT = 'https://portal.gupy.io/api/job-search/jobs'
CONTRACTS = {
    'internship': 'vacancy_type_internship',
    'employment': 'vacancy_type_effective',
    'temporary': 'vacancy_type_temporary',
}
MODES = {'remote': 'remote', 'hybrid': 'hybrid', 'on-site': 'onsite'}

# Nomes usados pela busca Gupy, adaptados do Job Pindorama (licença MIT).
UF_NAMES = {
    'AC':'Acre', 'AL':'Alagoas', 'AP':'Amapá', 'AM':'Amazonas', 'BA':'Bahia', 'CE':'Ceará',
    'DF':'Distrito Federal', 'ES':'Espírito Santo', 'GO':'Goiás', 'MA':'Maranhão',
    'MT':'Mato Grosso', 'MS':'Mato Grosso do Sul', 'MG':'Minas Gerais', 'PA':'Pará',
    'PB':'Paraíba', 'PR':'Paraná', 'PE':'Pernambuco', 'PI':'Piauí', 'RJ':'Rio de Janeiro',
    'RN':'Rio Grande do Norte', 'RS':'Rio Grande do Sul', 'RO':'Rondônia', 'RR':'Roraima',
    'SC':'Santa Catarina', 'SP':'São Paulo', 'SE':'Sergipe', 'TO':'Tocantins',
}

def source_parameters(slug):
    kinds = {'estagio':'internship', 'emprego':'employment', 'temporario':'temporary'}
    if not isinstance(slug, str): raise ValueError('Pesquisa Gupy inválida')
    parts = slug.split('-')
    if len(parts) == 1 and parts[0] in kinds:
        return kinds[parts[0]], ''
    if len(parts) == 2 and parts[0] in kinds and parts[1] in {x.lower() for x in UF_NAMES}:
        return kinds[parts[0]], UF_NAMES[parts[1].upper()]
    raise ValueError('Pesquisa Gupy inválida')

def explicit_country(value):
    if not isinstance(value,str): return None
    country=value.strip()
    if country.casefold() in ('brasil','brazil'): return 'BR'
    if re.fullmatch(r'[A-Za-z]{2}',country): return country.upper()
    return None


class _NextData(HTMLParser):
    def __init__(self):
        super().__init__(); self.active = False; self.parts = []
    def handle_starttag(self, tag, attrs):
        if tag == 'script' and dict(attrs).get('id') == '__NEXT_DATA__': self.active = True
    def handle_endtag(self, tag):
        if tag == 'script': self.active = False
    def handle_data(self, data):
        if self.active: self.parts.append(data)


def enrich_detail(item, page):
    """Lê o JSON da página pública; não infere país nem substitui identidade."""
    if not isinstance(page, str) or len(page) > 10_000_000: raise ValueError('Página Gupy inválida')
    parser = _NextData(); parser.feed(page)
    try:
        job = json.loads(''.join(parser.parts))['props']['pageProps']['job']
        if not isinstance(job, dict) or str(job.get('id')) != str(item['id']): raise ValueError('Identidade divergente')
        if not isinstance(job.get('description'), str) or not job['description'].strip(): raise ValueError('Descrição ausente')
    except (ValueError, KeyError, TypeError):
        raise ValueError('Detalhe Gupy inválido') from None
    from core import clean
    result = dict(item)
    result['detail_enriched'] = True
    result['description'] = '\n\n'.join(clean(job.get(k)) for k in ('description','responsibilities','prerequisites','relevantExperiences') if clean(job.get(k)))
    location = ', '.join(str(job[k]).strip() for k in ('addressCity','addressState') if isinstance(job.get(k),str) and job[k].strip())
    if location: result['location'] = location
    country = job.get('addressCountry')
    if explicit_country(country): result['country'] = explicit_country(country)
    return result


def build_url(query, contract='internship', limit=25, offset=0, city='', state='', workplace=''):
    if contract not in CONTRACTS:
        raise ValueError('Categoria não permitida')
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError('Limite inválido')
    if type(offset) is not int or offset < 0:
        raise ValueError('Deslocamento inválido')
    if workplace not in ('', 'remote', 'hybrid', 'on-site'):
        raise ValueError('Modalidade inválida')
    params = {'jobName': str(query)[:80], 'type': CONTRACTS[contract],
              'limit': str(limit), 'offset': str(offset)}
    if city:
        params['city'] = city
    if state:
        params['state'] = state
    if workplace:
        params['workplaceType'] = workplace
    return ENDPOINT + '?' + urlencode(params)


def safe_job_url(value):
    if not isinstance(value, str) or not value:
        return ''
    url = urljoin('https://portal.gupy.io/', value)
    try:
        parsed = urlparse(url)
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username is not None
                or parsed.password is not None or parsed.port not in (None, 443)
                or parsed.path in ('','/')):
            return ''
    except ValueError:
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
    parsed = urlparse(url)
    company = (parsed.hostname or '').removesuffix('.gupy.io')
    job_id = str(raw['id'])
    if (parsed.path.startswith('/job/') and re.fullmatch(r'[0-9]+', job_id)
            and re.fullmatch(r'[a-z0-9](?:[a-z0-9-]*[a-z0-9])?', company)
            and company not in {'portal', 'login', 'api', 'www', 'attachments', 'suporte-candidatos', 'pravoce'}
            and parsed.hostname == company + '.gupy.io'):
        url = f'https://{company}.gupy.io/jobs/{job_id}'
    city = str(raw.get('city') or '').strip()
    state = str(raw.get('state') or '').strip()
    return {
        'id': str(raw['id']), 'title': str(raw['name']),
        'company': str(raw.get('careerPageName') or ''),
        'description': str(raw.get('description') or ''),
        'location': ', '.join(v for v in (city, state) if v),
        'country': explicit_country(raw.get('country')),
        'mode': MODES.get(raw.get('workplaceType'), 'unknown'),
        'kind': kind, 'url': url,
        'date': raw.get('publishedDate'),
    }


def fetch(query, contract='internship', pages=1, get_json=None, limit=25, **filters):
    if get_json is None:
        from core import get_json as get_json_impl
        get_json = get_json_impl
    if type(pages) is not int or not 1 <= pages <= 5:
        raise ValueError('Limite de páginas inválido')
    result = []
    raw_count = 0
    pages_fetched = 0
    duplicate_items = 0
    skipped_invalid_url = 0
    seen = set()
    for page in range(pages):
        offset = page * limit
        payload = get_json(build_url(query, contract=contract, limit=limit, offset=offset, **filters))
        if not isinstance(payload, dict) or not isinstance(payload.get('data'), list):
            raise ValueError('Resposta inesperada da Gupy')
        batch = payload['data']
        pages_fetched += 1
        if len(batch) > limit:
            raise ValueError('Página Gupy excede o limite solicitado')
        pagination = payload.get('pagination')
        if pagination is not None:
            if not isinstance(pagination, dict):
                raise ValueError('Paginação Gupy inválida')
            for field, expected in (('offset', offset), ('limit', limit)):
                if field in pagination and (type(pagination[field]) is not int or pagination[field] != expected):
                    raise ValueError('Paginação Gupy inconsistente')
            # A Gupy pode limitar o total informado mesmo existindo páginas posteriores.
            if 'total' in pagination and (type(pagination['total']) is not int or
                    pagination['total'] < 0 or (offset == 0 and batch and pagination['total'] < len(batch))):
                raise ValueError('Total Gupy inconsistente')
        raw_count += len(batch)
        for row in batch:
            if not isinstance(row, dict) or not row.get('id') or not row.get('name'):
                raise ValueError('Anúncio Gupy malformado')
            item = normalize_item(row, contract)
            if item is None and row.get('type') == CONTRACTS[contract]:
                skipped_invalid_url += 1
            if item is not None:
                ident = str(row['id'])
                if ident in seen:
                    duplicate_items += 1
                    continue
                seen.add(ident)
                result.append(item)
        if len(batch) < limit:
            break
    from providers_extra import ListingBatch
    # A consulta usa filtros e pode cobrir apenas uma fração do catálogo.
    batch = ListingBatch(result, complete=False, raw_count=raw_count)
    batch.pages_fetched = pages_fetched
    batch.page_limit = pages
    batch.duplicate_items = duplicate_items
    batch.skipped_invalid_url = skipped_invalid_url
    return batch
