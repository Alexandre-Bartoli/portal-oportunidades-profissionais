"""Interface pública de consulta, sem dependências externas ou JavaScript."""
import html
from urllib.parse import quote


def esc(value):
    return html.escape(str(value if value is not None else ''), quote=True)


CSS = '''
:root{color-scheme:light;--ink:#172f2a;--muted:#5e716c;--green:#24584b;--deep:#173e35;--line:#dce5de;--paper:#fff;--cream:#f6f7f1;--lime:#dceba9;--orange:#ce7954}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--cream);color:var(--ink);font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;line-height:1.5}a{color:inherit}button,input,select{font:inherit}button,a,select,input{outline-offset:3px}button:focus-visible,a:focus-visible,select:focus-visible,input:focus-visible{outline:3px solid #d57945}
.wrap{width:min(1220px,calc(100% - 64px));margin:auto}.topbar{background:#fff;border-bottom:1px solid #e9eee8}.topbar-inner{height:76px;display:flex;align-items:center;justify-content:space-between;gap:16px}.brand{display:flex;align-items:center;gap:12px;text-decoration:none}.brand-mark{width:38px;height:38px;border-radius:12px;background:var(--green);display:grid;place-items:center;color:#e8f1c8;font-weight:800;font-size:21px}.brand-name{font-weight:750;letter-spacing:-.03em;font-size:16px;line-height:1.1}.brand-name span{display:block;font-weight:500;font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#778b82;margin-top:4px}.nav-link{text-decoration:none;font-size:13px;color:#48665d;font-weight:650}.nav-link:hover{text-decoration:underline}
.hero{background:var(--deep);color:#fff;position:relative;overflow:hidden}.hero:after{content:"";position:absolute;right:-100px;top:-165px;width:470px;height:470px;border:1px solid #ffffff16;border-radius:50%;box-shadow:0 0 0 65px #ffffff08,0 0 0 130px #ffffff06;pointer-events:none}.hero-inner{padding:52px 0 57px;position:relative;z-index:1}.eyebrow{display:inline-flex;align-items:center;gap:8px;color:#d6e9bc;font-size:11px;font-weight:750;letter-spacing:.14em;text-transform:uppercase}.eyebrow:before{content:"";width:7px;height:7px;border-radius:50%;background:#cbe693}.hero h1{font-family:Georgia,serif;font-weight:400;font-size:clamp(34px,4vw,51px);letter-spacing:-.035em;line-height:1.13;margin:13px 0 12px;max-width:660px}.hero p{color:#d2ded8;max-width:620px;margin:0;font-size:15px}.hero-note{font-size:12px;color:#abc2b4;margin-top:20px}
.content{display:grid;grid-template-columns:310px minmax(0,1fr);gap:34px;align-items:start;padding:36px 0 70px}.filter-panel{background:#fff;border:1px solid var(--line);border-radius:16px;box-shadow:0 10px 28px #183e2e09;overflow:hidden}.panel-top{padding:22px 22px 17px;border-bottom:1px solid #edf1eb}.panel-top h2{font-size:17px;letter-spacing:-.03em;margin:0}.panel-top p{color:var(--muted);font-size:12px;margin:4px 0 0}.filter-body{padding:20px 22px 22px}.field{display:block;margin-bottom:17px}.field-title,.group-title{display:block;font-size:12px;font-weight:750;color:#344e45;margin-bottom:7px}.field small{display:block;color:#778780;font-size:11px;margin-top:5px;line-height:1.45}.control{width:100%;height:43px;border:1px solid #d5dfd7;border-radius:9px;background:#fff;color:#263e36;padding:0 11px;font-size:13px}.control::placeholder{color:#99a8a0}.control:focus{border-color:#4e806e}.categories{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:19px}.choice{position:relative}.choice input{position:absolute;opacity:0;inset:0;width:100%;height:100%;margin:0;cursor:pointer}.choice span{display:block;text-align:center;border:1px solid #dce5dd;padding:9px 3px;border-radius:8px;color:#496258;background:#fff;font-size:12px;font-weight:650}.choice input:checked+span{background:#e8f1dc;border-color:#6f977d;color:#244d3c}.choice input:focus-visible+span{outline:3px solid #d57945;outline-offset:2px}.field-section{padding-top:16px;margin-top:3px;border-top:1px solid #edf1eb}.field-section h3{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:#82948a;margin:0 0 16px}.search-button{width:100%;border:0;border-radius:10px;background:var(--green);color:#fff;min-height:45px;font-weight:700;cursor:pointer}.search-button:hover{background:#173e35}.clear{display:block;text-align:center;color:#587269;font-size:12px;margin-top:12px;text-decoration:none}.clear:hover{text-decoration:underline}
.results-head{display:flex;justify-content:space-between;align-items:end;gap:20px;margin:4px 0 21px}.section-kicker{color:#a55a38;font-weight:750;letter-spacing:.13em;text-transform:uppercase;font-size:10px}.results-head h2{font-family:Georgia,serif;font-weight:400;font-size:30px;letter-spacing:-.03em;line-height:1.15;margin:6px 0}.results-head p{font-size:13px;color:var(--muted);margin:0}.count{white-space:nowrap;padding:7px 11px;border-radius:999px;background:#e8eee5;color:#4b695c;font-size:12px;font-weight:700}.job-list{display:grid;gap:12px}.job-card{background:#fff;border:1px solid #e0e8e0;border-radius:14px;padding:20px 22px;transition:border-color .15s,box-shadow .15s}.job-card:hover{border-color:#a9c5ad;box-shadow:0 8px 25px #2546380c}.card-top{display:flex;justify-content:space-between;gap:15px;align-items:flex-start}.company{display:flex;align-items:center;gap:10px;color:#61776b;font-size:12px;font-weight:650}.company-mark{width:32px;height:32px;flex:none;border-radius:9px;background:#e9f0e5;display:grid;place-items:center;color:#53755f;font-weight:750}.job-title{font-size:18px;line-height:1.3;letter-spacing:-.025em;margin:13px 0 9px}.job-title a{text-decoration:none}.job-title a:hover{text-decoration:underline;color:#27634f}.meta{color:#687e72;font-size:12px;display:flex;gap:7px;flex-wrap:wrap}.meta span:not(:last-child):after{content:"·";margin-left:7px;color:#bac7bd}.card-bottom{display:flex;align-items:center;justify-content:space-between;gap:12px;border-top:1px solid #edf1eb;margin-top:18px;padding-top:14px}.pills{display:flex;flex-wrap:wrap;gap:6px}.pill{padding:4px 9px;background:#edf4e9;color:#4e7258;border-radius:6px;font-size:11px;font-weight:700}.pill.soft{background:#f5f4ef;color:#747b70}.pill.demo{background:#fff1d7;color:#8e6020}.detail-link{font-size:12px;color:#24634e;font-weight:750;text-decoration:none;white-space:nowrap}.detail-link:hover{text-decoration:underline}.empty{background:#fff;border:1px dashed #c8d8cb;border-radius:14px;padding:50px 28px;text-align:center}.empty-symbol{width:47px;height:47px;border-radius:50%;background:#eef4e9;margin:0 auto 13px;display:grid;place-items:center;font-size:22px;color:#668771}.empty h3{font-size:17px;margin:0 0 6px}.empty p{font-size:13px;color:var(--muted);margin:0}.pagination{display:flex;gap:10px;justify-content:flex-end;margin-top:20px}.pagination a{padding:9px 14px;border:1px solid #d9e4d9;border-radius:8px;text-decoration:none;background:#fff;font-size:12px;font-weight:700}.portal-list{margin-top:32px;padding-top:25px;border-top:1px solid #dde6dc}.portal-list h3{font-family:Georgia,serif;font-weight:400;font-size:23px;margin:0 0 5px}.portal-list p{font-size:12px;color:var(--muted);margin:0 0 12px}.portal-list ul{list-style:none;padding:0;display:flex;gap:8px;flex-wrap:wrap}.portal-list li a{display:block;padding:7px 10px;border:1px solid #dce5db;border-radius:8px;color:#436457;background:#fff;text-decoration:none;font-size:12px;font-weight:650}.portal-list li a:hover{border-color:#82a58f}.footer{border-top:1px solid #e2e9df;padding:22px 0;color:#71877b;font-size:12px}.footer-inner{display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap}.footer a{color:#536d60}.notice{background:#f9f5e8;color:#755d35;border:1px solid #eee2c0;border-radius:10px;padding:12px 14px;font-size:12px;margin-bottom:18px}
@media(max-width:800px){.wrap{width:min(100% - 36px,640px)}.topbar-inner{height:68px}.hero-inner{padding:37px 0 42px}.hero h1{font-size:37px}.hero:after{opacity:.5}.content{grid-template-columns:1fr;gap:30px;padding-top:22px}.filter-body{display:grid;grid-template-columns:1fr 1fr;gap:0 14px}.filter-body>.full,.filter-body>.field-section{grid-column:1/-1}.filter-body .field-section{display:grid;grid-template-columns:1fr 1fr;gap:0 14px}.filter-body .field-section h3{grid-column:1/-1}.results-head h2{font-size:27px}}@media(max-width:470px){.wrap{width:calc(100% - 28px)}.brand-name{font-size:14px}.hero h1{font-size:34px}.hero p{font-size:14px}.filter-body{display:block}.filter-body .field-section{display:block}.job-card{padding:18px}.card-bottom{align-items:flex-start;flex-direction:column}.detail-link{padding-top:4px}.count{font-size:11px}.results-head{gap:8px}}
.detail-wrap{max-width:900px;padding:35px 0 70px}.back-link{display:inline-block;color:#587368;font-size:13px;font-weight:700;text-decoration:none;margin-bottom:20px}.detail-box{background:#fff;border:1px solid var(--line);border-radius:16px;padding:34px;box-shadow:0 10px 28px #183e2e09}.detail-box h1{font-family:Georgia,serif;font-size:clamp(29px,4vw,43px);line-height:1.17;letter-spacing:-.025em;font-weight:400;margin:12px 0}.detail-info{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin:25px 0;padding:20px 0;border-top:1px solid #edf1eb;border-bottom:1px solid #edf1eb}.detail-info span{display:block;color:#7b9084;font-size:11px;font-weight:750;text-transform:uppercase;letter-spacing:.05em}.detail-info strong{display:block;font-size:13px;font-weight:650;margin-top:4px;overflow-wrap:anywhere}.detail-description{white-space:pre-wrap;overflow-wrap:anywhere;color:#394f46;font-size:14px;line-height:1.75}.detail-box h2{font-size:17px;margin-top:28px}.detail-action{display:inline-block;padding:12px 18px;background:var(--green);color:#fff;text-decoration:none;border-radius:9px;font-size:13px;font-weight:750;margin-top:20px}.detail-action:hover{background:var(--deep)}.detail-warning{background:#faf5e8;border:1px solid #eee3c6;border-radius:10px;padding:12px 18px;margin-top:25px;font-size:13px}.detail-warning h2{margin:2px 0 5px}.detail-warning ul{padding-left:18px}.detail-notice{color:#75887d;font-size:12px;margin-top:16px}@media(max-width:600px){.detail-box{padding:23px}.detail-info{grid-template-columns:1fr 1fr}}
'''


