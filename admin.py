"""Painel local, somente leitura. Não constitui configuração de produção."""
import base64
import binascii
import html
import hmac
import json
import os
import sqlite3
from pathlib import Path
import threading
import time
from urllib.parse import quote

import core
from admin_history import recent
from source_reviews import review_report
from stage_storage import backup_list, stage_paths

_init_lock = threading.Lock()


class Gate:
    def __init__(self):
        self.lock = threading.Lock()
        self.failures = {}

    def check(self, address, authorization):
        user = os.getenv('PORTAL_ADMIN_USER', '')
        password = os.getenv('PORTAL_ADMIN_PASSWORD', '')
        if (not user or len(user) > 64 or ':' in user or any(ord(c) < 33 for c in user)
                or not 32 <= len(password) <= 256):
            return 503
        now = time.monotonic()
        with self.lock:
            self.failures = {key: [t for t in times if now-t < 60]
                             for key, times in self.failures.items() if any(now-t < 60 for t in times)}
            if len(self.failures.get(address, [])) >= 5:
                return 429
            if not authorization:
                return 401
            valid = False
            if len(authorization) <= 2048 and authorization.startswith('Basic '):
                try:
                    decoded = base64.b64decode(authorization[6:], validate=True).decode('utf-8')
                    given_user, given_password = decoded.split(':', 1)
                    a = hmac.compare_digest(given_user.encode('utf-8'), user.encode('utf-8'))
                    b = hmac.compare_digest(given_password.encode('utf-8'), password.encode('utf-8'))
                    valid = a and b
                except (ValueError, UnicodeError, binascii.Error):
                    pass
            if valid:
                self.failures.pop(address, None)
                return 200
            if address not in self.failures and len(self.failures) >= 2048:
                return 429
            self.failures.setdefault(address, []).append(now)
            return 401


def authenticate(handler):
    with _init_lock:
        if not hasattr(handler.server, 'admin_gate'):
            handler.server.admin_gate = Gate()
        gate = handler.server.admin_gate
    return gate.check(handler.client_address[0], handler.headers.get('Authorization', ''))


