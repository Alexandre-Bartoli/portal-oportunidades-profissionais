import hashlib
import os
import stat
from contextlib import contextmanager
import html
import json
import re
import sqlite3
import urllib.parse
import urllib.request
import urllib.error
import time
from datetime import datetime, timezone
from pathlib import Path
from listing_identity import canonical_url

BASE = Path(__file__).resolve().parent
DB = BASE / 'data' / 'jobs.sqlite3'
WORDS = re.compile(r'\b(internship|intern|internship program|estagio|estagiario|estagiaria|estagiarios|estagiarias|programa de estagio|summer internship|practicante|pasantia|praktikum|stage)\b', re.I)
NEGATIVE = re.compile(r'\b(senior|sr\.|manager|gerente|director|diretor|trainee|apprentice|junior software engineer)\b', re.I)
AREAS = {
 'Tecnologia': ['software','developer','desenvolvimento','programacao','data science','dados','cybersecurity','seguranca da informacao'],
 'Administração': ['administration','administracao','business operations','administrativo','finance','financas','accounting','contabilidade'],
 'Saúde': ['nursing','enfermagem','psychology','psicologia','nutrition','nutricao','pharmacy','farmacia','healthcare'],
 'Educação': ['education','educacao','teaching','professor','pedagogia','teacher'],
 'Agropecuária': ['agriculture','agronomy','agronomia','agricultura','veterinary','veterinaria','animal science'],
 'Engenharias': ['engineering','engenharia','mechanical','civil engineering','electrical'],
 'Comunicação': ['journalism','jornalismo','communication','comunicacao','marketing','design'],
 'Direito': ['law','legal','direito','juridico'],
}

def clean(value):
 return html.unescape(re.sub(r'<[^>]+>',' ',str(value or ''))).strip()

def normalize_text(value):
 import unicodedata
 return ''.join(ch for ch in unicodedata.normalize('NFKD', (value or '').lower()) if not unicodedata.combining(ch))

def normalize_country(value):
 """Converte apenas países informados explicitamente; regiões ficam desconhecidas."""
 if not isinstance(value,str):return None
 text=normalize_text(value.strip())
 names={'brasil':'BR','brazil':'BR','canada':'CA','united states':'US',
  'estados unidos':'US','united kingdom':'GB','reino unido':'GB','uk':'GB',
  'france':'FR','franca':'FR','germany':'DE','alemanha':'DE','south korea':'KR',
  'japan':'JP','japao':'JP','singapore':'SG','united arab emirates':'AE',
  'sweden':'SE','suecia':'SE','saudi arabia':'SA','australia':'AU',
  'ireland':'IE','irlanda':'IE','italy':'IT','italia':'IT','portugal':'PT',
  'spain':'ES','espanha':'ES','netherlands':'NL','holanda':'NL'}
 if text in names:return names[text]
 if text == 'eu':return None
 return text.upper() if re.fullmatch(r'[a-z]{2}',text) else None

def valid_publication_date(value):
 if not isinstance(value,str) or not value or len(value)>40:return None
 try:datetime.fromisoformat(value.replace('Z','+00:00'))
 except ValueError:return None
 return value

def classify(title,description=''):
 t=normalize_text(title)
 if NEGATIVE.search(t): return 'other','review'
 if WORDS.search(t): return 'internship','review'
 return 'other','review'

def category(title, description='', employment_type=''):
 """Classificação conservadora em três tipos; desconhecido fica em revisão."""
 code=normalize_text(employment_type).strip()
 if code in ('vacancy_type_internship','internship','intern','estagio'):
  return 'internship'
 if code in ('vacancy_type_temporary','temporary','temporario','fixed term'):
  return 'temporary'
 if code in ('vacancy_type_effective','effective','clt','permanent','full-time','full time','fulltime','part-time','part time','parttime','pj','fixed-term permanent'):
  return 'employment'
 t=normalize_text(title)
 if WORDS.search(t):return 'internship'
 if re.search(r'\b(temporario|temporaria|temporary|seasonal|sazonal)\b',t):return 'temporary'
 if re.search(r'\b(trainee|aprendiz|voluntario|bolsa de pesquisa)\b',t):return 'other'
 return 'other'