def options(name, label, selected, items, help_text=''):
    values=''.join('<option value="'+esc(value)+'"'+(' selected' if str(value)==str(selected) else '')+'>'+esc(caption)+'</option>' for value,caption in items)
    return '<label class="field"><span class="field-title">'+esc(label)+'</span><select class="control" name="'+esc(name)+'">'+values+'</select>'+('<small>'+esc(help_text)+'</small>' if help_text else '')+'</label>'


def shell_start(title):
    return '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+esc(title)+'</title><style>'+CSS+'</style></head><body><header class="topbar"><div class="wrap topbar-inner"><a class="brand" href="/"><span class="brand-mark" aria-hidden="true">✳</span><span class="brand-name">Oportunidades<span>Portal de vagas</span></span></a><a class="nav-link" href="/admin">Administração ↗</a></div></header>'


def footer():
    return '<footer class="footer"><div class="wrap footer-inner"><span>Portal de Oportunidades · Consulta local</span><span>Confira os detalhes no anúncio original.</span></div></footer></body></html>'


def render_detail(item, link, link_label, flags):
    labels={'selecao_interna':'Possível seleção interna','pagamento_suspeito':'Possível cobrança relacionada à inscrição',
            'modalidade_hibrida':'Descrição menciona trabalho híbrido','presencial':'Descrição menciona trabalho presencial',
            'modalidade_inconsistente':'Modalidade pode divergir da descrição'}
    def value(x): return esc(x or 'Não informado')
    details=[('Empresa',item.get('company')),('Fonte',item.get('provider')),('Local',item.get('location')),
             ('País',item.get('country')),('Modalidade',{'remote':'Remota','hybrid':'Híbrida','onsite':'Presencial'}.get(item.get('mode'))),
             ('Data de publicação',item.get('published_at'))]
    facts=''.join('<div aria-label="'+esc(label)+': '+value(data)+'"><span>'+esc(label)+'</span><strong>'+value(data)+'</strong></div>' for label,data in details)
    notice='EXEMPLO FICTÍCIO' if item.get('demo') else 'Dados coletados automaticamente, sujeitos a revisão.'
    warning=('<section class="detail-warning"><h2>Sinais para conferir</h2><p>São indícios automáticos, não conclusões. Confira no anúncio original.</p><ul>'+''.join('<li>'+esc(labels.get(f['type'],f['type']))+': '+esc(f['evidence'])+'</li>' for f in flags)+'</ul></section>') if flags else ''
    action='<a class="detail-action" rel="noopener noreferrer" href="'+esc(link)+'">'+esc(link_label)+' ↗</a>' if link else '<p>Link não confirmado. Consulte o site oficial da fonte para verificar a oportunidade.</p>'
    return shell_start(item['title'])+'<main class="wrap detail-wrap"><a class="back-link" href="/">← Voltar à pesquisa</a><article class="detail-box"><span class="section-kicker">Detalhes da oportunidade</span><h1>'+value(item['title'])+'</h1><p class="detail-notice">'+notice+'</p><div class="detail-info">'+facts+'</div><h2>Sobre a vaga</h2><div class="detail-description">'+value(item.get('description'))+'</div>'+warning+action+'<p class="detail-notice">Última verificação na coleta: '+value(item.get('last_seen'))+'</p></article></main>'+footer()


