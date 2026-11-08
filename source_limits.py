"""Limite persistente de consultas para fontes com frequência restrita."""
from pathlib import Path
import sqlite3
import time


class RateLimited(RuntimeError):
    pass


def acquire(provider, db_path, *, now=None):
    if provider != 'remotive':
        raise ValueError('Fonte sem política de limite configurada')
    path=Path(db_path)
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.is_symlink():
        raise ValueError('Arquivo de limite inseguro')
    timestamp=time.time() if now is None else float(now)
    with sqlite3.connect(path,timeout=5,isolation_level=None) as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('CREATE TABLE IF NOT EXISTS limits (provider TEXT PRIMARY KEY, last_attempt REAL NOT NULL)')
        row=db.execute('SELECT last_attempt FROM limits WHERE provider=?',(provider,)).fetchone()
        if row and timestamp-row[0]<21600:
            db.rollback()
            raise RateLimited('Limite de consultas Remotive: aguarde seis horas')
        db.execute('INSERT INTO limits(provider,last_attempt) VALUES (?,?) '
                   'ON CONFLICT(provider) DO UPDATE SET last_attempt=excluded.last_attempt',(provider,timestamp))
        db.commit()
