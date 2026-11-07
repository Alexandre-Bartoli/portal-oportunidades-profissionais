import hashlib
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

def classify(title,description=''):
 t=normalize_text(title)
 if NEGATIVE.search(t): return 'other','review'
 if WORDS.search(t): return 'internship','review'
 return 'other','review'

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
 else: raise ValueError('Fonte desconhecida')
 if not title or not url or not url.startswith('https://'): return None
 if not country and any(x in normalize_text(str(location)) for x in ('brasil','brazil','sao paulo','belo horizonte','campinas','rio de janeiro','curitiba','porto alegre','recife','fortaleza','brasilia')):country='BR'
 kind,review=classify(title,description)
 if kind!='internship':
  # Também considera o tipo de contratação explícito nas APIs.
  employment = str(raw.get('employmentType') or (raw.get('categories') or {}).get('commitment') or '')
  if normalize_text(employment) not in ('intern','internship','estagio'):return None
  kind='internship'
 fingerprint=hashlib.sha256((provider+'|'+source+'|'+extid+'|'+url).encode()).hexdigest()
 return {'id':fingerprint,'provider':provider,'source':source,'external_id':extid,'title':clean(title),
 'description':description[:12000],'url':url,'location':clean(location),'country':country,
 'mode':mode,'kind':kind,'review_status':review,'areas':areas_for(title,description),
 'last_seen':datetime.now(timezone.utc).isoformat(),'demo':0}

def get_json(url, attempts=3, wait=time.sleep):
 """Consulta HTTPS com tentativas limitadas para falhas transitórias."""
 if not url.startswith('https://'):
  raise ValueError('A consulta deve utilizar HTTPS')
 request=urllib.request.Request(url,headers={'User-Agent':'PortalOportunidades/0.4 (research prototype)','Accept':'application/json'})
 for attempt in range(attempts):
  try:
   with urllib.request.urlopen(request, timeout=20) as response:
    return json.load(response)
  except urllib.error.HTTPError as exc:
   if exc.code not in (429,500,502,503,504) or attempt==attempts-1:
    raise
  except (urllib.error.URLError, TimeoutError, ConnectionError):
   if attempt==attempts-1:
    raise
  wait(min(2**attempt,4))
 raise RuntimeError('Tentativas de consulta esgotadas')

def fetch_source(provider,slug):
 encoded=urllib.parse.quote(slug,safe='')
 if provider=='greenhouse':
  data=get_json('https://boards-api.greenhouse.io/v1/boards/'+encoded+'/jobs?content=true');items=data['jobs'] if isinstance(data,dict) else None
 elif provider=='lever':
  items=[];offset=0
  while offset<2000:
   batch=get_json('https://api.lever.co/v0/postings/'+encoded+'?mode=json&skip='+str(offset)+'&limit=100')
   if not isinstance(batch,list):raise ValueError('Resposta inválida do Lever')
   items.extend(batch)
   if len(batch)<100:break
   offset+=100
 elif provider=='ashby':
  data=get_json('https://api.ashbyhq.com/posting-api/job-board/'+encoded);items=[j for j in data['jobs'] if j.get('isListed',True)] if isinstance(data,dict) and isinstance(data.get('jobs'),list) else None
 else: raise ValueError('Provedor não permitido')
 if not isinstance(items,list):raise ValueError('Resposta inválida da fonte')
 return [j for raw in items if (j:=make_job(provider,slug,raw)) is not None]

@contextmanager
def connect():
 DB.parent.mkdir(parents=True,exist_ok=True)
 db=sqlite3.connect(DB)
 try:
  with db:
   yield db
 finally:
  db.close()

def init():
 with connect() as db:
  db.execute('''CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, provider TEXT, source TEXT, external_id TEXT,
   title TEXT, description TEXT, url TEXT, location TEXT, country TEXT, mode TEXT, kind TEXT,
   review_status TEXT, areas TEXT, last_seen TEXT, demo INTEGER DEFAULT 0)''')
  columns={r[1] for r in db.execute('PRAGMA table_info(jobs)').fetchall()}
  if 'active' not in columns:db.execute('ALTER TABLE jobs ADD COLUMN active INTEGER DEFAULT 1')
  if 'misses' not in columns:db.execute('ALTER TABLE jobs ADD COLUMN misses INTEGER DEFAULT 0')
  if 'first_seen' not in columns:db.execute('ALTER TABLE jobs ADD COLUMN first_seen TEXT')
  db.execute('UPDATE jobs SET first_seen=last_seen WHERE first_seen IS NULL')
  db.execute('CREATE INDEX IF NOT EXISTS ix_jobs_title ON jobs(title)')
  db.execute('CREATE INDEX IF NOT EXISTS ix_jobs_source ON jobs(provider, source, active)')

def save(items):
 init()
 with connect() as db:
  for j in items:
   db.execute('''INSERT INTO jobs (id,provider,source,external_id,title,description,url,location,country,mode,kind,review_status,areas,last_seen,demo,active,misses,first_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
    title=excluded.title, description=excluded.description, location=excluded.location,
    country=excluded.country, mode=excluded.mode, kind=excluded.kind,
    review_status=excluded.review_status, areas=excluded.areas, last_seen=excluded.last_seen, active=1, misses=0''',
    (j['id'],j['provider'],j['source'],j['external_id'],j['title'],j['description'],j['url'],j['location'],
     j['country'],j['mode'],j['kind'],j['review_status'],json.dumps(j['areas'],ensure_ascii=False),j['last_seen'],j['demo'],1,0,j['last_seen']))


def mark_missing(provider, source, seen_ids, threshold=2):
 """Uma vaga fica inativa após ausências em consultas bem sucedidas consecutivas.
 Esta função NUNCA deve ser chamada após erro de rede ou resposta inválida.
 """
 init()
 with connect() as db:
  rows=db.execute('SELECT id FROM jobs WHERE provider=? AND source=? AND demo=0 AND active=1',(provider,source)).fetchall()
  for (job_id,) in rows:
   if job_id not in seen_ids:
    db.execute('UPDATE jobs SET misses=misses+1 WHERE id=?',(job_id,))
  db.execute('UPDATE jobs SET active=0 WHERE provider=? AND source=? AND demo=0 AND misses>=?',(provider,source,threshold))
  return db.execute('SELECT COUNT(*) FROM jobs WHERE provider=? AND source=? AND active=0 AND demo=0',(provider,source)).fetchone()[0]

def stats():
 init()
 with connect() as db:
  return dict(db.execute('SELECT active,COUNT(*) FROM jobs WHERE demo=0 GROUP BY active').fetchall())

def query(q='',country='',kind='internship',limit=30):
 init();limit=max(1,min(int(limit),100))
 statement='SELECT * FROM jobs WHERE active=1';args=[]
 if q:
  statement+=' AND (lower(title) LIKE ? OR lower(description) LIKE ? OR lower(areas) LIKE ?)'
  args.extend(['%'+q.lower()+'%']*3)
 if country:statement+=' AND country = ?';args.append(country)
 if kind:statement+=' AND kind = ?';args.append(kind)
 statement+=' ORDER BY last_seen DESC LIMIT ?';args.append(limit)
 with connect() as db:
  db.row_factory=sqlite3.Row
  rows=db.execute(statement,args).fetchall()
 return [dict(r,areas=json.loads(r['areas'])) for r in rows]

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