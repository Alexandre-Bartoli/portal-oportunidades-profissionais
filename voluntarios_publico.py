"""Leitura experimental da listagem pública de voluntarios.com.br."""
import re
import urllib.error
import urllib.request
from datetime import date, datetime
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

from geografia import locate
from providers_extra import ListingBatch

URL='https://voluntarios.com.br/vaga/busca'
HEADERS=['Vaga','Área de trabalho na vaga','Modo de trabalho','Local','Causa','Inscrições']


class TableParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables=[];self.table=None;self.row=None;self.cell=None

    def handle_starttag(self,tag,attrs):
        if tag=='table' and self.table is None:self.table=[]
        elif self.table is not None and tag=='tr':self.row=[]
        elif self.table is not None and tag in ('td','th'):
            if self.row is None:self.row=[]
            self.cell={'tag':tag,'text':[],'links':[]}
        elif self.cell is not None and tag=='a':self.cell['links'].append(dict(attrs).get('href',''))

    def handle_data(self,data):
        if self.cell is not None:self.cell['text'].append(data)

    def handle_endtag(self,tag):
        if tag in ('td','th') and self.cell is not None:
            self.cell['text']=' '.join(''.join(self.cell['text']).split())
            self.row.append(self.cell);self.cell=None
        elif tag=='tr' and self.row is not None:
            self.table.append(self.row);self.row=None
        elif tag=='thead' and self.row is not None:
            self.table.append(self.row);self.row=None
        elif tag=='table' and self.table is not None:
            self.tables.append(self.table);self.table=None


class DetailParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth=0;self.records=0;self.title=[];self.in_title=False;self.parts=[];self.ignore=0

    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='h1' and not self.depth:self.in_title=True
        if tag=='div' and 'registro' in attrs.get('class','').split() and not self.depth:
            self.records+=1;self.depth=1;return
        if not self.depth:return
        if tag in ('script','style'):self.ignore+=1
        if tag=='div':self.depth+=1
        if tag in ('p','h3','br','li'):self.parts.append('\n')

    def handle_data(self,data):
        if self.in_title:self.title.append(data)
        if self.depth and not self.ignore:self.parts.append(data)

    def handle_endtag(self,tag):
        if tag=='h1':self.in_title=False
        if not self.depth:return
        if tag in ('script','style') and self.ignore:self.ignore-=1
        if tag in ('p','h3','li'):self.parts.append('\n')
        if tag=='div':self.depth-=1


def enrich_detail(job,page):
    import core
    if not isinstance(page,str) or len(page)>2_000_000:raise ValueError('Detalhes inválidos')
    parser=DetailParser();parser.feed(page)
    title=' '.join(''.join(parser.title).split())
    if parser.records!=1 or parser.depth or core.normalize_text(title)!=core.normalize_text(job['title']):
        raise ValueError('Detalhes não correspondem à vaga')
    lines=[' '.join(line.split()) for line in ''.join(parser.parts).splitlines()]
    lines=[line for line in lines if line]
    if not any(core.normalize_text(line)=='atividades' for line in lines):raise ValueError('Detalhes incompletos')
    entity=next((line.split(':',1)[1].strip() for line in lines if line.lower().startswith('entidade:')),None)
    result=dict(job)
    result['description']=(job['description']+'\n\n'+'\n'.join(lines))[:12000]
    result['company']=entity[:200] if entity else None
    result['areas']=sorted(set(job['areas'])|set(core.areas_for(job['title'],result['description'])))
    result['detail_enriched']=True
    return result


