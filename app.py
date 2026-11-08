import html
import json
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from core import init, demo, query, fetch_source, save, BASE
from brasil import portals_json, import_csv
from automatico import collect_once, start_scheduler, status as collection_status
from signals import analyze

STAGING_MODE = False

class Handler(BaseHTTPRequestHandler):
 def response(self,body,content_type='application/json',status=200):
  payload=body.encode('utf-8');self.send_response(status)
  self.send_header('Content-Type',content_type+'; charset=utf-8')
  self.send_header('Content-Length',str(len(payload)))
  self.send_header('X-Content-Type-Options','nosniff')
  self.send_header('Cache-Control','no-store')
  self.send_header('Content-Security-Policy',"default-src 'none'; style-src 'unsafe-inline'")
  self.end_headers();self.wfile.write(payload)
 def do_GET(self):
  u=urllib.parse.urlparse(self.path);p=urllib.parse.parse_qs(u.query)
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
                 region=p.get('region',[''])[0],mode=p.get('mode',[''])[0],area=p.get('area',[''])[0],offset=p.get('offset',[0])[0])
    for item in result:item['signals']=analyze(item['title'],item['description'],item['mode'])
    return self.response(json.dumps({'count':len(result),'results':result},ensure_ascii=False))
   except ValueError:return self.response('{"error":"Parâmetro inválido"}',status=400)
  if u.path=='/vaga':
   from core import job_details
   from listing_identity import canonical_url
   item=job_details(p.get('id',[''])[0][:128],exclude_demo=STAGING_MODE)
   if not item:return self.response('Vaga não encontrada','text/plain',404)
   esc=lambda value:html.escape(str(value or 'Não informado'))
   link=canonical_url(item.get('url'))
   action=('<a rel="noopener noreferrer" href="'+html.escape(link,quote=True)+'">Consultar anúncio original</a>') if link else '<p>Link não confirmado.</p>'
   notice='<p>EXEMPLO FICTÍCIO</p>' if item['demo'] else '<p>Dados coletados automaticamente, sujeitos a revisão.</p>'
   page='<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Detalhes da oportunidade</title><main><a href="/">Voltar à pesquisa</a><h1>'+esc(item['title'])+'</h1>'+notice+'<p>Fonte: '+esc(item['provider'])+' / '+esc(item['source'])+'</p><p>Local: '+esc(item['location'])+' | País: '+esc(item['country'])+'</p><p>Modalidade: '+esc(item['mode'])+'</p><p>Última verificação: '+esc(item['last_seen'])+'</p><p>'+esc(item['description'])+'</p>'+action+'</main></html>'
   return self.response(page,'text/html')
  if u.path!='/':return self.response('Não encontrado','text/plain',404)
  q=p.get('q',[''])[0][:100];country=p.get('country',[''])[0][:3]
  kind=p.get('kind',['internship'])[0]
  if kind not in ('internship','employment','temporary','all'):kind='internship'
  region=p.get('region',[''])[0];mode=p.get('mode',[''])[0];area=p.get('area',[''])[0]
  try:
   offset=int(p.get('offset',[0])[0])
   records=query(q,country,kind='' if kind=='all' else kind,exclude_demo=STAGING_MODE,region=region,mode=mode,area=area,limit=31,offset=offset)
  except ValueError:return self.response('Filtro inválido','text/plain',400)
  has_more=len(records)>30;records=records[:30]
  cards=''.join('<article><h2><a href="/vaga?id='+urllib.parse.quote(j['id'],safe='')+'">'+html.escape(j['title'])+'</a></h2><p>'+html.escape(j['location'] or 'Local não informado')+' · '+html.escape(j['country'] or 'País não informado')+'</p><p>Categoria: '+html.escape({'internship':'Estágio','employment':'Emprego','temporary':'Temporária'}.get(j['kind'],'Em revisão'))+'</p><p>Área sugerida: '+html.escape(', '.join(j['areas']) or 'Não identificada')+'</p><p>Origem: '+html.escape(j['provider'])+' · '+('EXEMPLO FICTÍCIO' if j['demo'] else 'Vaga encontrada automaticamente, pendente de revisão')+'</p></article>' for j in records)
  portals=''.join('<li><a href="'+html.escape(p['url'],quote=True)+'" target="_blank" rel="noopener noreferrer">'+html.escape(p['name'])+'</a> <small>('+('integração institucional pendente' if not p['connected'] else 'conectado')+')</small></li>' for p in portals_json())
  page='''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Portal de Oportunidades | Homologação</title><style>body{font:16px system-ui;background:#f6f8fb;color:#1a2434;max-width:880px;margin:auto;padding:28px}h1{font-size:2rem}article{background:white;border:1px solid #d7dfe8;border-radius:12px;padding:16px;margin:14px 0}article h2{font-size:1.15rem}input,select,button{padding:12px;border:1px solid #9aaabc;border-radius:8px;font:inherit}button{background:#163d68;color:white;cursor:pointer}a{color:#164b84}.warn{background:#fff2d1;padding:12px;border-radius:8px}</style><h1>Portal de Oportunidades</h1><p class="warn">HOMOLOGAÇÃO. A consulta local não é uma publicação pública e as fontes exigem revisão de uso. Dados fictícios são marcados. Resultados coletados automaticamente dependem das fontes e não são oportunidades academicamente validadas.</p><form method="get"><label for="q">Pesquisar cargo ou área</label><p><input id="q" name="q" value="'''+html.escape(q,quote=True)+'''" placeholder="Ex.: Administração"><select name="kind" aria-label="Tipo de oportunidade">'''+''.join('<option value="'+k+'" '+('selected' if kind==k else '')+'>'+lab+'</option>' for k,lab in [('internship','Estágio'),('employment','Emprego'),('temporary','Temporária'),('all','Todas')])+'''</select><select name="country" aria-label="País"><option value="">Todos os países</option>'''+''.join('<option value="'+c+'" '+('selected' if country==c else '')+'>'+label+'</option>' for c,label in [('BR','Brasil'),('CA','Canadá'),('US','Estados Unidos'),('GB','Reino Unido'),('PT','Portugal')])+'''</select> <button>Pesquisar</button></p></form><p>Resultados nesta consulta: '''+str(len(records))+'''</p>'''+(cards or '<p>Nenhuma vaga encontrada.</p>')+'''<section><h2>Portais brasileiros cadastrados</h2><p>Links oficiais para consultar vagas. Ainda não são conexões automáticas.</p><ul>'''+portals+'''</ul></section><footer><small>Somente divulgação. Candidaturas realizadas no site original. Código de demonstração, não destinado a produção.</small></footer></html>'''
  from core import AREAS
  def selector(name, label, selected, options):
   choices=''.join('<option value="'+html.escape(value,quote=True)+'"'+(' selected' if value==selected else '')+'>'+html.escape(caption)+'</option>' for value,caption in options)
   return '<label>'+html.escape(label)+' <select name="'+name+'">'+choices+'</select></label> '
  filters=selector('region','Região',region,[('','Todas'),('brazil','Brasil'),('international','Exterior')])
  filters+=selector('mode','Modalidade',mode,[('','Todas'),('remote','Remota'),('hybrid','Híbrida'),('onsite','Presencial'),('unknown','Não informada')])
  filters+=selector('area','Área sugerida',area,[('','Todas')]+[(x,x) for x in AREAS])
  page=page.replace(' <button>Pesquisar</button>', ' '+filters+'<button>Pesquisar</button>')
  navigation=[]
  for target,label in ((max(0,offset-30),'Página anterior'),(offset+30,'Próxima página')):
   if (label=='Página anterior' and offset>0) or (label=='Próxima página' and has_more and target<=10000):
    params={'q':q,'country':country,'kind':kind,'region':region,'mode':mode,'area':area,'offset':target}
    navigation.append('<a href="/?'+html.escape(urllib.parse.urlencode(params),quote=True)+'">'+label+'</a>')
  page=page.replace('<section><h2>Portais brasileiros cadastrados</h2>', '<nav aria-label="Páginas">'+' | '.join(navigation)+'</nav><section><h2>Portais brasileiros cadastrados</h2>')
  if not STAGING_MODE:
   page=page.replace('Portal de Oportunidades | Homologação', 'Portal de Oportunidades | Protótipo')
   page=page.replace('HOMOLOGAÇÃO. A consulta local não é uma publicação pública e as fontes exigem revisão de uso. Dados fictícios são marcados.',
                     'Protótipo local. Anúncios fictícios são marcados e os resultados dependem das fontes consultadas.')
  self.response(page,'text/html')

def main():
 cmd=sys.argv[1] if len(sys.argv)>1 else 'help'
 if cmd=='init':init();print('Banco inicializado')
 elif cmd=='demo':demo();print('Quatro anúncios FICTÍCIOS adicionados')
 elif cmd=='serve':
  init();start_scheduler();print('Acesse http://127.0.0.1:8766');ThreadingHTTPServer(('127.0.0.1',8766),Handler).serve_forever()
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
  config=json.loads((BASE/'sources.json').read_text(encoding='utf-8'));total=0
  for source in config['sources']:
   if not source.get('enabled'):continue
   try:
    found=fetch_source(source['provider'],source['slug']);save(found);total+=len(found)
    print(source['provider'],source['slug'],len(found),'vagas com indício de estágio')
   except Exception as exc:print('Erro na fonte',source['slug'],str(exc),file=sys.stderr)
  print('Total importado:',total)
 else:print('Uso: python3 app.py init|collect-auto|serve')
if __name__=='__main__':main()
