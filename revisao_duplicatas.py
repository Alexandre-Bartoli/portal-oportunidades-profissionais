"""Sinaliza anúncios possivelmente repetidos, sem alterar nem unir registros."""
import hashlib
from pathlib import Path
import sqlite3
import unicodedata


def _normalize(value):
    if not isinstance(value, str):
        return ''
    value=unicodedata.normalize('NFKC',value).casefold()
    return ' '.join(value.split())


def inspect(db_path, limit=1000):
    if type(limit) is not int or not 1 <= limit <= 5000:
        raise ValueError('Limite inválido')
    path=Path(db_path)
    if not path.is_file() or path.is_symlink():
        raise ValueError('Banco indisponível')
    with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        rows=db.execute('''SELECT id,title,description,location,country,provider,source,url
            FROM jobs WHERE active=1 AND demo=0 ORDER BY last_seen DESC,id LIMIT ?''', (limit+1,)).fetchall()
    groups={}
    for row in rows[:limit]:
        title, desc, location, country=(_normalize(row[key]) for key in ('title','description','location','country'))
        if not title or len(desc)<160 or not location or not country:
            continue
        key=(title,location,country,hashlib.sha256(desc.encode('utf-8')).hexdigest())
        groups.setdefault(key,[]).append({'id':row['id'],'title':row['title'],
            'source':str(row['provider'] or 'desconhecida')+'/'+str(row['source'] or 'desconhecida'),'url':row['url']})
    candidates=[{'reason':'titulo_local_e_descricao_iguais','jobs':group}
                for group in groups.values() if len(group)>1]
    return {'examined':min(len(rows),limit),'limit':limit,'truncated':len(rows)>limit,
            'groups':candidates,
            'note':'Possíveis duplicatas para revisão; nenhum registro foi alterado.'}
