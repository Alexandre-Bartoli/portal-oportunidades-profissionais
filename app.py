import html
import json
import os
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from core import init, demo, query, fetch_source, save, BASE
from brasil import portals_json, import_csv
from automatico import collect_once, start_scheduler, status as collection_status
from signals import analyze

STAGING_MODE = False
RADIUS_MESSAGES = frozenset({'Selecione um município para usar o raio de distância.', 'Informe um raio entre 0 e 2000 km.',
 'Busca expirada ou indisponível. Faça uma nova pesquisa.', 'A busca ainda está em andamento.'})
_search_lock=threading.Lock()

def search_manager(server):
 with _search_lock:
  if not hasattr(server,'search_manager'):
   from busca_online import SearchManager
   server.search_manager=SearchManager()
  return server.search_manager

def filter_message(error):
 return str(error) if str(error) in RADIUS_MESSAGES else 'Confira os filtros e tente novamente.'

def local_host_allowed(handler):
 hosts=handler.headers.get_all('Host',[])
 if len(hosts)!=1:return False
 try:
  parsed=urllib.parse.urlsplit('//'+hosts[0])
  return (parsed.hostname in {'127.0.0.1','localhost','::1'} and parsed.port==handler.server.server_port
          and parsed.username is None and parsed.password is None and not parsed.path and not parsed.query and not parsed.fragment)
 except ValueError:return False

