"""Histórico local de contagens, separado para cada banco de dados."""
import sqlite3

import core


def record_source(provider,slug,status,received=None,incomplete=None):
    with core.connect() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS source_observations
            (provider TEXT NOT NULL, slug TEXT NOT NULL, checked_at TEXT NOT NULL, status TEXT NOT NULL, received INTEGER, incomplete INTEGER)''')
        columns={x[1] for x in db.execute('PRAGMA table_info(source_observations)')}
        if 'received' not in columns:db.execute('ALTER TABLE source_observations ADD COLUMN received INTEGER')
        if 'incomplete' not in columns:db.execute('ALTER TABLE source_observations ADD COLUMN incomplete INTEGER')
        db.execute("DELETE FROM source_observations WHERE checked_at < datetime('now','-30 days')")
        db.execute("INSERT INTO source_observations(provider,slug,checked_at,status,received,incomplete) VALUES (?,?,datetime('now'),?,?,?)",(provider,slug,status,received,incomplete))


def source_health():
    if not core.DB.is_file():return []
    try:
        with sqlite3.connect(core.DB.resolve().as_uri()+'?mode=ro',uri=True) as db:
            db.row_factory=sqlite3.Row
            if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='source_observations'").fetchone():return []
            rows=db.execute("""SELECT provider,slug,COUNT(*) attempts,
                SUM(status='failed') failures,SUM(status='partial') partial,SUM(received) received,SUM(incomplete) incomplete,MAX(checked_at) last_checked
                FROM source_observations WHERE checked_at >= datetime('now','-30 days') GROUP BY provider,slug ORDER BY failures DESC,partial DESC""").fetchall()
            return [dict(row) for row in rows]
    except (sqlite3.Error,OSError):return []


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