def areas_for(title,description=''):
 text=normalize_text(title+' '+description)
 return sorted([area for area,keywords in AREAS.items() if any(normalize_text(k) in text for k in keywords)])

def make_job(provider,source,raw):
 if provider=='greenhouse':
  title=raw.get('title',''); description=clean(raw.get('content','')); url=raw.get('absolute_url','')
  location=(raw.get('location') or {}).get('name',''); extid=str(raw.get('id',''))
  country=None; mode='unknown'
 elif provider=='lever':
  title=raw.get('text',''); description=clean(raw.get('descriptionPlain') or raw.get('description',''))
  url=raw.get('hostedUrl') or raw.get('applyUrl') or ''
  cats=raw.get('categories') or {};location=cats.get('location','')
  extid=str(raw.get('id',''));country=raw.get('country');mode={'on-site':'onsite','remote':'remote','hybrid':'hybrid'}.get(raw.get('workplaceType'),'unknown')
 elif provider=='ashby':
  title=raw.get('title','');description=clean(raw.get('descriptionPlain') or raw.get('descriptionHtml') or '')
  url=raw.get('jobUrl') or raw.get('applyUrl') or '';location=raw.get('location','')
  extid=str(raw.get('id') or raw.get('jobUrl') or '')
  address=raw.get('address') or {};postal=address.get('postalAddress') or {}
  country=postal.get('addressCountry');mode={'Remote':'remote','Hybrid':'hybrid','OnSite':'onsite'}.get(raw.get('workplaceType'),'unknown')
 elif provider in ('smartrecruiters','breezy','solides','remotive','workable','inhire'):
  title=raw.get('title','');description=clean(raw.get('description',''));url=raw.get('url','')
  location=raw.get('location','');extid=str(raw.get('id',''));country=raw.get('country')
  mode=raw.get('mode','unknown')
 elif provider=='gupy':
  title=raw.get('title','');description=clean(raw.get('description',''));url=raw.get('url','')
  location=raw.get('location','');extid=str(raw.get('id',''));country=raw.get('country')
  mode=raw.get('mode','unknown')
 else: raise ValueError('Fonte desconhecida')
 country=normalize_country(country)
 if not title or not url or not url.startswith('https://'): return None
 employment = str(raw.get('employmentType') or (raw.get('categories') or {}).get('commitment') or '')
 kind = raw.get('kind') if provider in ('gupy','smartrecruiters','breezy','solides','remotive','workable','inhire') else category(title,description,employment)
 if kind=='other':return None
 review='review'
 fingerprint=hashlib.sha256((provider+'|'+source+'|'+extid+'|'+url).encode()).hexdigest()
 from geografia import locate
 company=raw.get('company')
 company=clean(company)[:200] or None if isinstance(company,str) else None
 published_at=valid_publication_date(raw.get('published_at') or raw.get('date') or (raw.get('publishedAt') if provider=='ashby' else None))
 return {'id':fingerprint,'provider':provider,'source':source,'external_id':extid,'title':clean(title),
 'description':description[:12000],'url':url,'location':clean(location),'country':country,
 'mode':mode,'kind':kind,'review_status':review,'areas':areas_for(title,description),
 'last_seen':datetime.now(timezone.utc).isoformat(),'demo':0,
 'geo_municipio':locate(clean(location),country) if mode!='remote' else None,
 'company':company,'published_at':published_at,'detail_enriched':provider=='gupy' and raw.get('detail_enriched') is True}

class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
 def redirect_request(self, req, fp, code, msg, headers, newurl):
  return None


