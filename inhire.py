"""Adaptador InHire inspirado em Radar de Vagas (licença MIT)."""
import re
import unicodedata
from urllib.parse import quote

from providers_extra import ListingBatch
from fontes_novas import _kind

BASE = 'https://api.inhire.app/job-posts/public/pages'
SAFE = re.compile(r'^[A-Za-z0-9](?:[A-Za-z0-9-]{0,78}[A-Za-z0-9])?$')
MAX_DETAILS = 50

def fetch(slug, get_json):
    if not isinstance(slug, str) or not SAFE.fullmatch(slug):
        raise ValueError('Identificador InHire inválido')
    headers = {'X-Tenant': slug}
    payload = get_json(BASE, headers=headers)
    if not isinstance(payload, dict) or not isinstance(payload.get('jobsPage'), list):
        raise ValueError('Listagem InHire inválida')
    rows = payload['jobsPage']
    output = []
    seen = set()
    for item in rows[:MAX_DETAILS]:
        ident = item.get('jobId') if isinstance(item, dict) else None
        if not isinstance(ident, (str, int)) or isinstance(ident, bool) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', str(ident)):
            raise ValueError('Identificador de vaga InHire inválido')
        ident = str(ident)
        if ident in seen:
            raise ValueError('Identificador InHire repetido')
        seen.add(ident)
        job = get_json(BASE+'/'+quote(ident, safe=''), headers=headers)
        if not isinstance(job, dict) or not isinstance(job.get('displayName'), str) or not job['displayName'].strip():
            raise ValueError('Detalhe InHire inválido')
        if job.get('jobId') is not None and str(job['jobId']) != ident:
            raise ValueError('Identidade InHire divergente')
        if not isinstance(job.get('description'), str) or not job['description'].strip():
            raise ValueError('Descrição InHire ausente')
        title = job['displayName'].strip()
        contracts = job.get('contractType') or []
        if isinstance(contracts, str): contracts = [contracts]
        if not isinstance(contracts, list): raise ValueError('Contrato InHire inválido')
        kinds = {_kind('', value) for value in contracts if isinstance(value, str)} - {'other'}
        kind = next(iter(kinds)) if len(kinds) == 1 else _kind(title, '') if not kinds else 'other'
        if kind == 'other': continue
        name = unicodedata.normalize('NFKD', title).encode('ascii','ignore').decode().lower()
        title_slug = re.sub(r'[^a-z0-9]+','-', name).strip('-') or 'vaga'
        mode = {'remote':'remote','hybrid':'hybrid','onsite':'onsite','on-site':'onsite'}.get(str(job.get('workplaceType') or '').lower(),'unknown')
        location = job.get('location') if isinstance(job.get('location'), str) else ''
        country = 'BR' if re.search(r',\s*BR\s*$', location, re.IGNORECASE) else None
        output.append({'id':ident,'title':title,'company':job.get('tenantName') or payload.get('tenantName'),
                       'description':str(job.get('description') or ''),
                       'url':f'https://{slug.lower()}.inhire.app/vagas/{quote(ident,safe="")}/{title_slug}',
                       'location':location,'country':country,'mode':mode,'kind':kind,
                       'published_at':job.get('publishedAt')})
    return ListingBatch(output, complete=False, raw_count=len(rows))