def _read_json(path):
    try:
        path = Path(path)
        if not path.exists():
            return None
        if not path.is_file() or path.stat().st_size > 2_000_000:
            return {'status': 'unavailable'}
        data = json.loads(path.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {'status': 'unavailable'}
    except (OSError, ValueError, UnicodeError):
        return {'status': 'unavailable'}


def dashboard(staging=False):
    config = _read_json(core.BASE / 'sources.json')
    if not config:
        raise ValueError('Configuração de fontes indisponível')
    reviews = review_report(config)
    db_path, report_path = stage_paths()
    data_dir = db_path.parent if staging else core.BASE / 'data'
    status_file = report_path if staging else data_dir / 'ultima_coleta.json'
    status = _read_json(status_file) or {}
    audits = {x.get('source'): x for x in status.get('sources', []) if isinstance(x, dict)}
    review_by_source = {x['source']: x for x in reviews['sources']}
    sources = []
    for item in config['sources']:
        name = item['provider'] + '/' + item['slug']
        row = audits.get(name, {})
        sources.append({'source': name, 'enabled': item['enabled'],
                        'review': review_by_source[name]['status'],
                        'status': row.get('status'), 'checked_at': row.get('checked_at'),
                        'received': row.get('raw_count'), 'eligible': row.get('jobs'),
                        'duplicates': row.get('duplicate_records'), 'reason': row.get('reason')})
    suggestions = _read_json(data_dir / 'fontes_sugeridas.json')
    candidates = suggestions.get('candidates') if suggestions else None
    candidate_rows = ([{'source':str(x.get('provider',''))+'/'+str(x.get('slug','')),
                        'status':str(x.get('status','pendente_de_validacao'))}
                       for x in candidates[:100] if isinstance(x,dict)]
                      if isinstance(candidates,list) else None)
    links = _read_json(data_dir / 'auditoria_links.json') if staging else None
    backups = backup_list(db_path.parent / 'backups')
    history = recent()
    duplicate_review = None
    if core.DB.is_file():
        try:
            from revisao_duplicatas import inspect
            duplicate_review = inspect(core.DB)
        except (ValueError, OSError, sqlite3.Error):
            duplicate_review = {'status':'unavailable'}
    last = {'checked_at': status.get('checked_at') or status.get('finished_at'),
            'collected': status.get('records_processed', status.get('collected')),
            'active': status.get('active_real_jobs_in_staging_db', status.get('real_jobs_active')),
            'status': status.get('status')}
    alerts = []
    status_names = {'error':'erro de coleta', 'invalid_data':'dados inválidos', 'partial':'retorno parcial',
                    'pending_review':'revisão técnica pendente'}
    for row in sources:
        if row['status'] in status_names:
            alerts.append('Fonte '+row['source']+': '+status_names[row['status']])
    if reviews['status'] != 'all_enabled_reviewed':
        alerts.append('Revisão de uso das fontes pendente ou incompleta')
    if not backups:
        alerts.append('Nenhum backup local de homologação encontrado')
    if status.get('history_error'):
        alerts.append('Falha no registro do histórico da última coleta')
    if history == 'unavailable':
        alerts.append('Histórico indisponível para leitura')
    if not status:
        alerts.append('Nenhuma coleta registrada neste ambiente')
    elif status.get('status') == 'unavailable':
        alerts.append('Relatório da última coleta indisponível ou inválido')
    return {'mode': 'homologacao' if staging else 'local', 'sources': sources,
            'last_collection': last, 'history': history if history is not None else 'not_recorded',
            'suggestions_count': len(candidates) if isinstance(candidates,list) else None,
            'suggestions': candidate_rows,
            'link_check': {'checked_at': links.get('checked_at'), 'sampled': links.get('sampled'),
                           'statuses': links.get('statuses')} if links else None,
            'backups': {'scope': 'homologacao_local', 'count': len(backups),
                        'latest': backups[-1]['name'] if backups else None},
            'review_status': reviews['status'], 'alerts': alerts,
            'possible_duplicates':duplicate_review}


def render(report):
    def e(value):
        return html.escape(str('Não registrado' if value is None else value), quote=True)
    names={'ok':'Sucesso','empty':'Fonte sem anúncios','no_match':'Sem vagas elegíveis',
           'partial':'Resposta parcial','error':'Erro','invalid_data':'Dados inválidos','pending_review':'Revisão técnica pendente',
           'pending':'Pendente','rejected':'Rejeitada','invalid_evidence':'Evidência inválida',
           'approved_access_only':'Acesso técnico revisado','approved_republication':'Republicação revisada'}
    entries = ''.join('<tr><td>'+e(x['source'])+'</td><td>'+('Sim' if x['enabled'] else 'Não')+
        '</td><td>'+e(names.get(x['status'],x['status']))+'</td><td>'+e(x['checked_at'])+'</td><td>'+e(x['received'])+
        '</td><td>'+e(x['eligible'])+'</td><td>'+e(x['duplicates'])+'</td><td>'+e(x['reason'])+
        '</td><td>'+e(names.get(x['review'],x['review']))+'</td></tr>' for x in report['sources'])
    last, backup = report['last_collection'], report['backups']
    links = report['link_check']
    link_status = links.get('statuses') if links and isinstance(links.get('statuses'),dict) else None
    link_details = ', '.join(str(k)+': '+str(v) for k,v in link_status.items()) if link_status else None
    history = report['history']
    if isinstance(history, list):
        history_text = ''.join('<li>'+e(row.get('checked_at'))+' | Processadas: '+e(row.get('collected'))+
            ' | Ativas: '+e(row.get('active'))+' | Fontes com erro: '+e(row.get('errors'))+'</li>' for row in history)
        history_html = '<ul>'+history_text+'</ul>' if history else '<p>Não registrado.</p>'
    elif history == 'unavailable':
        history_html = '<p>Indisponível.</p>'
    else:
        history_html = '<p>Não registrado.</p>'
    suggestions = report.get('suggestions')
    suggestion_html = ('<ul>'+''.join('<li>'+e(x['source'])+' | '+e(x['status'])+'</li>' for x in suggestions)+'</ul>') if suggestions else '<p>Não registrado ou sem sugestões.</p>'
    alert_html = '<ul>'+''.join('<li>'+e(x)+'</li>' for x in report.get('alerts',[]))+'</ul>'
    duplicate_review=report.get('possible_duplicates')
    if duplicate_review and 'groups' in duplicate_review:
        groups=duplicate_review['groups']
        duplicate_html='<p>'+e(len(groups))+' grupos para revisão. Nenhuma vaga foi removida ou unida.</p>'
        duplicate_html+=''.join('<ul>'+''.join('<li>'+e(job['title'])+' | '+e(job['source'])+
            ' | <a href="/vaga?id='+quote(str(job['id']),safe='')+'">Consultar vaga</a></li>' for job in group['jobs'])+'</ul>' for group in groups[:100])
        if duplicate_review['truncated'] or len(groups)>100:
            duplicate_html+='<p>Exibição limitada; a análise não cobre todos os registros.</p>'
    else:
        duplicate_html='<p>Não registrado ou indisponível.</p>'
    return ('<!doctype html><html lang="pt-BR"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Administração do portal</title><style>body{font:16px system-ui;max-width:1100px;'
        'margin:auto;padding:1rem;color:#172534}table{border-collapse:collapse;width:100%}'
        'th,td{text-align:left;border:1px solid #bcc6d1;padding:.5rem}.table{overflow:auto}'
        'section{margin:1.5rem 0}code{overflow-wrap:anywhere}</style><main>'
        '<h1>Administração do portal</h1><p>Ambiente: '+e(report['mode'])+'. Consulta local e somente leitura.</p>'
        '<section><h2>Última coleta</h2><p>Data: '+e(last['checked_at'])+' | Recebidas e processadas: '+e(last['collected'])+
        ' | Vagas ativas: '+e(last['active'])+'</p><h3>Histórico de execuções</h3>'+history_html+'</section>'
        '<section><h2>Fontes e verificações</h2><div class="table"><table><thead><tr><th>Fonte</th><th>Ativa</th>'
        '<th>Resultado</th><th>Verificação</th><th>Anúncios recebidos</th><th>Vagas elegíveis</th>'
        '<th>Duplicados identificados</th><th>Motivo</th><th>Revisão de uso</th></tr></thead><tbody>'+entries+
        '</tbody></table></div><p>Revisão documental: '+e(report['review_status'])+
        '. Nenhuma fonte é ativada por este painel.</p></section>'
        '<section><h2>Operação</h2><p>Sugestões de fontes: '+e(report['suggestions_count'])+
        ' | Backups locais de homologação: '+e(backup['count'])+' | Último: '+e(backup['latest'])+
        '</p><p>Auditoria de links: '+e(links.get('checked_at') if links else None)+
        ' | Amostra: '+e(links.get('sampled') if links else None)+' | Situações: '+e(link_details)+'</p>'
        '<p>A presença de um arquivo não comprova a integridade ou restauração do backup. Backups externos e monitoramento contínuo não são comprovados aqui.</p><h3>Sugestões de fontes</h3>'+
        suggestion_html+'<h3>Possíveis duplicatas</h3>'+duplicate_html+'<h3>Alertas</h3>'+alert_html+'</section>'
        '</main></html>')