class Handler(BaseHTTPRequestHandler):
 def response(self,body,content_type='application/json',status=200):
  payload=body.encode('utf-8');self.send_response(status)
  self.send_header('Content-Type',content_type+'; charset=utf-8')
  self.send_header('Content-Length',str(len(payload)))
  self.send_header('X-Content-Type-Options','nosniff')
  self.send_header('X-Frame-Options','DENY')
  self.send_header('Cache-Control','no-store')
  self.send_header('Content-Security-Policy',"default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'")
  if status==401:self.send_header('WWW-Authenticate','Basic realm="Portal administracao", charset="UTF-8"')
  if status==429:self.send_header('Retry-After','60')
  self.end_headers();self.wfile.write(payload)
 def do_GET(self):
  if not local_host_allowed(self):return self.response('Origem de acesso inválida','text/plain',403)
  u=urllib.parse.urlparse(self.path);p=urllib.parse.parse_qs(u.query)
  if u.path=='/busca-progresso':
   from interface_publica import render_progress
   ident=p.get('id',[''])[0]
   state=search_manager(self.server).status(ident)
   if not state:return self.response('Busca não encontrada','text/plain',404)
   return self.response(render_progress(state,ident),'text/html')
  if u.path in ('/admin','/api/admin','/api/collection-status','/api/staging-status'):
   import admin
   result=admin.authenticate(self)
   if result!=200:
    return self.response('Acesso administrativo indisponível' if result==503 else 'Acesso negado','text/plain',result)
   if u.path in ('/admin','/api/admin'):
    try:
     report=admin.dashboard(staging=STAGING_MODE)
     return self.response(admin.render(report),'text/html') if u.path=='/admin' else self.response(json.dumps(report,ensure_ascii=False))
    except Exception:
     return self.response('Dados administrativos indisponíveis','text/plain',503)
  if u.path=='/api/collection-status':
   if STAGING_MODE:
    from homologacao import staging_status
    return self.response(json.dumps(staging_status(),ensure_ascii=False))
   return self.response(json.dumps(collection_status(),ensure_ascii=False))
  if u.path=='/api/staging-status' and STAGING_MODE:
   from homologacao import staging_status
   return self.response(json.dumps(staging_status(),ensure_ascii=False))
  if u.path=='/api/providers':
   from provider_catalog import CATALOG
   return self.response(json.dumps({'providers':CATALOG},ensure_ascii=False))
  if u.path=='/api/health':return self.response(json.dumps({'status':'ok','version':'0.9-experimental','mode':'homologacao' if STAGING_MODE else 'local'}))
  if u.path=='/api/portals':return self.response(json.dumps({'portals':portals_json()},ensure_ascii=False))
  if u.path=='/api/jobs':
   try:
    kind=p.get('kind',['internship'])[0]
    if kind not in ('internship','employment','temporary','all'):return self.response('{"error":"Categoria inválida"}',status=400)
    result=query(q=p.get('q',[''])[0][:100],country=p.get('country',[''])[0][:3],kind='' if kind=='all' else kind,limit=p.get('limit',[30])[0],exclude_demo=STAGING_MODE,
                 region=p.get('region',[''])[0],mode=p.get('mode',[''])[0],area=p.get('area',[''])[0],offset=p.get('offset',[0])[0],
                 uf=p.get('uf',[''])[0],municipality=p.get('municipality',[''])[0],radius_km=p.get('radius_km',[''])[0],published_days=p.get('published_days',[''])[0])
    from link_checks import allowed_link
    for item in result:
     item['signals']=analyze(item['title'],item['description'],item['mode'])
     item['link_permitido']=allowed_link(item.get('provider'),item.get('url'))
     if not item['link_permitido']:item['url']=None
    return self.response(json.dumps({'count':len(result),'results':result},ensure_ascii=False))
   except ValueError as error:return self.response(json.dumps({'error':filter_message(error)},ensure_ascii=False),status=400)
  if u.path=='/vaga':
   from core import job_details
   from link_checks import allowed_link
   item=job_details(p.get('id',[''])[0][:128],exclude_demo=STAGING_MODE)
   if not item:return self.response('Vaga não encontrada','text/plain',404)
   from interface_publica import render_detail
   link=item.get('url') if allowed_link(item.get('provider'),item.get('url')) else None
   link_label='Consultar anúncio na Remotive' if item['provider']=='remotive' else 'Consultar anúncio na fonte'
   flags=analyze(item['title'],item['description'],item['mode'])
   return self.response(render_detail(item,link,link_label,flags),'text/html')
  if u.path!='/':return self.response('Não encontrado','text/plain',404)
  q=p.get('q',[''])[0][:100];country=p.get('country',[''])[0][:3]
  kind=p.get('kind',['internship'])[0]
  if kind not in ('internship','employment','temporary','all'):kind='internship'
  region=p.get('region',[''])[0];mode=p.get('mode',[''])[0];area=p.get('area',[''])[0]
  uf=p.get('uf',[''])[0];municipality=p.get('municipality',[''])[0];radius=p.get('radius_km',[''])[0];published_days=p.get('published_days',[''])[0]
  search_id=p.get('search_id',[''])[0]
  search=None
  loading_cities=p.get('load_cities',[''])[0]=='1'
  if loading_cities:municipality=''
  error_message=''
  try:
   offset=int(p.get('offset',[0])[0])
   only_ids=None
   if search_id:
    search=search_manager(self.server).status(search_id)
    if not search:raise ValueError('Busca expirada ou indisponível. Faça uma nova pesquisa.')
    if search['status']!='completed':raise ValueError('A busca ainda está em andamento.')
    only_ids=search['ids']
   records=query(q,country,kind='' if kind=='all' else kind,exclude_demo=STAGING_MODE,region=region,mode=mode,area=area,limit=31,offset=offset,uf=uf,municipality=municipality,radius_km='' if loading_cities else radius,published_days=published_days,only_ids=only_ids)
  except ValueError as error:
   error_message=filter_message(error);records=[];offset=0
  has_more=len(records)>30;records=records[:30]
  from core import AREAS
  from geografia import municipalities
  from interface_publica import render_search
  states=[(x,x) for x in sorted({r[2] for r in municipalities()})]
  cities=[(r[0],r[1]) for r in municipalities(uf)] if uf else []
  filters={'q':q,'country':country,'kind':kind,'region':region,'mode':mode,'area':area,
           'uf':uf,'municipality':municipality,'radius_km':radius,'published_days':published_days}
  navigation=[]
  for target,label in ((max(0,offset-30),'Página anterior'),(offset+30,'Próxima página')):
   if (label=='Página anterior' and offset>0) or (label=='Próxima página' and has_more and target<=10000):
    params={**filters,'offset':target}
    if search_id:params['search_id']=search_id
    navigation.append(('/?'+urllib.parse.urlencode(params),label))
  page=render_search(records,filters,list(AREAS),states,cities,navigation,STAGING_MODE,portals_json(),error_message=error_message,source_results=search.get('sources',[]) if search and not error_message else [])
  self.response(page,'text/html',status=400 if error_message else 200)

 def do_POST(self):
  if not local_host_allowed(self):return self.response('Origem de acesso inválida','text/plain',403)
  if self.path!='/buscar-agora':return self.response('Operação indisponível','text/plain',501)
  if STAGING_MODE:return self.response('Operação indisponível','text/plain',404)
  if self.headers.get_all('Origin',[])!=['http://'+self.headers.get('Host','')]:
   return self.response('Origem de acesso inválida','text/plain',403)
  lengths=self.headers.get_all('Content-Length',[])
  if len(lengths)!=1:return self.response('Requisição inválida','text/plain',400)
  try:length=int(lengths[0])
  except ValueError:return self.response('Requisição inválida','text/plain',400)
  if not 0<=length<=8192 or self.headers.get_content_type()!='application/x-www-form-urlencoded':
   return self.response('Requisição inválida','text/plain',400)
  try:
   params=urllib.parse.parse_qs(self.rfile.read(length).decode('utf-8'),max_num_fields=30)
   def get(name,limit=150):return params.get(name,[''])[0][:limit]
   filters={'q':get('q',100),'kind':get('kind') or 'all','country':get('country',3),
            'region':get('region'),'mode':get('mode'),'area':get('area'),
            'uf':get('uf'),'municipality':get('municipality'),'radius_km':get('radius_km'),
            'published_days':get('published_days')}
   kind=filters['kind']
   if kind not in ('all','internship','employment','temporary'):raise ValueError('Categoria inválida')
   query(q=filters['q'],country=filters['country'],kind='' if kind=='all' else kind,limit=1,
         region=filters['region'],mode=filters['mode'],area=filters['area'],uf=filters['uf'],
         municipality=filters['municipality'],radius_km=filters['radius_km'],published_days=filters['published_days'])
   ident=search_manager(self.server).start(filters)
  except (ValueError,UnicodeError) as error:
   if 'filters' not in locals():return self.response('Requisição inválida','text/plain',400)
   from geografia import municipalities
   from interface_publica import render_search
   from core import AREAS
   messages=RADIUS_MESSAGES | {'País, região e estado incompatíveis',
       'Nenhuma fonte disponível para os filtros escolhidos','Já existe uma busca em andamento'}
   message=str(error) if str(error) in messages else 'Confira os filtros e tente novamente.'
   states=[(x,x) for x in sorted({r[2] for r in municipalities()})]
   cities=[(r[0],r[1]) for r in municipalities(filters['uf'])] if filters['uf'] else []
   return self.response(render_search([],filters,list(AREAS),states,cities,[],False,portals_json(),error_message=message),'text/html',400)
  self.send_response(303);self.send_header('Location','/busca-progresso?id='+urllib.parse.quote(ident,safe=''))
  self.send_header('Content-Length','0');self.send_header('Cache-Control','no-store');self.end_headers()

