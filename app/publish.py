"""M09: atomic publication pointer + audit + outbox."""
from .db import Version, Outbox, transaction, lock_term, record
from .rules import validate, snapshot
from .timetable import rows

def publish(actor, vid, expected, expected_published):
    with transaction() as db:
        term=lock_term(db); version=db.get(Version,vid)
        if not version: raise ValueError('Version not found')
        if term.published != expected_published:
            raise ValueError('Another publication occurred; reload')
        if version.revision != expected:
            raise ValueError('Draft changed; reload')
        if version.input_revision != term.revision:
            raise ValueError('Inputs changed; create a new candidate')
        validate(snapshot(db,term),rows(db,vid))
        if term.published==vid: return
        term.published=vid;version.state='published'
        db.add(Outbox(message=f'Timetable version {vid} published'))
        record(db,actor,'version.published',{'version':vid})

