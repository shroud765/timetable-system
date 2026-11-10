"""M06: draft operations and SQL-enforced resource occupancy."""
from sqlalchemy import select, delete
from .db import (Version, Lesson, Occupancy, transaction, lock_term, record)
from .rules import validate, snapshot

def rows(db, vid):
    return [dict(id=l.id, requirement=l.requirement, teacher=l.teacher,
        cohort=l.cohort, room=l.room, slot=l.slot, duration=l.duration)
        for l in db.scalars(select(Lesson).where(Lesson.version == vid)
                           .order_by(Lesson.slot,Lesson.id))]

def save_lessons(db, version, lessons):
    # Call only with term locked, after independent validation.
    db.execute(delete(Occupancy).where(Occupancy.version == version.id))
    db.execute(delete(Lesson).where(Lesson.version == version.id))
    for row in lessons:
        lesson = Lesson(version=version.id,
            **{k:v for k,v in row.items() if k != 'id'})
        db.add(lesson); db.flush()
        for rid in (lesson.teacher,lesson.cohort,lesson.room):
            for slot in range(lesson.slot,lesson.slot+lesson.duration):
                db.add(Occupancy(version=version.id,lesson=lesson.id,
                                 resource=rid,slot=slot))

def new_draft(actor):
    with transaction() as db:
        term=lock_term(db); snap=snapshot(db,term)
        version=Version(name='Manual draft',snapshot=snap,
                        input_revision=term.revision)
        db.add(version);db.flush()
        record(db,actor,'draft.created',{'version':version.id})
        return version.id

def replace_draft(actor, vid, expected, lessons):
    with transaction() as db:
        term=lock_term(db); version=db.get(Version,vid)
        if not version or version.state != 'draft':
            raise ValueError('Editable draft not found')
        if version.revision != expected:
            raise ValueError('Stale draft revision; reload')
        if version.input_revision != term.revision:
            raise ValueError('Planning inputs changed; generate a new draft')
        validate(version.snapshot,lessons,complete=False)
        save_lessons(db,version,lessons); version.revision+=1
        record(db,actor,'draft.edited',{'version':vid})
        return version.revision

