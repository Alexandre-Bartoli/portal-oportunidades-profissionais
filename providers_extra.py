"""Conectores experimentais de quadros públicos de vagas.

Referências de arquitetura: career-ops (MIT). Implementação própria em Python.
Não habilitar sem verificar as condições de uso e realizar um teste real.
"""
import json
import re
import urllib.error
import urllib.parse
import urllib.request


class ListingBatch(list):
    """Lista com indicador de inventário completo ou parcial."""
    def __init__(self, items=(), complete=True, raw_count=None):
        super().__init__(items)
        self.complete = complete
        self.raw_count = raw_count


SLUG = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$')


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def read_public_json(url):
    """Requisição sem redirecionamentos automáticos para outro domínio."""
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port:
        raise ValueError('URL do provedor inválida')
    host = parsed.hostname or ''
    if host != 'api.smartrecruiters.com' and not re.fullmatch(
            r'[a-z0-9][a-z0-9-]*\.breezy\.hr', host):
        raise ValueError('Domínio de provedor não permitido')
    req = urllib.request.Request(url, headers={
        'User-Agent': 'PortalOportunidades/0.6 (public-job-catalog)',
        'Accept': 'application/json'})
    opener = urllib.request.build_opener(_NoRedirect())
    with opener.open(req, timeout=20) as response:
        if response.status != 200:
            raise ValueError('Resposta HTTP inesperada')
        # Limite de tamanho para proteger o servidor local.
        body = response.read(5_000_001)
        if len(body) > 5_000_000:
            raise ValueError('Resposta excede o tamanho permitido')
        return json.loads(body.decode('utf-8'))


def _kind(value):
    from core import category
    code = value.get('label') if isinstance(value, dict) else value
    return category('', employment_type=str(code or ''))


def smartrecruiters(slug, get_json=read_public_json, max_pages=2):
    """Consulta limitada da API pública por organização; retorna vagas normalizadas."""
    if not isinstance(slug, str) or not SLUG.fullmatch(slug):
        raise ValueError('Identificador SmartRecruiters inválido')
    if not isinstance(max_pages, int) or not 1 <= max_pages <= 5:
        raise ValueError('Limite de páginas inválido')
    output = []
    raw_count = 0
    for index in range(max_pages):
        url = (f'https://api.smartrecruiters.com/v1/companies/{slug}/postings'
               f'?limit=100&offset={100 * index}&status=PUBLIC')
        response = get_json(url)
        if not isinstance(response, dict) or not isinstance(response.get('content'), list):
            raise ValueError('Resposta SmartRecruiters inválida')
        rows = response['content']
        raw_count += len(rows)
        for row in rows:
            if not isinstance(row, dict) or not row.get('id') or not row.get('name'):
                continue
            kind = _kind(row.get('typeOfEmployment'))
            if kind == 'other':
                # Sem tipo explicitamente reconhecido, não inventar categoria.
                from core import category
                kind = category(str(row['name']))
            if kind == 'other':
                continue
            location = row.get('location') or {}
            if not isinstance(location, dict):
                location = {}
            place = location.get('fullLocation') or ', '.join(str(location.get(k) or '')
                for k in ('city', 'region', 'country') if location.get(k))
            country = str(location.get('country') or '').upper() or None
            if country in ('BRA', 'BRAZIL', 'BRASIL'):
                country = 'BR'
            if country and len(country) != 2:
                country = None
            output.append({'id': str(row['id']), 'title': str(row['name']),
                'description': '', 'location': str(place), 'country': country,
                'mode': 'remote' if location.get('remote') is True else 'unknown',
                'url': f'https://jobs.smartrecruiters.com/{slug}/{urllib.parse.quote(str(row["id"]), safe="")}',
                'kind': kind})
        if len(rows) < 100:
            break
    complete = len(rows) < 100
    return ListingBatch(output, complete=complete, raw_count=raw_count)


def breezy(slug, get_json=read_public_json):
    """Consulta do feed público de um único tenant Breezy."""
    if not isinstance(slug, str) or not SLUG.fullmatch(slug):
        raise ValueError('Identificador Breezy inválido')
    response = get_json(f'https://{slug.lower()}.breezy.hr/json')
    if not isinstance(response, list):
        raise ValueError('Resposta Breezy inválida')
    result = []
    for row in response:
        if not isinstance(row, dict) or not row.get('name'):
            continue
        url = row.get('url')
        try:
            parsed = urllib.parse.urlsplit(url) if isinstance(url, str) else None
            if (not parsed or parsed.scheme != 'https' or parsed.hostname != f'{slug.lower()}.breezy.hr'
                    or parsed.username or parsed.password or parsed.port not in (None, 443)):
                continue
        except ValueError:
            continue
        location = row.get('location') or {}
        if not isinstance(location, dict):
            location = {}
        country = location.get('country') or {}
        country_name = country.get('name', '') if isinstance(country, dict) else country
        place = location.get('name') or ', '.join(str(x) for x in
            (location.get('city'), location.get('state'), country_name) if x)
        kind = _kind(row.get('employment_type') or row.get('type'))
        if kind == 'other':
            from core import category
            kind = category(str(row['name']))
        if kind == 'other':
            continue
        result.append({'id': str(row.get('id') or parsed.path),
            'title': str(row['name']), 'description': str(row.get('description') or ''),
            'url': url, 'location': str(place), 'country': None,
            'mode': 'remote' if location.get('is_remote') else 'unknown', 'kind': kind})
    return ListingBatch(result, complete=True, raw_count=len(response))
