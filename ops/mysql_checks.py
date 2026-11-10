"""Run against the configured MySQL database after setup (no deletion).
Confirms InnoDB and unique indexes; demonstrates a real term-row lock timeout.
Requires the normal app configuration; do not run alongside active editors.
"""
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from app.db import engine

assert engine.dialect.name=='mysql','This check requires real MySQL'
with engine.connect() as c:
    print('MySQL',c.execute(text('SELECT VERSION()')).scalar())
    tables=c.execute(text("SELECT ENGINE FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='occupancy'")).all()
    assert tables and all(r[0]=='InnoDB' for r in tables)
    print('InnoDB verified')
with engine.connect() as a,engine.connect() as b:
    ta=a.begin();tb=b.begin()
    try:
        a.execute(text('SELECT id FROM terms WHERE id=1 FOR UPDATE')).one()
        b.execute(text('SET SESSION innodb_lock_wait_timeout=1'))
        try:
            b.execute(text('SELECT id FROM terms WHERE id=1 FOR UPDATE')).one()
            raise AssertionError('Second connection unexpectedly acquired lock')
        except OperationalError as exc:
            assert exc.orig.args[0]==1205,exc
            print('Row-lock exclusion verified')
    finally: tb.rollback();ta.rollback()

