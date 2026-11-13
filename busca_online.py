"""Busca pontual de fontes configuradas e acompanhamento em memória."""
import json
import copy
import hashlib
import logging
import re
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone

import core
from geografia import catalog, distance_km
from source_quality import validate_sources
from source_reviews import pending_technical_review

KINDS={'internship':'estagio','employment':'emprego','temporary':'temporario'}
LOG=logging.getLogger(__name__)
CACHE_SECONDS=24*60*60
COURSES={
    'informatica_internet':('Técnico em Informática para Internet','Tecnologia'),
    'sistemas_informacao':('Sistemas de Informação','Tecnologia'),
    'sistemas_internet':('Tecnólogo em Sistemas para Internet','Tecnologia'),
    'psicologia':('Psicologia','Saúde'),
}


def course_area(course):
    if not course:return ''
    if course not in COURSES:raise ValueError('Curso inválido')
    return COURSES[course][1]


def _cache_key(filters,tasks):
    data=json.dumps({'version':3,'filters':filters,'tasks':tasks},sort_keys=True,ensure_ascii=False,separators=(',',':'))
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


def _read_cache(key):
    core.init()
    with core.connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS search_cache (cache_key TEXT PRIMARY KEY, created_at REAL NOT NULL, result TEXT NOT NULL)')
        row=db.execute('SELECT created_at,result FROM search_cache WHERE cache_key=?',(key,)).fetchone()
    if not row or not 0 <= time.time()-row[0] < CACHE_SECONDS:return None
    try:
        result=json.loads(row[1])
        if not isinstance(result,dict) or not isinstance(result.get('ids'),list) or not isinstance(result.get('pending'),dict) or not isinstance(result.get('sources'),list):return None
    except (ValueError,TypeError):return None
    result['cached_at']=datetime.fromtimestamp(row[0],timezone.utc).isoformat()
    return result


def _write_cache(key,result):
    core.init()
    with core.connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS search_cache (cache_key TEXT PRIMARY KEY, created_at REAL NOT NULL, result TEXT NOT NULL)')
        now=time.time()
        timestamps=[datetime.fromisoformat(source['checked_at']).timestamp() for source in result.get('sources',[]) if source.get('checked_at')]
        origin=min(timestamps,default=now)
        db.execute('DELETE FROM search_cache WHERE created_at < ?', (now-CACHE_SECONDS,))
        db.execute('INSERT OR REPLACE INTO search_cache(cache_key,created_at,result) VALUES(?,?,?)',
                   (key,origin,json.dumps(result,ensure_ascii=False)))


