"""Extrai sedes do arquivo oficial de localidades do IBGE, sem bibliotecas externas."""
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import zipfile

EXPECTED_SHA256 = '1d96d5f0b379972a506d4b18c3696af974fbe59f8f6680557cb3a6dd38a0eb57'
MEMBER = 'BR_localidades_2022.gpkg'


def extract(archive, destination):
    archive, destination = Path(archive), Path(destination)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest != EXPECTED_SHA256:
        raise ValueError('Arquivo IBGE diferente da versão documentada')
    with tempfile.TemporaryDirectory() as temp:
        with zipfile.ZipFile(archive) as source:
            info = source.getinfo(MEMBER)
            if info.file_size > 100_000_000:
                raise ValueError('Arquivo geográfico muito grande')
            gpkg = Path(temp) / MEMBER
            with source.open(info) as src, gpkg.open('wb') as dst:
                while chunk := src.read(1024 * 1024):
                    dst.write(chunk)
        with sqlite3.connect(f'file:{gpkg}?mode=ro', uri=True) as db:
            rows = db.execute("SELECT CD_MUN,NM_MUN,SIGLA_UF,LAT_LOCALIDADE,LONG_LOCALIDADE "
                "FROM BR_localidades_2022 WHERE CT_LOCALIDADE='Cidade' AND CD_MUN=CD_LOCALIDADE "
                "ORDER BY CD_MUN").fetchall()
    seen = {}
    for code, name, uf, lat, lon in rows:
        if not (isinstance(code, str) and len(code) == 7 and code.isdigit()
                and isinstance(name, str) and isinstance(uf, str) and len(uf) == 2
                and isinstance(lat, (float, int)) and isinstance(lon, (float, int))
                and -90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError('Registro IBGE inválido')
        row = [code, name, uf, round(lat, 4), round(lon, 4)]
        if code in seen and seen[code] != row:
            raise ValueError('Coordenadas conflitantes para município')
        seen[code] = row
    if len(seen) != 5570 or len({r[2] for r in seen.values()}) != 27:
        raise ValueError('Catálogo de municípios incompleto')
    destination.mkdir(parents=True, exist_ok=True)
    for uf in sorted({row[2] for row in seen.values()}):
        records = [row for row in seen.values() if row[2] == uf]
        (destination / (uf + '.json')).write_text(json.dumps(records, ensure_ascii=False,
            separators=(',', ':')), encoding='utf-8')
    return len(seen)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('Uso: python ops/extrair_municipios_ibge.py arquivo.zip diretorio_saida')
    print('Municípios:', extract(sys.argv[1], sys.argv[2]))
