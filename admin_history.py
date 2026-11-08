"""Histórico local de contagens, separado para cada banco de dados."""
import sqlite3

import core


def record(entry):
    with core.connect() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS collection_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT, checked_at TEXT NOT NULL, mode TEXT NOT NULL,
            collected INTEGER, active INTEGER, success INTEGER, errors INTEGER)''')
        db.execute('''INSERT INTO collection_history
            (checked_at,mode,collected,active,success,errors) VALUES (?,?,?,?,?,?)''',
            tuple(entry.get(k) for k in ('checked_at','mode','collected','active','success','errors')))


def recent(limit=30):
    path = core.DB
    if not path.is_file():
        return None
    try:
        with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
            db.row_factory = sqlite3.Row
            exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='collection_history'").fetchone()
            if not exists:
                return None
            return [dict(x) for x in db.execute('''SELECT checked_at,mode,collected,active,success,errors
                FROM collection_history ORDER BY id DESC LIMIT ?''', (min(max(int(limit),1),100),))]
    except (sqlite3.Error, OSError):
        return 'unavailable'
