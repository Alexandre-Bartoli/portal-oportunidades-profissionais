"""Descoberta conservadora de sistemas de recrutamento a partir de links públicos.

Apenas reconhece endereços de plataformas conhecidas. Não faz scraping,
não ativa conectores e não acessa URLs fornecidas em anúncios.
"""
import json
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

PROVIDERS = frozenset({'greenhouse', 'lever', 'ashby', 'smartrecruiters', 'breezy'})
SAFE_SLUG = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$')


def detect(url):
    if not isinstance(url, str):
        return None
    try:
        u = urlsplit(url.strip())
        if u.scheme != 'https' or u.username or u.password or u.port not in (None, 443):
            return None
    except ValueError:
        return None
    host = (u.hostname or '').lower()
    parts = [p for p in u.path.split('/') if p]
    if host in {'boards.greenhouse.io', 'job-boards.greenhouse.io', 'boards.eu.greenhouse.io'}:
        provider, slug = 'greenhouse', parts[0] if parts else ''
    elif host in {'jobs.lever.co', 'jobs.eu.lever.co'}:
        provider, slug = 'lever', parts[0] if parts else ''
    elif host == 'jobs.ashbyhq.com':
        provider, slug = 'ashby', parts[0] if parts else ''
    elif host in {'jobs.smartrecruiters.com', 'careers.smartrecruiters.com'}:
        provider, slug = 'smartrecruiters', parts[0] if parts else ''
    elif re.fullmatch(r'[a-z0-9][a-z0-9-]*\.breezy\.hr', host):
        provider, slug = 'breezy', host.split('.')[0]
    else:
        return None
    if not SAFE_SLUG.fullmatch(slug):
        return None
    return {'provider': provider, 'slug': slug}


class _Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []
    def handle_starttag(self, tag, attrs):
        if tag not in ('a', 'iframe'):
            return
        attributes = dict(attrs)
        value = attributes.get('href') or attributes.get('src')
        if isinstance(value, str):
            self.urls.append(value)


def from_html(page_url, html):
    """Extrai somente links de ATS; HTML deve vir de fonte autorizada."""
    if not isinstance(html, str) or len(html) > 1_000_000:
        raise ValueError('HTML inválido ou grande demais')
    page = urlsplit(page_url)
    if page.scheme != 'https' or not page.hostname:
        raise ValueError('Página de origem deve ser HTTPS')
    parser = _Links()
    parser.feed(html)
    return from_urls([urljoin(page_url, x) for x in parser.urls])


def from_urls(urls, configured=()):
    """Retorna sugestões, nunca configura automaticamente fontes ativas."""
    known = {(s['provider'], s['slug'].casefold()) for s in configured}
    suggestions = []
    for url in urls:
        hit = detect(url)
        if not hit:
            continue
        key = (hit['provider'], hit['slug'].casefold())
        if key not in known:
            suggestions.append({'provider': hit['provider'], 'slug': hit['slug'],
                'enabled': False, 'status': 'pendente_de_validacao', 'evidence_url': url})
            known.add(key)
    return suggestions


def from_database(db_connection, configured=()):
    """Descobre possíveis fontes a partir das URLs já coletadas, sem rede."""
    rows = db_connection.execute('SELECT url FROM jobs WHERE demo=0 AND url IS NOT NULL').fetchall()
    return from_urls([r[0] for r in rows], configured)