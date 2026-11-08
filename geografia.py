"""Referências municipais do IBGE; coordenadas representam sedes, não endereços."""
import json
import math
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent / 'data_geo'


def _key(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', value.casefold())
                   if not unicodedata.combining(c)).strip()


@lru_cache(maxsize=1)
def catalog():
    rows = []
    for path in sorted(DATA.glob('[A-Z][A-Z].json')):
        rows.extend(json.loads(path.read_text(encoding='utf-8')))
    by_code = {row[0]: row for row in rows}
    by_name = {}
    for row in rows:
        key = (_key(row[1]), row[2])
        by_name.setdefault(key, []).append(row[0])
    return by_code, by_name


def municipalities(uf=''):
    return sorted((r for r in catalog()[0].values() if not uf or r[2] == uf),
                  key=lambda r: _key(r[1]))


def locate(location, country):
    if country != 'BR' or not isinstance(location, str):
        return None
    match = re.fullmatch(r'\s*([^,;/]+),\s*([A-Za-z]{2})(?:,\s*(?:Brasil|Brazil))?\s*', location, re.I)
    if not match:
        return None
    matches = catalog()[1].get((_key(match.group(1)), match.group(2).upper()), [])
    return matches[0] if len(matches) == 1 else None


def distance_km(code_a, code_b):
    a, b = catalog()[0].get(code_a), catalog()[0].get(code_b)
    if not a or not b:
        return None
    lat1, lon1, lat2, lon2 = map(math.radians, (a[3], a[4], b[3], b[4]))
    h = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return 6371.0088 * 2 * math.asin(min(1.0, math.sqrt(h)))