def _source_key(provider,slug,options):
    return hashlib.sha256(json.dumps([1,provider,slug,options],sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def _source_load(key):
    from providers_extra import ListingBatch
    with core.connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS source_cache (cache_key TEXT PRIMARY KEY, created_at REAL NOT NULL, result TEXT NOT NULL)')
        row=db.execute('SELECT created_at,result FROM source_cache WHERE cache_key=?',(key,)).fetchone()
    if not row or not 0<=time.time()-row[0]<CACHE_SECONDS:return None
    data=json.loads(row[1]);rows=ListingBatch(data['jobs'],complete=data['complete'],raw_count=data['raw_count'])
    for job in rows:
        job['areas']=sorted(set(job.get('areas',[])) | set(core.areas_for(job.get('title',''),job.get('description',''))))
    rows.pages_fetched=data.get('pages_fetched');rows.page_limit=data.get('page_limit')
    return rows,datetime.fromtimestamp(row[0],timezone.utc).isoformat()


def _source_save(key,rows):
    payload=json.dumps({'jobs':list(rows),'complete':getattr(rows,'complete',True),'raw_count':getattr(rows,'raw_count',None),
                        'pages_fetched':getattr(rows,'pages_fetched',None),'page_limit':getattr(rows,'page_limit',None)},ensure_ascii=False)
    if len(payload)>10_000_000:return False
    with core.connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS source_cache (cache_key TEXT PRIMARY KEY, created_at REAL NOT NULL, result TEXT NOT NULL)')
        now=time.time();db.execute('DELETE FROM source_cache WHERE created_at < ?', (now-CACHE_SECONDS,))
        db.execute('INSERT OR REPLACE INTO source_cache VALUES (?,?,?)',(key,now,payload))
    return True


def _plan(filters):
    kind=filters.get('kind','all');region=filters.get('region','');country=filters.get('country','')
    uf=filters.get('uf','');city_id=filters.get('municipality','');radius=filters.get('radius_km','')
    if kind not in ('all','volunteer',*KINDS) or region not in ('','brazil','international'):
        raise ValueError('Filtros inválidos')
    if country and not re.fullmatch(r'[A-Z]{2}',country):raise ValueError('País inválido')
    cities=catalog()[0];states={row[2] for row in cities.values()}
    if uf and uf not in states:raise ValueError('Estado inválido')
    if city_id and (not uf or city_id not in cities or cities[city_id][2]!=uf):raise ValueError('Município inválido')
    if radius:
        try:distance=float(radius)
        except (ValueError,TypeError):raise ValueError('Raio inválido') from None
        import math
        if not city_id or not math.isfinite(distance) or not 0<=distance<=2000:raise ValueError('Raio inválido')
    if (uf and (region=='international' or (country and country!='BR'))) or (region=='brazil' and country and country!='BR') or (region=='international' and country=='BR'):
        raise ValueError('País, região e estado incompatíveis')
    config=json.loads((core.BASE/'sources.json').read_text(encoding='utf-8'));validate_sources(config)
    sources=config['sources'];kinds=list(KINDS) if kind=='all' else ([kind] if kind in KINDS else [])
    brazil=bool(uf or country=='BR' or region=='brazil') or not (country or region)
    international=not uf and country!='BR' and region!='brazil'
    tasks=[]
    if brazil:
        ufs=[uf]
        if uf and radius:
            closest={}
            for code,row in cities.items():
                if row[2]==uf:continue
                d=distance_km(city_id,code)
                if d<=distance:closest[row[2]]=min(d,closest.get(row[2],d))
            ufs += sorted(closest,key=lambda state:(closest[state],state))[:4]
        for k in kinds:
            for search_uf in ufs:
                base=KINDS[k];slug=base+'-'+search_uf.lower() if search_uf else base
                candidates=[s for s in sources if s['provider']=='gupy' and s['slug'] in (base,slug) and s['enabled']]
                if not any(not pending_technical_review(s) for s in candidates):continue
                city=cities[city_id][1] if city_id and not radius else ''
                workplace={'remote':'remote','hybrid':'hybrid','onsite':'on-site'}.get(filters.get('mode'),'')
                tasks.append(('gupy',slug,{'detail_limit':5,'query_text':filters.get('q','')[:100],
                                          'city':city,'workplace':workplace}))
        for source in sources:
            if (source['enabled'] and source.get('region')=='BR' and source['provider'] in ('inhire','ashby','lever','greenhouse','voluntarios')
                    and (source['provider']!='voluntarios' or kind in ('all','volunteer'))
                    and not pending_technical_review(source)):
                tasks.append((source['provider'],source['slug'],{}))
    if international:
        for source in sources:
            if (source['enabled'] and source.get('region')=='international' and source['provider'] in ('ashby','lever','greenhouse')
                    and not pending_technical_review(source)):
                tasks.append((source['provider'],source['slug'],{}))
    return tasks


def _matches(job, filters):
    kind=filters.get('kind','all');region=filters.get('region','');country=filters.get('country','')
    uf=filters.get('uf','');city=filters.get('municipality','');radius=filters.get('radius_km','')
    if kind!='all' and job['kind']!=kind:return False
    if country and job.get('country')!=country:return False
    if (region=='brazil' or uf) and job.get('country')!='BR':return False
    if region=='international' and (not re.fullmatch(r'[A-Z]{2}',job.get('country') or '') or job.get('country')=='BR'):return False
    if filters.get('mode') and job.get('mode')!=filters['mode']:return False
    if filters.get('area') and filters['area'] not in job.get('areas',[]):return False
    text=filters.get('q','').lower()
    if text and text not in (job.get('title','')+' '+job.get('description','')+' '+json.dumps(job.get('areas',[]),ensure_ascii=False)).lower():return False
    date=job.get('published_at');days=filters.get('published_days','')
    if days and date:
        try:
            when=datetime.fromisoformat(date.replace('Z','+00:00'))
            if when.tzinfo is None:when=when.replace(tzinfo=timezone.utc)
            if when < datetime.now(timezone.utc)-timedelta(days=int(days)):return False
        except (ValueError,TypeError):pass
    code=job.get('geo_municipio');cities=catalog()[0]
    if radius:
        if code not in cities or distance_km(city,code)>float(radius):return False
    elif city:
        if code!=city:return False
    elif uf and (code not in cities or cities[code][2]!=uf):return False
    return True


def _classify(job, filters):
    relaxed=dict(filters, country='',region='',uf='',municipality='',radius_km='',mode='')
    if not _matches(job,relaxed):return None
    country=job.get('country') or ''
    wanted=filters.get('country','');region=filters.get('region','');uf=filters.get('uf','')
    if country and ((wanted and country!=wanted) or (region=='brazil' and country!='BR') or
                    (region=='international' and country=='BR') or (uf and country!='BR')):return None
    mode=job.get('mode') or 'unknown';requested=filters.get('mode','')
    if requested and mode!='unknown' and mode!=requested:return None
    if requested=='unknown' and mode!='unknown':return None
    missing=[]
    remote_without_geo = mode=='remote' and not (wanted or region or uf or filters.get('municipality') or filters.get('radius_km'))
    if not country and not remote_without_geo:missing.append('País não confirmado')
    if mode=='unknown':missing.append('Modalidade não informada')
    cities=catalog()[0];code=job.get('geo_municipio')
    if uf and code in cities:
        city=filters.get('municipality','');radius=filters.get('radius_km','')
        if radius and distance_km(city,code)>float(radius):return None
        if not radius and city and code!=city:return None
        if not city and cities[code][2]!=uf:return None
    location_needed=bool(uf or filters.get('municipality') or filters.get('radius_km')) or not (wanted or region)
    if location_needed and not remote_without_geo and (not job.get('location') or (uf and code not in cities)):missing.append('Localização insuficiente para confirmar a região')
    return missing


class SearchManager:
    def __init__(self, timeout=900):
        self.lock=threading.Lock();self.jobs={};self.threads={}
        self.timeout=timeout

    def _expire(self, ident):
        job=self.jobs.get(ident)
        if job and job['status']=='running' and time.monotonic()-job['started_monotonic']>self.timeout:
            job.update(status='failed',current='Tempo de consulta esgotado',failed=job['failed']+1)

    def _worker(self, ident, tasks, filters):
        try:
            self._run(ident,tasks,filters)
        except BaseException as exc:
            LOG.error('Busca interrompida: %s',type(exc).__name__)
            with self.lock:
                job=self.jobs.get(ident)
                if job and job['status']=='running':job.update(status='failed',current='Consulta interrompida',failed=job['failed']+1)

    def start(self,filters):
        tasks=_plan(filters)
        if not tasks:raise ValueError('Nenhuma fonte disponível para os filtros escolhidos')
        with self.lock:
            for old in self.jobs:self._expire(old)
            if any(t.is_alive() for t in self.threads.values()):raise ValueError('Já existe uma busca em andamento')
            self.jobs.clear();self.threads.clear()
            ident=secrets.token_urlsafe(24)
            self.jobs[ident]={'status':'running','total':len(tasks),'done':0,'failed':0,'details_failed':0,'saved':0,'ids':[],
                              'detail_done':0,'detail_total':0,'current':'Preparando consulta','filters':dict(filters),'sources':[],'pending':{},'started_monotonic':time.monotonic()}
            key=_cache_key(filters,tasks)
            try:cached=_read_cache(key)
            except (sqlite3.Error,OSError,ValueError):
                LOG.warning('Não foi possível ler pesquisas armazenadas');cached=None
            if cached:
                self.jobs[ident].update(cached,status='completed',done=len(tasks),current='Resultados armazenados',cached=True)
                return ident
            worker=threading.Thread(target=self._worker,args=(ident,tasks,dict(filters)),daemon=True)
            self.threads[ident]=worker
            try:worker.start()
            except Exception:
                self.jobs.clear();self.threads.clear()
                raise
        return ident

    def _run(self,ident,tasks,filters):
        for provider,slug,options in tasks:
            with self.lock:
                self._expire(ident)
                if self.jobs[ident]['status']!='running':return
                self.jobs[ident].update(current=provider+'/'+slug,detail_done=0,detail_total=0)
            result={'provider':provider,'slug':slug,'status':'failed','matched':None}
            network_attempted=False
            try:
                def progress(done,total):
                    with self.lock:self.jobs[ident].update(detail_done=done,detail_total=total)
                extra={'progress_callback':progress} if provider in ('gupy','voluntarios') else {}
                source_key=_source_key(provider,slug,options)
                try:stored=_source_load(source_key)
                except (sqlite3.Error,OSError,ValueError,KeyError,TypeError):stored=None
                if stored:
                    rows,checked_at=stored
                    result['cached']=True
                else:
                    network_attempted=True
                    rows=core.fetch_source(provider,slug,**options,**extra)
                    checked_at=datetime.now(timezone.utc).isoformat()
                with self.lock:
                    self._expire(ident)
                    if self.jobs[ident]['status']!='running':return
                detail_failed=max(0,getattr(rows,'details_attempted',0)-getattr(rows,'details_succeeded',0))
                result['received']=len(rows)
                result['incomplete']=sum(1 for job in rows if not job.get('title') or not job.get('description') or job.get('mode') in (None,'','unknown') or (job.get('mode')!='remote' and not job.get('location')))
                source_saved=bool(stored)
                if not stored and not detail_failed:
                    try:source_saved=_source_save(source_key,rows)
                    except (sqlite3.Error,OSError,ValueError,TypeError):LOG.warning('Não foi possível armazenar fonte')
                with self.lock:self.jobs[ident]['details_failed']+=detail_failed
                classified=[(job,_classify(job,filters)) for job in rows]
                accepted=[(job,missing) for job,missing in classified if missing is not None]
                core.save([job for job,_ in accepted])
                external_ids=[str(job['external_id']) for job,_ in accepted]
                with core.connect() as db:
                    aliases=dict(db.execute('SELECT external_id,job_id FROM job_aliases WHERE provider=? AND source=? AND external_id IN (SELECT value FROM json_each(?))',
                         (provider,slug,json.dumps(external_ids))).fetchall())
                ids={aliases[str(job['external_id'])] for job,missing in accepted if not missing and str(job['external_id']) in aliases}
                with self.lock:
                    self.jobs[ident]['ids']=sorted(set(self.jobs[ident]['ids'])|set(ids))
                    for job,missing in accepted:
                        job_id=aliases.get(str(job['external_id']))
                        if job_id and missing and job_id not in self.jobs[ident]['ids']:self.jobs[ident]['pending'][job_id]=missing
                    for job_id in self.jobs[ident]['ids']:self.jobs[ident]['pending'].pop(job_id,None)
                    self.jobs[ident]['saved']=len(self.jobs[ident]['ids'])
                result.update(status='partial' if not getattr(rows,'complete',True) or detail_failed else 'ok',matched=len(ids),pages=getattr(rows,'pages_fetched',None),page_limit=getattr(rows,'page_limit',None),checked_at=checked_at,cacheable=source_saved)
            except Exception as exc:
                LOG.warning('Falha na consulta %s/%s: %s',provider,slug,type(exc).__name__)
                with self.lock:self.jobs[ident]['failed']+=1
            finally:
                if network_attempted:
                    try:
                        from admin_history import record_source
                        record_source(provider,slug,result['status'],result.get('received'),result.get('incomplete'))
                    except (sqlite3.Error,OSError,ValueError):LOG.warning('Não foi possível registrar consulta da fonte')
                with self.lock:
                    self.jobs[ident]['sources'].append(result)
                    self.jobs[ident]['done']+=1
        with self.lock:
            if self.jobs[ident]['status']=='running':
                self.jobs[ident].update(status='completed',current='Consulta concluída')
                state=self.jobs[ident]
                cached={name:copy.deepcopy(state[name]) for name in ('ids','pending','sources','saved')}
                can_cache=not state['failed'] and not state['details_failed']
            else:can_cache=False
        if can_cache:
            try:_write_cache(_cache_key(filters,tasks),cached)
            except (sqlite3.Error,OSError,ValueError):LOG.warning('Não foi possível armazenar pesquisa')

    def status(self,ident):
        with self.lock:
            self._expire(ident)
            return copy.deepcopy(self.jobs[ident]) if ident in self.jobs else None

    def wait(self,ident,timeout=None):
        with self.lock:thread=self.threads.get(ident)
        if thread:thread.join(timeout)