def render_search(jobs, filters, areas, states, cities, navigation, staging, portals=(), error_message=''):
    categories=[('all','Todas'),('internship','Estágio'),('employment','Emprego'),('temporary','Temporária')]
    choices=''.join('<label class="choice"><input type="radio" name="kind" value="'+value+'"'+(' checked' if filters['kind']==value else '')+'><span>'+label+'</span></label>' for value,label in categories)
    panel='<aside class="filter-panel"><div class="panel-top"><h2>Refine sua busca</h2><p>Escolha o que faz sentido para você.</p></div><form class="filter-body" method="get" action="/">'
    panel+='<label class="field full"><span class="field-title">Cargo ou palavra-chave</span><input class="control" name="q" type="search" value="'+esc(filters['q'])+'" placeholder="Ex.: psicologia, administração"></label>'
    panel+='<fieldset class="full" style="border:0;padding:0;margin:0"><legend class="group-title">Tipo de oportunidade</legend><div class="categories">'+choices+'</div></fieldset>'
    panel+='<div class="field-section"><h3>Onde e como</h3>'
    panel+=options('region','Região',filters['region'],[('','Todas as regiões'),('brazil','Brasil'),('international','Exterior')])
    panel+=options('country','País',filters['country'],[('','Todos os países'),('BR','Brasil'),('CA','Canadá'),('US','Estados Unidos'),('GB','Reino Unido'),('DE','Alemanha'),('SA','Arábia Saudita'),('AU','Austrália'),('KR','Coreia do Sul'),('AE','Emirados Árabes Unidos'),('ES','Espanha'),('FR','França'),('NL','Holanda'),('IE','Irlanda'),('IT','Itália'),('JP','Japão'),('PT','Portugal'),('SG','Singapura'),('SE','Suécia')])
    panel+=options('mode','Modalidade',filters['mode'],[('','Todas as modalidades'),('remote','Remota'),('hybrid','Híbrida'),('onsite','Presencial'),('unknown','Não informada')])
    panel+=options('area','Área sugerida',filters['area'],[('','Todas as áreas')]+[(x,x) for x in areas])
    panel+=options('published_days','Data de publicação',filters.get('published_days',''),[('','Qualquer data'),('7','Últimos 7 dias'),('14','Últimos 14 dias'),('30','Últimos 30 dias'),('90','Últimos 90 dias')], 'Sem data informada, a vaga continua aparecendo.')
    panel+=options('uf','Estado',filters['uf'],[('','Todos os estados')]+states)
    panel+='<button class="control" type="submit" name="load_cities" value="1" formnovalidate>Carregar municípios</button>'
    panel+=options('municipality','Município',filters['municipality'],[('','Todos os municípios')]+cities if filters['uf'] else [('','Selecione o estado primeiro')], 'Selecione o estado e clique em Carregar municípios.')
    panel+='<label class="field"><span class="field-title">Raio em quilômetros</span><input class="control" name="radius_km" type="number" min="0" max="2000" step="1" value="'+esc(filters['radius_km'])+'" placeholder="Ex.: 50"><small>Escolha um município. O raio é medido em linha reta a partir da sede municipal, não da sua localização atual.</small></label></div>'
    online='' if staging else ' formmethod="post" formaction="/buscar-agora"'
    panel+='<div class="full"><button class="search-button" type="submit"'+online+'>Buscar oportunidades &nbsp; →</button><small>Ao buscar, o cargo e a localização escolhidos podem ser enviados às fontes consultadas.</small><a class="clear" href="/?kind=all">Limpar filtros</a></div></form></aside>'
    cards=[]
    for job in jobs:
        ident=quote(str(job['id']),safe='');title=esc(job['title']);company=job.get('company') or 'Empresa não informada'
        kind={'internship':'Estágio','employment':'Emprego','temporary':'Temporária'}.get(job['kind'],'Em revisão')
        mode={'remote':'Remoto','hybrid':'Híbrido','onsite':'Presencial'}.get(job.get('mode'),'Modalidade não informada')
        location=job.get('location') or 'Local não informado'; area=', '.join(job.get('areas') or [])
        distance=('<span>Distância aproximada: '+esc(job['distance_km'])+' km</span>') if 'distance_km' in job else ''
        demo='<span class="pill demo">EXEMPLO FICTÍCIO</span>' if job.get('demo') else ''
        cards.append('<article class="job-card"><div class="card-top"><div class="company"><span class="company-mark" aria-hidden="true">'+esc(str(company)[:1].upper())+'</span><span>'+esc(company)+'</span></div><span class="pill soft">'+esc(job['provider'])+'</span></div><h3 class="job-title"><a href="/vaga?id='+ident+'">'+title+'</a></h3><div class="meta"><span>'+esc(location)+'</span><span>'+esc(mode)+'</span>'+distance+'</div><div class="card-bottom"><div class="pills"><span class="pill">'+esc(kind)+'</span>'+(('<span class="pill soft">'+esc(area)+'</span>') if area else '')+demo+'</div><a class="detail-link" href="/vaga?id='+ident+'">Ver oportunidade →</a></div></article>')
    cards_html='' if error_message else (''.join(cards) or '<div class="empty"><div class="empty-symbol" aria-hidden="true">⌕</div><h3>Nenhuma vaga encontrada</h3><p>Tente ampliar a busca ou limpar alguns filtros.</p></div>')
    nav='<nav class="pagination" aria-label="Páginas">'+''.join('<a href="'+esc(url)+'">'+esc(label)+'</a>' for url,label in navigation)+'</nav>' if navigation else ''
    portal_links=''.join('<li><a href="'+esc(p['url'])+'" target="_blank" rel="noopener noreferrer">'+esc(p['name'])+' ↗</a></li>' for p in portals)
    directory=('<section class="portal-list"><h3>Outros lugares para pesquisar</h3><p>Portais com consulta diretamente na fonte.</p><ul>'+portal_links+'</ul></section>') if portal_links else ''
    notice='Ambiente de homologação. Os anúncios são coletados automaticamente e podem precisar de revisão.' if staging else 'Protótipo local. Os resultados dependem das fontes consultadas e podem ser parciais. Confira as informações no anúncio original.'
    alert='<div class="notice" role="alert">'+esc(error_message)+'</div>' if error_message else ''
    body=shell_start('Portal de Oportunidades')+'<section class="hero"><div class="wrap hero-inner"><div class="eyebrow">Um lugar para descobrir possibilidades</div><h1>Encontre oportunidades<br>para o seu próximo passo.</h1><p>Pesquise vagas de estágio, emprego e trabalho temporário em um só lugar.</p><div class="hero-note">Consulte os detalhes e candidate-se na fonte original.</div></div></section><main class="wrap content">'+panel+'<section aria-labelledby="results-title">'+alert+'<div class="notice">'+notice+'</div><div class="results-head"><div><span class="section-kicker">Explore as vagas</span><h2 id="results-title">Oportunidades para você</h2><p>Resultados de acordo com os filtros selecionados.</p></div><span class="count">'+str(len(jobs))+' nesta página</span></div><div class="job-list">'+cards_html+'</div>'+nav+'<div class="notice" style="margin-top:24px">No filtro por município e raio, a distância em linha reta é aproximada entre sedes municipais. Vagas remotas e vagas sem localização suficiente não aparecem nessa pesquisa.</div>'+directory+'</section></main>'+footer()
    return body


