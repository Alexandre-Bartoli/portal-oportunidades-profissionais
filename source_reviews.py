"""Revisão documental por fonte. Nenhuma aprovação é inferida de respostas HTTP."""
from datetime import date
from urllib.parse import urlsplit

from source_quality import validate_sources


VALID_SCOPES = {'technical_access', 'republication'}
REVIEW_REQUIRED_PROVIDERS = frozenset({'gupy','solides','remotive','workable','inhire'})


def pending_technical_review(entry):
    if (entry.get('provider') in {'gupy', 'inhire'} and entry.get('experimental_access') is True
            and entry.get('usage_review', 'pending') == 'pending'):
        return False
    return entry['provider'] in REVIEW_REQUIRED_PROVIDERS and not source_review(entry)['technical_probe_allowed']


def source_review(entry):
    status = entry.get('usage_review', 'pending')
    key = f"{entry['provider']}/{entry['slug']}"
    result = {'source': key, 'enabled': entry['enabled'], 'status': 'pending',
              'technical_probe_allowed': False, 'republication_reviewed': False}
    if status == 'rejected':
        result['status'] = 'rejected'
        return result
    if status == 'pending':
        if entry.get('provider') in {'gupy', 'inhire'} and entry.get('experimental_access') is True:
            result['technical_probe_allowed'] = True
            result['experimental_access'] = True
        return result
    if status != 'approved':
        result['status'] = 'invalid_evidence'
        return result
    evidence = entry.get('usage_evidence_url', '')
    reviewer = entry.get('usage_reviewed_by', '')
    reviewed_at = entry.get('usage_reviewed_at', '')
    scope = entry.get('usage_scope')
    try:
        parsed = urlsplit(evidence)
        valid_url = parsed.scheme == 'https' and bool(parsed.hostname) and not parsed.username and not parsed.password
        valid_date = date.fromisoformat(reviewed_at) <= date.today()
    except (ValueError, TypeError):
        valid_url = False
        valid_date = False
    if not (valid_url and valid_date and isinstance(reviewer, str) and reviewer.strip() and scope in VALID_SCOPES):
        result['status'] = 'invalid_evidence'
        return result
    result.update(status='approved_access_only' if scope == 'technical_access' else 'approved_republication',
                  technical_probe_allowed=True, republication_reviewed=scope == 'republication')
    return result


def review_report(config):
    validate_sources(config)
    entries = [source_review(s) for s in config['sources']]
    enabled = [e for e in entries if e['enabled']]
    return {'schema_version':1, 'status':('no_enabled_sources' if not enabled else ('manual_review_required' if any(not e['republication_reviewed'] for e in enabled) else 'all_enabled_reviewed')),
            'enabled_sources':len(enabled),
            'technical_probes_allowed':sum(e['technical_probe_allowed'] for e in enabled),
            'republication_reviews_completed':sum(e['republication_reviewed'] for e in enabled),
            'sources':entries,
            'note':'Avaliação documental inserida pelo operador; não constitui parecer jurídico automático.'}
