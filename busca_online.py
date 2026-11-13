"""Busca pontual de fontes configuradas e acompanhamento em memória."""
import json
import copy
import logging
import re
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone

import core
from geografia import catalog, distance_km
from source_quality import validate_sources
from source_reviews import pending_technical_review

KINDS={'internship':'estagio','employment':'emprego','temporary':'temporario'}
LOG=logging.getLogger(__name__)


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
            if (source['enabled'] and source.get('region')=='BR' and source['provider'] in ('inhire','ashby','lever','greenhouse')
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
    if not country:missing.append('País não confirmado')
    if mode=='unknown':missing.append('Modalidade não informada')
    cities=catalog()[0];code=job.get('geo_municipio')
    if uf and code in cities:
        city=filters.get('municipality','');radius=filters.get('radius_km','')
        if radius and distance_km(city,code)>float(radius):return None
        if not radius and city and code!=city:return None
        if not city and cities[code][2]!=uf:return None
    if not job.get('location') or (uf and code not in cities):missing.append('Localização insuficiente para confirmar a região')
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
            try:
                def progress(done,total):
                    with self.lock:self.jobs[ident].update(detail_done=done,detail_total=total)
                extra={'progress_callback':progress} if provider=='gupy' else {}
                rows=core.fetch_source(provider,slug,**options,**extra)
                with self.lock:
                    self._expire(ident)
                    if self.jobs[ident]['status']!='running':return
                detail_failed=max(0,getattr(rows,'details_attempted',0)-getattr(rows,'details_succeeded',0))
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
                result.update(status='partial' if not getattr(rows,'complete',True) or detail_failed else 'ok',matched=len(ids),pages=getattr(rows,'pages_fetched',None),page_limit=getattr(rows,'page_limit',None))
            except Exception as exc:
                LOG.warning('Falha na consulta %s/%s: %s',provider,slug,type(exc).__name__)
                with self.lock:self.jobs[ident]['failed']+=1
            finally:
                with self.lock:
                    self.jobs[ident]['sources'].append(result)
                    self.jobs[ident]['done']+=1
        with self.lock:
            if self.jobs[ident]['status']=='running':self.jobs[ident].update(status='completed',current='Consulta concluída')

    def status(self,ident):
        with self.lock:
            self._expire(ident)
            return copy.deepcopy(self.jobs[ident]) if ident in self.jobs else None

    def wait(self,ident,timeout=None):
        with self.lock:thread=self.threads.get(ident)
        if thread:thread.join(timeout)