def render_progress(state, ident):
    from urllib.parse import urlencode
    filters=state['filters']
    result_url='/?'+urlencode({**filters,'search_id':ident})
    progress_url='/busca-progresso?id='+quote(ident,safe='')
    running=state['status']=='running'
    if running:
        meta='<meta http-equiv="refresh" content="2;url='+esc(progress_url)+'">'
    elif not state['failed'] and not state.get('details_failed'):
        meta='<meta http-equiv="refresh" content="2;url='+esc(result_url)+'">'
    else:
        meta=''
    header=shell_start('Atualizando oportunidades').replace('</head>',meta+'</head>')
    total=state['total'];done=state['done']
    detail_total=state.get('detail_total',0);detail_done=state.get('detail_done',0)
    fraction=min(99,round(100*detail_done/detail_total)) if running and detail_total else 0
    value=done*100+fraction
    status='Consultando '+esc(state['current']) if running else 'Consulta concluída'
    details=('<p>Não foi possível concluir '+str(state['failed'])+' consulta(s). Os resultados incluem apenas as fontes que responderam.</p>' if state['failed'] else '')
    if not running:
        details+='<p>'+str(state['saved'])+' oportunidade(s) encontradas nesta consulta.</p>'
    if state.get('details_failed'):
        details+='<p>'+str(state['details_failed'])+' detalhes não puderam ser consultados. Algumas vagas podem não aparecer nos filtros de localização.</p>'
    action='' if running else '<a class="detail-action" href="'+esc(result_url)+'">Ver resultados</a>'
    body=('<main class="wrap detail-wrap"><article class="detail-box"><h1>Atualizando oportunidades</h1>'
          '<p>'+status+'</p><progress value="'+str(value)+'" max="'+str(total*100)+'" style="width:100%"></progress>'
          '<p>'+str(done)+' de '+str(total)+' fontes consultadas.</p>'+details+action+
          '<p class="detail-notice">A consulta usa as fontes configuradas para a região escolhida. Algumas enviam todos os anúncios para filtragem no portal. As fontes e o número de anúncios consultados são limitados, por isso pode haver outras vagas. No filtro por raio, são consultados até cinco estados.</p>'
          '</article></main>')
    return header+body+footer()
