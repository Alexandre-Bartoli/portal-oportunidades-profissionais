"""Adaptadores experimentais independentes, desabilitados até revisão das fontes.

Padrões consultados: Job Pindorama (MIT), Career Ops (MIT). Nenhuma vaga
é retornada por padrão e respostas de teste não validam acessos reais.
"""
import re
import unicodedata
from urllib.parse import quote, urlencode, urlsplit

from providers_extra import ListingBatch


def _safe_url(value, allowed):
    if not isinstance(value, str):
        return False
    try:
        p=urlsplit(value)
        host=p.hostname or ''
        return (p.scheme=='https' and not p.username and not p.password and
                p.port in (None,443) and p.path not in ('','/') and
                any(host==x or host.endswith('.'+x) for x in allowed))
    except ValueError:
        return False


def _kind(title, contract):
    from core import category
    code=''.join(c for c in unicodedata.normalize('NFKD',str(contract or '').casefold())
                 if not unicodedata.combining(c)).strip().replace('_',' ')
    values={'estagio':'internship','internship':'internship','intern':'internship',
            'temporario':'temporary','temporaria':'temporary','temporary':'temporary',
            'clt':'employment','efetivo':'employment','efetiva':'employment',
            'pj':'employment','full time':'employment','part time':'employment'}
    return values.get(code) or category(str(title or ''))


def fetch(provider, slug, get_json):
    if provider=='remotive':
        if slug!='feed':raise ValueError('Identificador Remotive inválido')
        payload=get_json('https://remotive.com/api/remote-jobs')
        rows=payload.get('jobs') if isinstance(payload,dict) else None
    elif provider=='workable':
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}',slug):raise ValueError('Identificador Workable inválido')
        payload=get_json('https://apply.workable.com/api/v1/widget/accounts/'+quote(slug,safe='')+'?details=true')
        rows=payload.get('jobs') if isinstance(payload,dict) else None
    elif provider=='solides':
        if slug not in ('estagio','emprego','temporario'):raise ValueError('Consulta Sólides inválida')
        params=urlencode({'page':1,'take':20,'title':{'estagio':'estágio','emprego':'','temporario':'temporário'}[slug]})
        payload=get_json('https://vagas.solides.com.br/api/vacancies?'+params)
        rows=payload.get('data') if isinstance(payload,dict) else None
    else:
        raise ValueError('Fonte desconhecida')
    if not isinstance(rows,list):raise ValueError('Resposta da fonte inválida')
    output=[]; seen=set()
    for row in rows:
        if not isinstance(row,dict):raise ValueError('Anúncio malformado')
        ident=row.get('shortcode') if provider=='workable' else row.get('id')
        title=row.get('title')
        if not ident or not isinstance(title,str) or not title.strip():raise ValueError('Anúncio sem identidade ou título')
        ident=str(ident)
        if ident in seen:raise ValueError('Identidade repetida na resposta')
        seen.add(ident)
        if provider=='solides':
            contracts=row.get('recruitmentContractType') or []
            if not isinstance(contracts,list):raise ValueError('Tipo de contrato inválido')
            kinds={_kind('', x.get('name')) for x in contracts if isinstance(x,dict)}-{'other'}
            kind=next(iter(kinds)) if len(kinds)==1 else (_kind(title,'') if not kinds else 'other')
            if ident.isdigit():
                url='https://vagas.solides.com.br/vaga/'+ident
            else:
                publisher=row.get('publishers') or {}
                url=(publisher.get('rhgestor') or {}).get('redirectUrl','') if isinstance(publisher,dict) else ''
            allowed=('vagas.solides.com.br','rhgestor.com.br')
            city=row.get('city') or {}; state=row.get('state') or {}
            location=', '.join(str(x) for x in (city.get('name') if isinstance(city,dict) else None,
                state.get('code') if isinstance(state,dict) else None) if x)
            mode={'remoto':'remote','hibrido':'hybrid','presencial':'onsite'}.get(str(row.get('jobType') or '').casefold(),'unknown')
            country=None
        elif provider=='remotive':
            kind=_kind(title,row.get('job_type'));url=row.get('url','')
            allowed=('remotive.com',);restriction=row.get('candidate_required_location')
            location='Elegibilidade geográfica informada: '+restriction if isinstance(restriction,str) and restriction.strip() else ''
            mode='remote';country=None
        else:
            kind=_kind(title,row.get('employment_type'));url=row.get('url') or row.get('shortlink') or ''
            allowed=('workable.com',);location=', '.join(str(row.get(k) or '') for k in ('city','state') if row.get(k))
            mode='remote' if row.get('telecommuting') is True else 'unknown'
            raw_country=row.get('country')
            country=raw_country.upper() if isinstance(raw_country,str) and re.fullmatch(r'[A-Za-z]{2}',raw_country) else None
        if kind=='other':continue
        if not _safe_url(url,allowed):raise ValueError('Endereço de anúncio não autorizado')
        company=row.get('companyName') if provider=='solides' else row.get('company_name') if provider=='remotive' else payload.get('name')
        published=row.get('createdAt') if provider=='solides' else row.get('publication_date') if provider=='remotive' else row.get('published_on')
        output.append({'id':ident,'title':title,'description':str(row.get('description') or ''),
                       'url':url,'location':location,'country':country,'mode':mode,'kind':kind,
                       'company':company,'published_at':published})
    # Consultas filtradas ou feeds sem prova de inventário completo nunca expiram vagas.
    return ListingBatch(output,complete=False,raw_count=len(rows))
