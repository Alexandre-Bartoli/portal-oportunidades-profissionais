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


def fetch():
    from core import NoRedirectHandler
    request=urllib.request.Request(URL,headers={'User-Agent':'PortalOportunidades/0.9','Accept':'text/html'})
    with urllib.request.build_opener(NoRedirectHandler()).open(request,timeout=15) as response:
        if response.headers.get_content_type()!='text/html':raise ValueError('Formato de resposta inesperado')
        data=response.read(2_000_001)
        if len(data)>2_000_000:raise ValueError('Página excede o limite')
        return parse_list(data.decode('utf-8'))
