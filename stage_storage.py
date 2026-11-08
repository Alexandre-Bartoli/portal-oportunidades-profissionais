"""Armazenamento privado para homologação: diretório durável, backup e restauração.

Nenhum backup é enviado ao GitHub. Para sobreviver a reinícios, configure
PORTAL_STAGING_DIR em um volume persistente mantido pelo operador.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile

import core

BACKUP_NAME = re.compile(r'^homologacao-[0-9]{8}T[0-9]{12}Z\.sqlite3$')


def storage_dir():
    value = os.getenv('PORTAL_STAGING_DIR', '').strip()
    if value:
        directory = Path(value).expanduser()
        if not directory.is_absolute():
            raise ValueError('PORTAL_STAGING_DIR deve ser um caminho absoluto')
    else:
        directory = core.BASE / 'data'
    directory = directory.resolve()
    if directory == core.BASE.resolve() or directory == core.BASE.resolve().parent:
        raise ValueError('Diretório de homologação não pode ser a raiz do código')
    if value and directory.is_relative_to(core.BASE.resolve()) and directory != (core.BASE / 'data').resolve():
        raise ValueError('Diretório configurado dentro do código pode expor bancos')
    return directory


def stage_paths():
    directory = storage_dir()
    return directory / 'homologacao.sqlite3', directory / 'homologacao_status.json'


def ensure_private(directory):
    directory = Path(directory)
    if directory.is_symlink():
        raise ValueError('Diretório de homologação não pode ser um link simbólico')
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not directory.is_dir():
        raise ValueError('Diretório de homologação inválido')
    # Diretório dedicado, inclusive no modo padrão, acessível só ao usuário.
    directory.chmod(0o700)
    return directory


@contextmanager
def staging_lock(directory, *, exclusive=False):
    """Restauração exige lock exclusivo; coleta, servidor e backup usam compartilhado.

    No Windows, os locks são exclusivos para todas as operações por limitação
    da interface msvcrt; a documentação recomenda executar uma operação por vez.
    """
    directory = ensure_private(directory)
    lockfile = directory / '.staging.lock'
    if lockfile.is_symlink():
        raise ValueError('Arquivo de lock inseguro')
    with open(lockfile, 'a+b') as fh:
        os.chmod(lockfile, 0o600)
        try:
            import fcntl
        except ImportError:
            import msvcrt
            fh.seek(0)
            fh.write(b'0')
            fh.flush()
            fh.seek(0)
            try:
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as e:
                raise RuntimeError('Homologação em uso; encerre as outras operações') from e
            try:
                yield
            finally:
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            try:
                fcntl.flock(fh.fileno(), (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB)
            except BlockingIOError as e:
                raise RuntimeError('Homologação em uso; restauração exige servidor e coleta parados') from e
            try:
                yield
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def _validate_staging_db(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Arquivo SQLite ausente ou inseguro')
    if path.resolve() == (core.BASE / 'data' / 'jobs.sqlite3').resolve():
        raise ValueError('Não é permitido usar o banco principal')
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
        result = db.execute('PRAGMA integrity_check').fetchone()
        if not result or result[0] != 'ok':
            raise ValueError('Falha na integridade do SQLite')
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'jobs', 'job_aliases'}.issubset(tables):
            raise ValueError('O banco não corresponde ao esquema de homologação')
        if db.execute('SELECT COUNT(*) FROM jobs WHERE demo=1').fetchone()[0]:
            raise ValueError('Banco de homologação contém anúncios fictícios')
        return db.execute('SELECT COUNT(*) FROM jobs WHERE active=1 AND demo=0').fetchone()[0]


def _safe_backup_names(directory):
    if not directory.exists():
        return []
    return sorted((p for p in directory.iterdir() if BACKUP_NAME.fullmatch(p.name) and p.is_file() and not p.is_symlink()), key=lambda p: p.name)


def backup_staging(db_path=None, backup_dir=None, *, retain=10, now=None, protect_name=None):
    """Snapshot consistente via SQLite Backup API e rotação local.

    O chamador externo deve adquirir staging_lock(shared), que impede restore.
    """
    if type(retain) is not int or not 1 <= retain <= 100:
        raise ValueError('retain deve estar entre 1 e 100')
    db_path = Path(db_path or stage_paths()[0])
    backup_dir = Path(backup_dir or (db_path.parent / 'backups'))
    if db_path.resolve() == backup_dir.resolve():
        raise ValueError('Destino de backup inválido')
    ensure_private(backup_dir)
    active = _validate_staging_db(db_path)
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('Data do backup deve ter fuso horário')
    name = 'homologacao-' + now.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.sqlite3'
    destination = backup_dir / name
    if destination.exists():
        raise FileExistsError('Backup com mesmo identificador já existe')
    fd, temporary = tempfile.mkstemp(prefix='.backup-', suffix='.sqlite3', dir=backup_dir)
    os.close(fd)
    try:
        with sqlite3.connect(db_path.as_uri() + '?mode=ro', uri=True) as source:
            with sqlite3.connect(temporary) as target:
                source.backup(target)
        _validate_staging_db(temporary)
        os.chmod(temporary, 0o600)
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    old = _safe_backup_names(backup_dir)
    # Ao restaurar um backup antigo, a cópia de segurança prévia não pode
    # rotacionar justamente o arquivo que está prestes a ser restaurado.
    for path in old:
        if len(old) <= retain:
            break
        if path.name not in {protect_name, destination.name}:
            path.unlink()
            old.remove(path)
    return {'created':destination.name, 'retained':len(_safe_backup_names(backup_dir)), 'active_jobs_at_backup':active,
            'verified':True, 'local_only':True}


def restore_staging(name, *, confirm=False, db_path=None, backup_dir=None):
    """Restauração manual offline e não destrutiva, com snapshot anterior.

    Adquirir staging_lock(exclusive) fora desta função. Nome precisa existir
    dentro da pasta de backup configurada; nunca aceita caminho externo.
    """
    if not confirm:
        raise ValueError('Restauração exige --confirm e servidor encerrado')
    if not isinstance(name, str) or not BACKUP_NAME.fullmatch(name):
        raise ValueError('Informe somente o nome válido do backup, sem caminhos')
    db_path = Path(db_path or stage_paths()[0])
    backup_dir = Path(backup_dir or db_path.parent / 'backups')
    if db_path.resolve() == (core.BASE / 'data' / 'jobs.sqlite3').resolve():
        raise ValueError('O banco principal não pode ser restaurado por este comando')
    original = backup_dir / name
    if original.is_symlink() or not original.is_file():
        raise ValueError('Backup não encontrado na pasta autorizada')
    target_jobs = _validate_staging_db(original)
    if db_path.is_symlink():
        raise ValueError('Banco de destino não pode ser link simbólico')
    if any(Path(str(db_path) + ext).exists() for ext in ('-wal', '-shm', '-journal')):
        raise ValueError('Arquivos SQLite auxiliares presentes; pare os processos e faça checkpoint')
    ensure_private(db_path.parent)
    before = backup_staging(db_path, backup_dir=backup_dir, protect_name=name) if db_path.exists() else None
    fd, temporary = tempfile.mkstemp(prefix='.restore-', suffix='.sqlite3', dir=db_path.parent)
    os.close(fd)
    try:
        with sqlite3.connect(original.as_uri() + '?mode=ro', uri=True) as source:
            with sqlite3.connect(temporary) as target:
                source.backup(target)
        _validate_staging_db(temporary)
        os.chmod(temporary, 0o600)
        os.replace(temporary, db_path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return {'restored': name, 'active_jobs_after_restore':target_jobs,
            'safety_backup_before_restore':before['created'] if before else None, 'local_only':True}


def backup_list(directory=None):
    directory = Path(directory or stage_paths()[0].parent / 'backups')
    return [{'name':p.name, 'bytes':p.stat().st_size} for p in _safe_backup_names(directory)]


def write_private_report(report, path):
    path = Path(path)
    ensure_private(path.parent)
    temporary = path.with_name('.' + path.name + '.tmp')
    if temporary.is_symlink():
        raise ValueError('Destino de relatório inseguro')
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.chmod(0o600)
    temporary.replace(path)
    return path