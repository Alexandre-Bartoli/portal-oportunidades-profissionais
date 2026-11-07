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

class Handler(BaseHTTPRequestHandler):
 def response(self,body,content_type='application/json',status=200):
  payload=body.encode('utf-8');self.send_response(status)
  self.send_header('Content-Type',content_type+'; charset=utf-8')
  self.send_header('Content-Length',str(len(payload)))
  self.send_header('X-Content-Type-Options','nosniff')
  self.send_header('Content-Security-Policy',"default-src 'none'; style-src 'unsafe-inline'")
  self.end_headers();self.wfile.write(payload)
 def do_GET(self):
  u=urllib.parse.urlparse(self.path);p=urllib.parse.parse_qs(u.query)
  if u.path=='/api/collection-status':return self.response(json.dumps(collection_status(),ensure_ascii=False))
  if u.path=='/api/providers':
   from provider_catalog import CATALOG
   return self.response(json.dumps({'providers':CATALOG},ensure_ascii=False))
  if u.path=='/api/health':return self.response(json.dumps({'status':'ok','version':'0.6-experimental'}))
  if u.path=='/api/portals':return self.response(json.dumps({'portals':portals_json()},ensure_ascii=False))
  if u.path=='/api/jobs':
   try:
    kind=p.get('kind',['internship'])[0]
    if kind not in ('internship','employment','temporary','all'):return self.response('{"error":"Categoria inválida"}',status=400)
    result=query(q=p.get('q',[''])[0][:100],country=p.get('country',[''])[0][:3],kind='' if kind=='all' else kind,limit=p.get('limit',[30])[0])
    for item in result:item['signals']=analyze(item['title'],item['description'],item['mode'])
    return self.response(json.dumps({'count':len(result),'results':result},ensure_ascii=False))
   except ValueError:return self.response('{"error":"Parâmetro inválido"}',status=400)
  if u.path!='/':return self.response('Não encontrado','text/plain',404)
  q=p.get('q',[''])[0][:100];country=p.get('country',[''])[0][:3]
  kind=p.get('kind',['internship'])[0]
  if kind not in ('internship','employment','temporary','all'):kind='internship'
  records=query(q,country,kind='' if kind=='all' else kind)
  cards=''.join('<article><h2>'+html.escape(j['title'])+'</h2><p>'+html.escape(j['location'] or 'Local não informado')+' · '+html.escape(j['country'] or 'País não informado')+'</p><p>Categoria: '+html.escape({'internship':'Estágio','employment':'Emprego','temporary':'Temporária'}.get(j['kind'],'Em revisão'))+'</p><p>Área sugerida: '+html.escape(', '.join(j['areas']) or 'Não identificada')+'</p><p>Origem: '+html.escape(j['provider'])+' · '+('EXEMPLO FICTÍCIO' if j['demo'] else 'Vaga encontrada automaticamente, pendente de revisão')+'</p><a rel="noopener noreferrer" target="_blank" href="'+html.escape(j['url'],quote=True)+'">Consultar origem</a></article>' for j in records)
  portals=''.join('<li><a href="'+html.escape(p['url'],quote=True)+'" target="_blank" rel="noopener noreferrer">'+html.escape(p['name'])+'</a> <small>('+('integração institucional pendente' if not p['connected'] else 'conectado')+')</small></li>' for p in portals_json())
  page='''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Portal de Oportunidades | POC</title><style>body{font:16px system-ui;background:#f6f8fb;color:#1a2434;max-width:880px;margin:auto;padding:28px}h1{font-size:2rem}article{background:white;border:1px solid #d7dfe8;border-radius:12px;padding:16px;margin:14px 0}article h2{font-size:1.15rem}input,select,button{padding:12px;border:1px solid #9aaabc;border-radius:8px;font:inherit}button{background:#163d68;color:white;cursor:pointer}a{color:#164b84}.warn{background:#fff2d1;padding:12px;border-radius:8px}</style><h1>Portal de Oportunidades</h1><p class="warn">Protótipo de pesquisa. Dados fictícios são marcados. Resultados coletados automaticamente dependem das fontes e não são oportunidades academicamente validadas.</p><form method="get"><label for="q">Pesquisar cargo ou área</label><p><input id="q" name="q" value="'''+html.escape(q,quote=True)+'''" placeholder="Ex.: Administração"><select name="kind" aria-label="Tipo de oportunidade">'''+''.join('<option value="'+k+'" '+('selected' if kind==k else '')+'>'+lab+'</option>' for k,lab in [('internship','Estágio'),('employment','Emprego'),('temporary','Temporária'),('all','Todas')])+'''</select><select name="country" aria-label="País"><option value="">Todos os países</option>'''+''.join('<option value="'+c+'" '+('selected' if country==c else '')+'>'+label+'</option>' for c,label in [('BR','Brasil'),('CA','Canadá'),('US','Estados Unidos'),('GB','Reino Unido'),('PT','Portugal')])+'''</select> <button>Pesquisar</button></p></form><p>Resultados nesta consulta: '''+str(len(records))+'''</p>'''+(cards or '<p>Nenhuma vaga encontrada.</p>')+'''<section><h2>Portais brasileiros cadastrados</h2><p>Links oficiais para consultar vagas. Ainda não são conexões automáticas.</p><ul>'''+portals+'''</ul></section><footer><small>Somente divulgação. Candidaturas realizadas no site original. Código de demonstração, não destinado a produção.</small></footer></html>'''
  self.response(page,'text/html')

def main():
 cmd=sys.argv[1] if len(sys.argv)>1 else 'help'
 if cmd=='init':init();print('Banco inicializado')
 elif cmd=='demo':demo();print('Quatro anúncios FICTÍCIOS adicionados')
 elif cmd=='serve':
  init();start_scheduler();print('Acesse http://127.0.0.1:8766');ThreadingHTTPServer(('127.0.0.1',8766),Handler).serve_forever()
 elif cmd=='collect-auto':
  print(json.dumps(collect_once(),ensure_ascii=False,indent=2))
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