"""Importação de feeds brasileiros fornecidos por parceiros com autorização expressa.

Não descobre nem extrai páginas de portais. URLs são de feeds contratados/configurados.
"""
import csv
import io
import json
import os
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from brasil import PORTALS, import_rows

BASE = Path(__file__).resolve().parent


def load_configs(path=None):
    config_path = Path(path) if path else BASE / 'feeds_brasil.json'
    data = json.loads(config_path.read_text(encoding='utf-8'))
    return data.get('feeds', [])


def validate_feed(feed):
    portal = feed.get('portal', '')
    if portal not in PORTALS:
        raise ValueError('Portal desconhecido')
    url = feed.get('url', '')
    parsed = urlparse(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None,443):
        raise ValueError('Feed deve ter URL HTTPS válida')
    allowed = feed.get('allowed_host')
    if not allowed or parsed.hostname.lower() != allowed.lower():
        raise ValueError('Host do feed não corresponde ao host autorizado')
    if feed.get('format') not in ('csv', 'json'):
        raise ValueError('Formato não suportado (csv ou json)')
    return True


class NoRedirectHandler(__import__('urllib.request', fromlist=['HTTPRedirectHandler']).HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Redirecionamentos de feeds estão desativados')


def fetch_feed(feed):
    validate_feed(feed)
    import urllib.request
    headers = {'User-Agent':'PortalEstagiosInstitucional/0.2', 'Accept':'application/json, text/csv'}
    envvar = feed.get('token_env', '')
    if envvar:
        if not envvar.replace('_','').isalnum():
            raise ValueError('Nome de variável de ambiente inválido')
        token = os.environ.get(envvar)
        if not token:
            raise ValueError('Credencial ausente em variável de ambiente: ' + envvar)
        headers['Authorization'] = 'Bearer ' + token
    opener = urllib.request.build_opener(NoRedirectHandler)
    request = Request(feed['url'], headers=headers)
    with opener.open(request, timeout=20) as response:
        data = response.read(5_000_001)
    if len(data) > 5_000_000:
        raise ValueError('Feed excede limite de 5 MB')
    raw = data.decode('utf-8-sig')
    if feed['format'] == 'csv':
        return list(csv.DictReader(io.StringIO(raw)))
    obj = json.loads(raw)
    if isinstance(obj, dict):
        obj = obj.get(feed.get('items_key', 'jobs'))
    if not isinstance(obj, list) or any(not isinstance(x, dict) for x in obj):
        raise ValueError('JSON deve conter lista de vagas')
    mapping = feed.get('field_map', {})
    return [{field: item.get(original, '') for field, original in mapping.items()} if mapping else item for item in obj]


def collect_feed(feed):
    if not feed.get('enabled', False):
        return 0
    rows = fetch_feed(feed)
    # O provedor é fixado na configuração, não confiamos em campo vindo do feed.
    for row in rows:
        row['portal'] = feed['portal']
    return import_rows(rows)