def parse_list(page, *, today=None):
    import core
    if not isinstance(page,str) or len(page)>2_000_000:raise ValueError('Página de voluntariado inválida')
    parser=TableParser();parser.feed(page)
    tables=[t for t in parser.tables if t and [c['text'] for c in t[0]]==HEADERS]
    if len(tables)!=1:raise ValueError('Tabela de vagas não reconhecida')
    today=today or datetime.now(ZoneInfo('America/Sao_Paulo')).date()
    jobs=[];seen=set();raw=0
    for row in tables[0][1:]:
        if len(row)!=6 or any(c['tag']!='td' for c in row):raise ValueError('Linha de vaga inválida')
        title,area,mode,location,cause,period=[c['text'] for c in row]
        links=row[0]['links']
        if not title or len(links)!=1 or not re.fullmatch(r'/vaga/\d{3}-\d{3}-\d{3}',links[0]):raise ValueError('Vaga sem identificação válida')
        if links[0] in seen:raise ValueError('Vaga duplicada na resposta')
        seen.add(links[0]);raw+=1
        start=re.match(r'^(\d{2}/\d{2}/\d{4})\b',period)
        if not start:raise ValueError('Data de início não reconhecida')
        try:opening=datetime.strptime(start.group(1),'%d/%m/%Y').date()
        except ValueError:raise ValueError('Data de início inválida') from None
        end=re.search(r'\ba\s+(\d{2}/\d{2}/\d{4})\s*$',period)
        if end:
            try:deadline=datetime.strptime(end.group(1),'%d/%m/%Y').date()
            except ValueError:raise ValueError('Prazo inválido') from None
            if deadline<today:continue
        elif not re.search(r'\bsem data limite\s*$',period,re.I):
            raise ValueError('Prazo não reconhecido')
        if opening>today:continue
        mode_value={'presencial':'onsite','remoto':'remote','hibrido':'hybrid'}.get(core.normalize_text(mode),'unknown')
        match=re.fullmatch(r'(.+?)\s*-\s*([A-Z]{2})',location)
        normalized=(match.group(1).strip()+', '+match.group(2)) if match else ('' if location=='-' else location)
        municipality=locate(normalized,'BR') if match else None
        country='BR' if municipality else None
        details='Área informada: '+area+'; causa: '+cause+'; inscrições: '+period+'.'
        job=core.make_job('voluntarios','publico',{'id':links[0].split('/')[-1], 'title':title,'description':details,'url':'https://voluntarios.com.br'+links[0], 'location':normalized,'country':country,'mode':mode_value,'kind':'volunteer'})
        if not job:raise ValueError('Vaga inválida')
        if 'ensino' in core.normalize_text(area) and 'Educação' not in job['areas']:job['areas'].append('Educação')
        if 'tecnologia' in core.normalize_text(area) and 'Tecnologia' not in job['areas']:job['areas'].append('Tecnologia')
        jobs.append(job)
    result=ListingBatch(jobs,complete=False,raw_count=raw)
    result.pages_fetched=1;result.page_limit=1
    return result


def fetch(progress_callback=None):
    from core import NoRedirectHandler
    request=urllib.request.Request(URL,headers={'User-Agent':'PortalOportunidades/0.9','Accept':'text/html'})
    with urllib.request.build_opener(NoRedirectHandler()).open(request,timeout=15) as response:
        if response.headers.get_content_type()!='text/html':raise ValueError('Formato de resposta inesperado')
        data=response.read(2_000_001)
        if len(data)>2_000_000:raise ValueError('Página excede o limite')
        jobs=parse_list(data.decode('utf-8'))
    selected=jobs[:15]
    jobs.details_attempted=len(selected);jobs.details_succeeded=0
    if progress_callback:progress_callback(0,len(selected))
    for index,job in enumerate(selected):
        try:
            request=urllib.request.Request(job['url'],headers={'User-Agent':'PortalOportunidades/0.9','Accept':'text/html'})
            with urllib.request.build_opener(NoRedirectHandler()).open(request,timeout=4) as response:
                if response.headers.get_content_type()!='text/html':raise ValueError('Formato inesperado')
                data=response.read(2_000_001)
                if len(data)>2_000_000:raise ValueError('Página excede o limite')
            jobs[index]=enrich_detail(job,data.decode('utf-8'))
            jobs.details_succeeded+=1
        except (ValueError,UnicodeError,urllib.error.URLError,TimeoutError,OSError):pass
        if progress_callback:progress_callback(index+1,len(selected))
    return jobs
