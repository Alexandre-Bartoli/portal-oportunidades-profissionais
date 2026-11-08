"""Sinais explicáveis encontrados no anúncio, nunca decisões sobre elegibilidade.

As ideias de verificação do texto foram inspiradas no posting_signals.py de
Mads Lorentzen e no Job Pindorama. Regras reescritas para o portal.
"""
import re

PATTERNS = {
    'selecao_interna': [r'\b(?:processo seletivo|recrutamento) interno\b', r'\binternal applicants only\b',
                        r'\bexclusiv[oa]\s+(?:para|a)\s+(?:colaboradores|funcion[aá]rios)\b'],
    'pagamento_suspeito': [r'\b(?:pague|dep[oó]sito|pix)\b.{0,45}\b(?:taxa|inscri[çc][ãa]o|vaga|contrata[çc][ãa]o)\b',
                           r'\b(?:taxa|inscri[çc][ãa]o)\b.{0,40}\b(?:pix|dep[oó]sito)\b'],
    'modalidade_hibrida': [r'\b(?:modelo|regime|trabalho|atua[çc][ãa]o)\s+(?:de\s+trabalho\s+)?h[íi]brid[oa]\b',
                            r'\b\d+\s+dias?\s+(?:por semana\s+)?(?:no escrit[oó]rio|presencia(?:l|is))\b'],
    'presencial': [r'\b(?:100\s*%\s*presencial|fully on.site)\b'],
}


def analyze(title='', description='', mode='unknown'):
    text = str(title or '') + '\n' + str(description or '')
    flags = []
    for label, patterns in PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                flags.append({'type': label, 'evidence': match.group(0)[:120]})
                break
    if mode == 'remote' and any(x['type'] in ('modalidade_hibrida', 'presencial') for x in flags):
        flags.append({'type': 'modalidade_inconsistente', 'evidence': 'Rótulo remoto contradiz a descrição'})
    return flags