def main():
 cmd=sys.argv[1] if len(sys.argv)>1 else 'help'
 if cmd=='init':init();print('Banco inicializado')
 elif cmd=='demo':demo();print('Quatro anúncios FICTÍCIOS adicionados')
 elif cmd=='serve':
  init()
  if os.getenv('PORTAL_COLETA_AUTOMATICA')=='1':start_scheduler()
  print('Acesse http://127.0.0.1:8766');ThreadingHTTPServer(('127.0.0.1',8766),Handler).serve_forever()
 elif cmd=='collect-auto':
  print(json.dumps(collect_once(),ensure_ascii=False,indent=2))
 elif cmd=='stage-collect':
  import argparse
  from homologacao import collect_current_staging, STAGING_DB
  from stage_storage import staging_lock, backup_staging, write_private_report
  from homologacao import STAGING_REPORT
  parser=argparse.ArgumentParser(description='Coleta de homologação em banco isolado')
  parser.add_argument('--min-sources',type=int,default=2)
  args=parser.parse_args(sys.argv[2:])
  with staging_lock(STAGING_DB.parent):
   report=collect_current_staging(min_sources=args.min_sources)
   if report['summary']['ok'] > 0:
    report['automatic_backup'] = backup_staging(STAGING_DB)
   else:
    report['automatic_backup'] = {'skipped':'nenhuma fonte completa com vagas nesta execução'}
   write_private_report(report,STAGING_REPORT)
  print(json.dumps(report,ensure_ascii=False,indent=2))
  if not report['criteria']['met']:raise SystemExit(2)
 elif cmd=='stage-status':
  from homologacao import staging_status
  print(json.dumps(staging_status(),ensure_ascii=False,indent=2))
 elif cmd=='stage-serve':
  import core
  from homologacao import STAGING_DB, MAIN_DB
  from stage_storage import staging_lock
  if STAGING_DB.resolve()==MAIN_DB.resolve():raise SystemExit('Banco de homologação inválido')
  if not STAGING_DB.exists():raise SystemExit('Execute stage-collect antes de abrir a homologação')
  global STAGING_MODE
  STAGING_MODE=True
  core.DB=STAGING_DB
  print('HOMOLOGAÇÃO LOCAL: http://127.0.0.1:8767',flush=True)
  with staging_lock(STAGING_DB.parent):
   ThreadingHTTPServer(('127.0.0.1',8767),Handler).serve_forever()
 elif cmd=='stage-backup':
  from homologacao import STAGING_DB
  from stage_storage import backup_staging, staging_lock
  with staging_lock(STAGING_DB.parent):
   print(json.dumps(backup_staging(STAGING_DB), ensure_ascii=False, indent=2))
 elif cmd=='stage-backups':
  from homologacao import STAGING_DB
  from stage_storage import backup_list
  print(json.dumps({'backups':backup_list(STAGING_DB.parent/'backups')},ensure_ascii=False,indent=2))
 elif cmd=='stage-restore':
  import argparse
  from homologacao import STAGING_DB
  from stage_storage import restore_staging, staging_lock
  parser=argparse.ArgumentParser(description='Restaurar backup somente com servidor desligado')
  parser.add_argument('--name',required=True,help='Nome do arquivo listado em stage-backups')
  parser.add_argument('--confirm',action='store_true',help='Confirma a substituição do banco')
  args=parser.parse_args(sys.argv[2:])
  with staging_lock(STAGING_DB.parent, exclusive=True):
   print(json.dumps(restore_staging(args.name,confirm=args.confirm,db_path=STAGING_DB),ensure_ascii=False,indent=2))
 elif cmd=='stage-review-sources':
  from homologacao import STAGING_DB
  from source_reviews import review_report
  from stage_storage import write_private_report
  config=json.loads((BASE/'sources.json').read_text(encoding='utf-8'))
  report=review_report(config)
  write_private_report(report,STAGING_DB.parent/'revisao_fontes.json')
  print(json.dumps(report,ensure_ascii=False,indent=2))
 elif cmd=='stage-check-links':
  import argparse
  from homologacao import STAGING_DB
  from stage_storage import staging_lock
  from link_checks import audit_links
  parser=argparse.ArgumentParser(description='Amostra de links sem alterar vagas')
  parser.add_argument('--limit',type=int,default=12)
  parser.add_argument('--network',action='store_true',help='Consultar somente fontes com revisão documental válida')
  args=parser.parse_args(sys.argv[2:])
  config=json.loads((BASE/'sources.json').read_text(encoding='utf-8'))
  with staging_lock(STAGING_DB.parent):
   report=audit_links(STAGING_DB,config,limit=args.limit,network=args.network,report_path=STAGING_DB.parent/'auditoria_links.json')
  print(json.dumps(report,ensure_ascii=False,indent=2))
 elif cmd=='verify-sources':
  import argparse
  from source_validation import verify_current_sources
  parser=argparse.ArgumentParser(description='Auditar fontes habilitadas sem alterar vagas')
  parser.add_argument('--min-sources',type=int,default=2,
                      help='Número mínimo de fontes completas com oportunidades')
  args=parser.parse_args(sys.argv[2:])
  report=verify_current_sources(min_sources=args.min_sources)
  print(json.dumps(report,ensure_ascii=False,indent=2))
  if not report['criteria']['met']:
   raise SystemExit(2)
 elif cmd=='audit-duplicates':
  from core import audit_legacy_duplicates
  print(json.dumps({'legacy_duplicate_groups':audit_legacy_duplicates()},ensure_ascii=False,indent=2))
 elif cmd=='discover-sources':
  from discover_sources import from_database
  from core import connect
  cfg=json.loads((BASE/'sources.json').read_text(encoding='utf-8'))
  init()
  with connect() as db:
   found=from_database(db,configured=cfg['sources'])
  print(json.dumps({'candidates':found},ensure_ascii=False,indent=2))
 elif cmd=='import-br':
  if len(sys.argv)<3: raise SystemExit('Uso: python3 app.py import-br caminho.csv')
  print('Vagas importadas para revisão:',import_csv(sys.argv[2]))
 elif cmd=='collect-br':
  from feeds_brasil import load_configs, collect_feed
  total=0
  for feed in load_configs():
   if not feed.get('enabled', False): continue
   try:
    count=collect_feed(feed); total+=count; print('Feed brasileiro',feed['portal'],count,'registros para revisão')
   except Exception as exc:print('Erro em feed brasileiro',feed.get('portal'),str(exc),file=sys.stderr)
  print('Total brasileiro importado:',total)
 elif cmd=='collect':
  from source_reviews import pending_technical_review
  config=json.loads((BASE/'sources.json').read_text(encoding='utf-8'));total=0
  for source in config['sources']:
   if not source.get('enabled'):continue
   if pending_technical_review(source):
    print('Fonte aguardando revisão técnica:',source['provider'],source['slug'])
    continue
   try:
    found=fetch_source(source['provider'],source['slug']);save(found);total+=len(found)
    print(source['provider'],source['slug'],len(found),'vagas com indício de estágio')
   except Exception as exc:print('Erro na fonte',source['slug'],str(exc),file=sys.stderr)
  print('Total importado:',total)
 else:print('Uso: python3 app.py init|collect-auto|serve')
if __name__=='__main__':main()
