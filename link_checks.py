"""Verificação opcional e conservadora de URLs de candidatura em homologação.

Nunca segue redirecionamentos, nunca acessa hosts desconhecidos e nunca altera
qualquer vaga. HTTP 200 só prova resposta HTTP, não vaga aberta.
"""
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from source_reviews import source_review
from source_quality import validate_sources
from stage_storage import write_private_report


HOSTS = {
    'lever': re.compile(r'^jobs\.lever\.co$'),
    'ashby': re.compile(r'^jobs\.ashbyhq\.com$'),
    'greenhouse': re.compile(r'^(?:boards|job-boards)\.greenhouse\.io$'),
    'smartrecruiters': re.compile(r'^jobs\.smartrecruiters\.com$'),
    'breezy': re.compile(r'^[a-z0-9][a-z0-9-]*\.breezy\.hr$'),
    'gupy': re.compile(r'^[a-z0-9][a-z0-9-]*\.gupy\.io$'),
    'inhire': re.compile(r'^[a-z0-9][a-z0-9-]*\.inhire\.app$'),
}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def allowed_link(provider, url):
    if not isinstance(url, str) or len(url) > 2048:
        return False
    try:
        p = urlsplit(url)
        hostname = p.hostname or ''
        return (p.scheme == 'https' and not p.username and not p.password
                and p.port in (None, 443) and p.fragment == ''
                and bool(HOSTS.get(provider, re.compile(r'a^')).fullmatch(hostname))
                and bool(p.path) and p.path != '/')
    except (ValueError, TypeError):
        return False


def check_link(provider, url, *, opener=None, timeout=6):
    """Uma única requisição HEAD; respostas 30x não são seguidas."""
    if not allowed_link(provider, url):
        return {'status':'unsupported_host','http_status':None}
    opener = opener or urllib.request.build_opener(_NoRedirect(), urllib.request.ProxyHandler({}))
    request = urllib.request.Request(url, method='HEAD', headers={
        'User-Agent':'PortalOportunidades-StagingLinkAudit/0.9',
        'Accept':'text/html,application/xhtml+xml',
    })
    try:
        with opener.open(request, timeout=timeout) as response:
            code = response.status
    except urllib.error.HTTPError as exc:
        code = exc.code
        exc.close()
    except (urllib.error.URLError, TimeoutError, OSError):
        return {'status':'network_unverified','http_status':None}
    if code == 200:
        label = 'http_reachable_unverified'
    elif code in (404, 410):
        label = 'not_found_unverified'
    elif code in (401, 403):
        label = 'access_restricted'
    elif code == 429:
        label = 'rate_limited'
    elif code in (405, 501):
        label = 'head_unsupported'
    elif 300 <= code < 400:
        label = 'redirect_not_followed'
    else:
        label = 'uncertain_http_status'
    return {'status':label, 'http_status':code}


def sample_jobs(db_path, *, limit=12):
    if type(limit) is not int or not 1 <= limit <= 30:
        raise ValueError('O limite precisa estar entre 1 e 30')
    db_path = Path(db_path)
    if not db_path.is_file():
        raise FileNotFoundError('Banco de homologação ainda não existe')
    with sqlite3.connect(db_path.as_uri() + '?mode=ro', uri=True) as db:
        # SQL faz a distribuição por fonte antes do LIMIT, sem consumir memória
        # com milhares de vagas pertencentes a um único quadro.
        rows = db.execute('''SELECT id,provider,source,url FROM (
            SELECT id,provider,source,url,ROW_NUMBER() OVER (
                PARTITION BY provider,source ORDER BY last_seen DESC,id) AS pos
            FROM jobs WHERE active=1 AND demo=0
        ) ORDER BY pos,provider,source,id LIMIT ?''', (limit,)).fetchall()
    return rows


def audit_links(db_path, config, *, limit=12, network=False, checker=None, report_path=None):
    validate_sources(config)
    reviews = {(s['provider'], s['slug']): source_review(s) for s in config['sources']}
    rows = sample_jobs(db_path, limit=limit)
    if checker is None:
        checker = check_link
    entries = []
    for jid, provider, source, url in rows:
        review = reviews.get((provider,source), {'technical_probe_allowed':False})
        if not allowed_link(provider,url):
            outcome = {'status':'unsupported_host', 'http_status':None}
        elif not network:
            outcome = {'status':'not_checked', 'http_status':None}
        elif not review['technical_probe_allowed']:
            outcome = {'status':'pending_source_review', 'http_status':None}
        else:
            outcome = checker(provider,url)
        entries.append({'job_id_prefix':str(jid)[:12], 'source':provider+'/'+source,
                        'status':outcome['status'], 'http_status':outcome.get('http_status')})
    counts = dict(Counter(e['status'] for e in entries))
    result = {'schema_version':1, 'checked_at':datetime.now(timezone.utc).isoformat(),
              'network_requested':bool(network), 'sampled':len(entries),'statuses':counts,'results':entries,
              'note':'HEAD não comprova inscrição aberta; dados não são alterados; URLs não constam neste relatório.'}
    if report_path:
        write_private_report(result,report_path)
    return result
