"""Integrações brasileiras: cadastro oficial e importação consentida de arquivos CSV.

Não efetua extração de páginas privadas ou endpoints não documentados.
"""
import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

PORTALS = {
    'ciee': {'name': 'CIEE', 'url': 'https://portal.ciee.org.br/', 'integration': 'api_institucional_mediante_adesao', 'notes': 'API Vitrine de Vagas para instituições; solicitar documentação e credenciais ao CIEE.'},
    'iel': {'name': 'IEL', 'url': 'https://carreiras.iel.org.br/', 'integration': 'parceria_ou_importacao_autorizada', 'notes': 'Consultar o IEL regional sobre exportação ou integração institucional.'},
    'nube': {'name': 'Nube', 'url': 'https://www.nube.com.br/estudantes/vagas/index_html', 'integration': 'parceria_ou_importacao_autorizada', 'notes': 'Portal de oportunidades; integração automática não confirmada.'},
    'gupy': {'name': 'Gupy', 'url': 'https://portal.gupy.io/', 'integration': 'api_autenticada_por_parceiro', 'notes': 'APIs documentadas; token e permissões concedidos pelo titular da conta.'},
    'vagas': {'name': 'Vagas.com', 'url': 'https://www.vagas.com.br/', 'integration': 'parceria_ou_importacao_autorizada', 'notes': 'Integração automática não confirmada.'},
    '99jobs': {'name': '99jobs', 'url': 'https://99jobs.com/', 'integration': 'parceria_ou_importacao_autorizada', 'notes': 'Integração automática não confirmada.'},
}

COLUMNS = ['portal', 'id_externo', 'titulo', 'descricao', 'url', 'localidade', 'pais', 'modalidade', 'areas']


def import_rows(rows):
    """Normaliza registros de importação consentida e os deixa pendentes de revisão."""
    from core import classify, areas_for, clean, save
    jobs = []
    for line, row in enumerate(rows, 2):
        portal = (row.get('portal') or '').strip().lower()
        if portal not in PORTALS:
            raise ValueError(f'Linha {line}: portal não cadastrado: {portal}')
        url = (row.get('url') or '').strip()
        parsed = urlparse(url)
        if parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError(f'Linha {line}: URL HTTPS inválida')
        title = clean(row.get('titulo'))
        description = clean(row.get('descricao'))
        if not title:
            raise ValueError(f'Linha {line}: título ausente')
        kind, review = classify(title, description)
        if kind != 'internship':
            continue
        source_id = str(row.get('id_externo') or '').strip() or url
        job_id = hashlib.sha256(f'{portal}|{source_id}|{url}'.encode()).hexdigest()
        given_areas = [a.strip() for a in (row.get('areas') or '').split(';') if a.strip()]
        jobs.append({
            'id': job_id, 'provider': portal, 'source': portal,
            'external_id': source_id, 'title': title,
            'description': description[:12000], 'url': url,
            'location': clean(row.get('localidade')),
            'country': (row.get('pais') or 'BR').strip().upper(),
            'mode': (row.get('modalidade') or 'unknown').strip().lower(),
            'kind': kind, 'review_status': 'review',
            'areas': given_areas or areas_for(title, description),
            'last_seen': datetime.now(timezone.utc).isoformat(),
            'demo': 0,
        })
    save(jobs)
    return len(jobs)


def import_csv(path):
    """Importa CSV de parceiro autorizado, sem consultar os sites dos portais."""
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        missing = set(COLUMNS[:7]) - set(reader.fieldnames or [])
        if missing:
            raise ValueError('Colunas ausentes: ' + ', '.join(sorted(missing)))
        return import_rows(reader)


def portals_json():
    return [{'id': k, **v, 'connected': False} for k, v in PORTALS.items()]