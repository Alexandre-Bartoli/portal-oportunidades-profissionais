"""Catálogo de conectores disponíveis no código, não lista de fontes autorizadas.

`enabled` e os identificadores de cada empresa pertencem a sources.json.
`experimental` indica que a coleta real ainda não foi validada para a plataforma.
"""
CATALOG = [
    {'provider': 'greenhouse', 'scope': 'companies', 'experimental': True,
     'endpoint': 'boards-api.greenhouse.io', 'configured_automatically': False},
    {'provider': 'lever', 'scope': 'companies', 'experimental': True,
     'endpoint': 'api.lever.co', 'configured_automatically': False},
    {'provider': 'ashby', 'scope': 'companies', 'experimental': True,
     'endpoint': 'api.ashbyhq.com', 'configured_automatically': False},
    {'provider': 'gupy', 'scope': 'brazil_search', 'experimental': True,
     'endpoint': 'portal.gupy.io', 'configured_automatically': False},
    {'provider': 'smartrecruiters', 'scope': 'companies', 'experimental': True,
     'endpoint': 'api.smartrecruiters.com', 'configured_automatically': False},
    {'provider': 'breezy', 'scope': 'companies', 'experimental': True,
     'endpoint': '*.breezy.hr', 'configured_automatically': False},
]