def get_json(url, attempts=None, wait=time.sleep, headers=None):
 """Consulta HTTPS com tentativas limitadas para falhas transitórias."""
 if attempts is None:
  attempts = max(1, min(int(os.getenv('PORTAL_HTTP_ATTEMPTS', '3')), 3))
 timeout = max(3, min(int(os.getenv('PORTAL_HTTP_TIMEOUT', '20')), 20))
 try:
  parsed=urllib.parse.urlsplit(url)
  if (parsed.scheme!='https' or parsed.hostname not in {'boards-api.greenhouse.io','api.lever.co','api.ashbyhq.com','portal.gupy.io','vagas.solides.com.br','remotive.com','apply.workable.com','api.inhire.app'}
      or parsed.username is not None or parsed.password is not None or parsed.port not in (None,443)):
   raise ValueError('Endereço de provedor não permitido')
 except (TypeError,ValueError):
  raise ValueError('Endereço de provedor não permitido') from None
 if headers is not None and (parsed.hostname != 'api.inhire.app' or set(headers) != {'X-Tenant'} or not isinstance(headers['X-Tenant'],str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}',headers['X-Tenant'])):
  raise ValueError('Cabeçalho de provedor inválido')
 request=urllib.request.Request(url,headers={'User-Agent':'PortalOportunidades/0.7 (research prototype)','Accept':'application/json',**(headers or {})})
 opener=urllib.request.build_opener(NoRedirectHandler())
 for attempt in range(attempts):
  try:
   with opener.open(request, timeout=timeout) as response:
    body=response.read(10_000_001)
    if len(body)>10_000_000:raise ValueError('Resposta excede o limite permitido')
    return json.loads(body)
  except urllib.error.HTTPError as exc:
   if exc.code not in (429,500,502,503,504) or attempt==attempts-1:
    raise
  except (urllib.error.URLError, TimeoutError, ConnectionError):
   if attempt==attempts-1:
    raise
  wait(min(2**attempt,4))
 raise RuntimeError('Tentativas de consulta esgotadas')

def get_gupy_detail(url):
 """Obtém apenas página de vaga Gupy identificada, sem seguir redirecionamentos."""
 try:
  p=urllib.parse.urlsplit(url)
  if (p.scheme!='https' or p.username is not None or p.password is not None or p.port not in (None,443)
      or not re.fullmatch(r'[a-z0-9][a-z0-9-]*\.gupy\.io',p.hostname or '')
      or (p.hostname or '').split('.')[0] in {'portal','login','api','www','attachments','suporte-candidatos','pravoce'}
      or not re.fullmatch(r'/jobs/[0-9]+',p.path) or p.query or p.fragment):
   raise ValueError('Endereço de detalhe Gupy inválido')
 except (ValueError, TypeError): raise ValueError('Endereço de detalhe Gupy inválido') from None
 request=urllib.request.Request(url,headers={'User-Agent':'PortalOportunidades/0.9','Accept':'text/html'})
 with urllib.request.build_opener(NoRedirectHandler()).open(request,timeout=8) as response:
  body=response.read(10_000_001)
  if len(body)>10_000_000: raise ValueError('Página Gupy excede o limite')
  return body.decode('utf-8')

def select_gupy_details(slug, raws, limit=3):
 """Prioriza anúncios ainda sem detalhe, sem alterar banco durante a consulta."""
 enriched=set()
 if DB.is_file():
  try:
   with sqlite3.connect(DB.resolve().as_uri()+'?mode=ro',uri=True) as db:
    enriched={str(r[0]) for r in db.execute('''SELECT a.external_id FROM job_aliases a
     JOIN jobs j ON j.id=a.job_id WHERE a.provider=? AND a.source=? AND j.detail_enriched=1''',('gupy',slug))}
  except sqlite3.Error:
   enriched=set()
 new=[r for r in raws if r['id'] not in enriched]
 old=[r for r in raws if r['id'] in enriched]
 return (new+old)[:limit]

def fetch_source(provider,slug, *, detail_limit=None, query_text='', city='', workplace='', progress_callback=None):
 encoded=urllib.parse.quote(slug,safe='')
 if provider=='inhire':
  from inhire import fetch
  from providers_extra import ListingBatch
  rows=fetch(slug, get_json)
  return ListingBatch([job for raw in rows if (job:=make_job(provider,slug,raw)) is not None],complete=False,raw_count=rows.raw_count)
 if provider in ('solides','remotive','workable'):
  from fontes_novas import fetch
  from providers_extra import ListingBatch
  if provider=='remotive':
   from source_limits import acquire
   acquire('remotive',BASE/'data'/'source_rate_limits.sqlite3')
   getter=lambda url:get_json(url,attempts=1)
  else:getter=get_json
  rows=fetch(provider,slug,getter)
  return ListingBatch([job for raw in rows if (job:=make_job(provider,slug,raw)) is not None],
                      complete=False,raw_count=rows.raw_count)
 if provider=='gupy':
  from gupy import fetch, enrich_detail, source_parameters
  contract,state=source_parameters(slug)
  from providers_extra import ListingBatch
  if not isinstance(query_text,str) or len(query_text)>100 or not isinstance(city,str) or len(city)>150:
   raise ValueError('Filtro de busca inválido')
  raws=fetch(query_text,contract=contract,pages=1 if state else 5,limit=25,get_json=get_json,state=state,city=city,workplace=workplace)
  # Detalhes limitados por rodada. Falhas individuais preservam a listagem.
  detail_ok=0
  if detail_limit is not None and (type(detail_limit) is not int or not 1<=detail_limit<=10):
   raise ValueError('Limite de detalhes Gupy inválido')
  selected=select_gupy_details(slug,raws,detail_limit if detail_limit is not None else (10 if state else 3))
  if progress_callback is not None:progress_callback(0,len(selected))
  indices={raw['id']:i for i,raw in enumerate(raws)}
  for index,raw in enumerate(selected):
   try:
    raws[indices[raw['id']]]=enrich_detail(raw,get_gupy_detail(raw['url']))
    detail_ok+=1
   except (ValueError, TypeError, KeyError, UnicodeError, urllib.error.URLError, TimeoutError, OSError): pass
   if progress_callback is not None:progress_callback(index+1,len(selected))
  batch=ListingBatch([job for raw in raws if (job:=make_job(provider,slug,raw)) is not None],
                      complete=False, raw_count=getattr(raws, 'raw_count', None))
  batch.details_attempted=len(selected);batch.details_succeeded=detail_ok
  batch.pages_fetched=raws.pages_fetched;batch.page_limit=raws.page_limit
  batch.duplicate_items=raws.duplicate_items;batch.skipped_invalid_url=raws.skipped_invalid_url
  return batch
 if provider in ('smartrecruiters','breezy'):
  from providers_extra import smartrecruiters, breezy
  raws = smartrecruiters(slug) if provider == 'smartrecruiters' else breezy(slug)
  from providers_extra import ListingBatch
  return ListingBatch([job for raw in raws if (job := make_job(provider, slug, raw)) is not None],
                      complete=getattr(raws, 'complete', True), raw_count=getattr(raws, 'raw_count', None))
 if provider=='greenhouse':
  data=get_json('https://boards-api.greenhouse.io/v1/boards/'+encoded+'/jobs?content=true');items=data.get('jobs') if isinstance(data,dict) else None
 elif provider=='lever':
  items=[];offset=0;complete=False
  while offset<2000:
   batch=get_json('https://api.lever.co/v0/postings/'+encoded+'?mode=json&skip='+str(offset)+'&limit=100')
   if not isinstance(batch,list):raise ValueError('Resposta inválida do Lever')
   items.extend(batch)
   if len(batch)<100:
    complete=True
    break
   offset+=100
 elif provider=='ashby':
  data=get_json('https://api.ashbyhq.com/posting-api/job-board/'+encoded);items=data.get('jobs') if isinstance(data,dict) else None
 else: raise ValueError('Provedor não permitido')
 if not isinstance(items,list):raise ValueError('Resposta inválida da fonte')
 if any(not isinstance(raw,dict) for raw in items):raise ValueError('Anúncio inválido na resposta')
 if provider=='ashby':items=[raw for raw in items if raw.get('isListed',True)]
 for raw in items:
  if provider=='greenhouse':title,url=raw.get('title'),raw.get('absolute_url')
  elif provider=='lever':title,url=raw.get('text'),raw.get('hostedUrl') or raw.get('applyUrl')
  else:title,url=raw.get('title'),raw.get('jobUrl') or raw.get('applyUrl')
  if not isinstance(title,str) or not title.strip() or not isinstance(url,str) or not url.startswith('https://'):
   raise ValueError('Anúncio sem título ou endereço válido')
 from providers_extra import ListingBatch
 return ListingBatch([j for raw in items if isinstance(raw,dict) and (j:=make_job(provider,slug,raw)) is not None],
                     complete=complete if provider=='lever' else True, raw_count=len(items))

@contextmanager
def connect():
 if DB.parent.is_symlink():raise ValueError('Diretório do banco não pode ser link simbólico')
 DB.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
 if os.name=='posix':os.chmod(DB.parent,0o700)
 if DB.is_symlink():raise ValueError('Banco não pode ser link simbólico')
 fd=os.open(DB,os.O_RDWR|os.O_CREAT|getattr(os,'O_NOFOLLOW',0),0o600)
 try:
  if not stat.S_ISREG(os.fstat(fd).st_mode):raise ValueError('Arquivo de banco inválido')
  if os.name=='posix':os.fchmod(fd,0o600)
 finally:os.close(fd)
 db=sqlite3.connect(DB)
 try:
  db.execute('PRAGMA foreign_keys=ON')
  with db:
   yield db
 finally:
  db.close()

def init():
 """Migração aditiva: preserva os IDs e registros existentes."""
 with connect() as db:
  db.execute('''CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, provider TEXT, source TEXT, external_id TEXT,
   title TEXT, description TEXT, url TEXT, location TEXT, country TEXT, mode TEXT, kind TEXT,
   review_status TEXT, areas TEXT, last_seen TEXT, demo INTEGER DEFAULT 0)''')
  columns={r[1] for r in db.execute('PRAGMA table_info(jobs)').fetchall()}
  if 'active' not in columns:db.execute('ALTER TABLE jobs ADD COLUMN active INTEGER DEFAULT 1')
  if 'misses' not in columns:db.execute('ALTER TABLE jobs ADD COLUMN misses INTEGER DEFAULT 0')
  if 'first_seen' not in columns:db.execute('ALTER TABLE jobs ADD COLUMN first_seen TEXT')
  if 'canonical_url' not in columns:db.execute('ALTER TABLE jobs ADD COLUMN canonical_url TEXT')
  if 'geo_municipio' not in columns:db.execute('ALTER TABLE jobs ADD COLUMN geo_municipio TEXT')
  if 'company' not in columns:db.execute('ALTER TABLE jobs ADD COLUMN company TEXT')
  if 'published_at' not in columns:db.execute('ALTER TABLE jobs ADD COLUMN published_at TEXT')
  if 'detail_enriched' not in columns:db.execute('ALTER TABLE jobs ADD COLUMN detail_enriched INTEGER NOT NULL DEFAULT 0')
  db.execute('UPDATE jobs SET first_seen=last_seen WHERE first_seen IS NULL')
  db.execute('''CREATE TABLE IF NOT EXISTS job_aliases (
    provider TEXT NOT NULL, source TEXT NOT NULL, external_id TEXT NOT NULL,
    source_job_id TEXT NOT NULL, job_id TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1, misses INTEGER NOT NULL DEFAULT 0,
    last_seen TEXT, PRIMARY KEY (provider, source, external_id),
    FOREIGN KEY(job_id) REFERENCES jobs(id))''')
  # Backfill uma única vez; a relação já coletada não perde seu identificador.
  if db.execute('PRAGMA user_version').fetchone()[0] < 1:
   for row in db.execute('SELECT id,provider,source,external_id,url,active,misses,last_seen,demo FROM jobs').fetchall():
    jid, provider, source, extid, url, active, misses, seen, demo=row
    db.execute('UPDATE jobs SET canonical_url=? WHERE id=?', (canonical_url(url) or '', jid))
    if not demo and provider and source:
     db.execute('''INSERT OR IGNORE INTO job_aliases
       (provider,source,external_id,source_job_id,job_id,active,misses,last_seen)
       VALUES (?,?,?,?,?,?,?,?)''',
       (provider,source,str(extid or jid),jid,jid,active or 0,misses or 0,seen))
   db.execute('PRAGMA user_version=1')
  if db.execute('PRAGMA user_version').fetchone()[0] < 2:
   db.execute('PRAGMA user_version=2')
  if db.execute('PRAGMA user_version').fetchone()[0] < 3:
   db.execute('PRAGMA user_version=3')
  if db.execute('PRAGMA user_version').fetchone()[0] < 4:
   db.execute('PRAGMA user_version=4')
  db.execute('CREATE INDEX IF NOT EXISTS ix_jobs_title ON jobs(title)')
  db.execute('CREATE INDEX IF NOT EXISTS ix_jobs_source ON jobs(provider, source, active)')
  db.execute('CREATE INDEX IF NOT EXISTS ix_jobs_canonical ON jobs(canonical_url, demo)')
  db.execute('CREATE INDEX IF NOT EXISTS ix_jobs_geo ON jobs(geo_municipio, active)')
  db.execute('CREATE INDEX IF NOT EXISTS ix_aliases_job ON job_aliases(job_id, active)')


def save(items):
 """Armazena uma vaga por URL canônica, mantendo proveniência por fonte.

 Não troca IDs legados. URLs iguais de fontes diferentes compartilham um job_id,
 mas permanecem registradas separadamente em job_aliases.
 """
 init()
 with connect() as db:
  for j in items:
   canonical = canonical_url(j['url']) or ''
   demo = int(j.get('demo',0))
   external_id = str(j.get('external_id') or j['id'])
   match = None
   if not demo:
    match=db.execute('SELECT job_id FROM job_aliases WHERE provider=? AND source=? AND external_id=?',
     (j['provider'],j['source'],external_id)).fetchone()
    if not match and canonical:
     match=db.execute('SELECT id FROM jobs WHERE canonical_url=? AND demo=0 ORDER BY first_seen, id LIMIT 1',
      (canonical,)).fetchone()
   job_id = match[0] if match else j['id']
   db.execute('''INSERT INTO jobs
    (id,provider,source,external_id,title,description,url,location,country,mode,kind,
     review_status,areas,last_seen,demo,active,misses,first_seen,canonical_url,geo_municipio,company,published_at,detail_enriched)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
    title=excluded.title, description=CASE WHEN jobs.provider='gupy' AND excluded.provider='gupy' AND jobs.detail_enriched=1 AND excluded.detail_enriched=0 THEN jobs.description ELSE excluded.description END, url=excluded.url,
    canonical_url=excluded.canonical_url, location=excluded.location,
    country=CASE WHEN jobs.provider='gupy' AND excluded.provider='gupy' AND jobs.detail_enriched=1 AND excluded.detail_enriched=0 THEN COALESCE(excluded.country,jobs.country) ELSE excluded.country END, mode=excluded.mode, kind=excluded.kind,
    review_status=excluded.review_status, areas=CASE WHEN jobs.provider='gupy' AND excluded.provider='gupy' AND jobs.detail_enriched=1 AND excluded.detail_enriched=0 THEN jobs.areas ELSE excluded.areas END,
    last_seen=excluded.last_seen, geo_municipio=CASE WHEN jobs.provider='gupy' AND excluded.provider='gupy' AND jobs.detail_enriched=1 AND excluded.detail_enriched=0 THEN COALESCE(excluded.geo_municipio,jobs.geo_municipio) ELSE excluded.geo_municipio END,
    detail_enriched=CASE WHEN jobs.provider='gupy' AND excluded.provider='gupy' AND jobs.detail_enriched=1 AND excluded.detail_enriched=0 THEN 1 ELSE excluded.detail_enriched END,
    company=COALESCE(excluded.company,jobs.company), published_at=COALESCE(excluded.published_at,jobs.published_at),
    active=1, misses=0''',
    (job_id,j['provider'],j['source'],external_id,j['title'],j['description'],j['url'],j['location'],
     j['country'],j['mode'],j['kind'],j['review_status'],json.dumps(j['areas'],ensure_ascii=False),
     j['last_seen'],demo,1,0,j['last_seen'],canonical,j.get('geo_municipio'),j.get('company'),j.get('published_at'),int(j.get('detail_enriched',False))))
   if not demo:
    db.execute('''INSERT INTO job_aliases
      (provider,source,external_id,source_job_id,job_id,active,misses,last_seen)
      VALUES (?,?,?,?,?,1,0,?) ON CONFLICT(provider,source,external_id) DO UPDATE SET
      source_job_id=excluded.source_job_id, active=1, misses=0,
      last_seen=excluded.last_seen''',
      (j['provider'],j['source'],external_id,j['id'],job_id,j['last_seen']))


def mark_missing(provider, source, seen_ids, threshold=2):
 """Desativa apenas a proveniência ausente após consultas válidas.

 Uma vaga compartilhada permanece ativa se qualquer outra origem estiver ativa.
 NÃO chamar esta função após erros de rede ou respostas incompletas.
 """
 init()
 with connect() as db:
  rows=db.execute('SELECT external_id,source_job_id,job_id FROM job_aliases '
                  'WHERE provider=? AND source=? AND active=1',(provider,source)).fetchall()
  affected={row[2] for row in rows}
  for extid, source_job_id, job_id in rows:
   if source_job_id not in seen_ids:
    db.execute('UPDATE job_aliases SET misses=misses+1 WHERE provider=? AND source=? AND external_id=?',
     (provider,source,extid))
  db.execute('UPDATE job_aliases SET active=0 WHERE provider=? AND source=? AND misses>=?',
    (provider,source,threshold))
  for job_id in affected:
   db.execute('''UPDATE jobs SET active=CASE WHEN EXISTS(
     SELECT 1 FROM job_aliases a WHERE a.job_id=jobs.id AND a.active=1)
     THEN 1 ELSE 0 END WHERE id=? AND demo=0''', (job_id,))
  return db.execute('''SELECT COUNT(DISTINCT j.id) FROM jobs j
     JOIN job_aliases a ON a.job_id=j.id WHERE a.provider=? AND a.source=?
     AND j.active=0 AND j.demo=0''', (provider,source)).fetchone()[0]

def audit_legacy_duplicates():
 """Aponta duplicidades preexistentes sem apagar dados ou combinar IDs."""
 init()
 with connect() as db:
  keys=db.execute('''SELECT canonical_url FROM jobs
   WHERE demo=0 AND canonical_url IS NOT NULL AND canonical_url<>''
   GROUP BY canonical_url HAVING COUNT(*)>1''').fetchall()
  return [{'url':url,'job_ids':[x[0] for x in db.execute(
   'SELECT id FROM jobs WHERE canonical_url=? ORDER BY first_seen,id',(url,)).fetchall()]}
   for (url,) in keys]

def stats():
 init()
 with connect() as db:
  return dict(db.execute('SELECT active,COUNT(*) FROM jobs WHERE demo=0 GROUP BY active').fetchall())

def query(q='',country='',kind='internship',limit=30,exclude_demo=False, *, region='', mode='', area='', offset=0, uf='', municipality='', radius_km=None, published_days='', only_ids=None):
 import math
 from geografia import catalog, distance_km
 cities=catalog()[0]
 states={v[2] for v in cities.values()}
 if uf and uf not in states:raise ValueError('Estado inválido')
 if municipality and (not uf or municipality not in cities or cities[municipality][2]!=uf):raise ValueError('Município inválido')
 if radius_km not in (None,''):
  if not municipality:raise ValueError('Selecione um município para usar o raio de distância.')
  try:radius_km=float(radius_km)
  except (TypeError, ValueError):raise ValueError('Informe um raio entre 0 e 2000 km.') from None
  if not math.isfinite(radius_km) or not 0<=radius_km<=2000:raise ValueError('Informe um raio entre 0 e 2000 km.')
 else:radius_km=None
 if region not in ('','brazil','international'):raise ValueError('Região inválida')
 if mode not in ('','remote','onsite','hybrid','unknown'):raise ValueError('Modalidade inválida')
 if str(published_days) not in ('','7','14','30','90'):raise ValueError('Período de publicação inválido')
 if area and area not in AREAS:raise ValueError('Área inválida')
 offset=int(offset)
 if not 0<=offset<=10000:raise ValueError('Página inválida')
 init();limit=max(1,min(int(limit),100))
 statement='SELECT * FROM jobs WHERE active=1';args=[]
 if only_ids is not None:
  if not isinstance(only_ids,list) or len(only_ids)>10000 or any(not isinstance(x,str) or len(x)>128 for x in only_ids):raise ValueError('Identificadores inválidos')
  statement+=' AND id IN (SELECT value FROM json_each(?))';args.append(json.dumps(only_ids))
 if exclude_demo:statement+=' AND demo=0'
 if q:
  statement+=' AND (lower(title) LIKE ? OR lower(description) LIKE ? OR lower(areas) LIKE ?)'
  args.extend(['%'+q.lower()+'%']*3)
 if country:statement+=' AND country = ?';args.append(country)
 if kind:statement+=' AND kind = ?';args.append(kind)
 if region=='brazil':statement+=" AND country = 'BR'"
 if region=='international':statement+=" AND country GLOB '[A-Z][A-Z]' AND country <> 'BR'"
 if mode:statement+=' AND mode = ?';args.append(mode)
 if area:statement+=' AND EXISTS (SELECT 1 FROM json_each(jobs.areas) WHERE value = ?)';args.append(area)
 if published_days:
  statement+=" AND (julianday(published_at) IS NULL OR julianday(published_at) >= julianday('now', ?))"
  args.append('-'+str(published_days)+' days')
 if radius_km is not None:
  statement+=' AND geo_distance(geo_municipio) <= ?';args.append(radius_km)
 elif municipality:
  statement+=' AND geo_municipio = ?';args.append(municipality)
 elif uf:
  statement+=' AND geo_uf(geo_municipio) = ?';args.append(uf)
 statement+=' ORDER BY last_seen DESC, id ASC LIMIT ? OFFSET ?';args.extend([limit,offset])
 with connect() as db:
  db.create_function('geo_uf',1,lambda code: cities[code][2] if code in cities else None)
  db.create_function('geo_distance',1,lambda code: distance_km(municipality,code) if code in cities else None)
  db.row_factory=sqlite3.Row
  rows=db.execute(statement,args).fetchall()
 result=[dict(r,areas=json.loads(r['areas'])) for r in rows]
 if radius_km is not None:
  for item in result:item['distance_km']=round(distance_km(municipality,item['geo_municipio']),1)
 return result


def job_details(job_id, exclude_demo=False):
 init()
 with connect() as db:
  db.row_factory=sqlite3.Row
  row=db.execute('SELECT * FROM jobs WHERE id=? AND active=1'+(' AND demo=0' if exclude_demo else ''), (job_id,)).fetchone()
  return dict(row, areas=json.loads(row['areas'])) if row else None

def demo():
 init()
 fixtures=[('Estágio em Administração','Administração','BR','Belo Horizonte','https://example.org/estagio-admin'),
 ('Estágio em Enfermagem','Saúde','BR','São Paulo','https://example.org/estagio-saude'),
 ('Software Engineering Internship','Tecnologia','CA','Toronto','https://example.org/internship-software'),
 ('Agriculture Internship','Agropecuária','US','Iowa','https://example.org/internship-agriculture')]
 jobs=[]
 for idx,(title,area,country,loc,url) in enumerate(fixtures):
  j=make_job('lever','DEMONSTRACAO',{'text':title,'id':str(idx),'hostedUrl':url,'country':country,'categories':{'location':loc}})
  j['areas']=[area];j['demo']=1;j['review_status']='fictional';jobs.append(j)
 save(jobs)
