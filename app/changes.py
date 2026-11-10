"""M10: dated cancellation or room/time move; teacher stays unchanged."""
from datetime import date
from sqlalchemy import select
from .db import (Version, ExceptionDay, Outbox, transaction, lock_term, record)
from .timetable import rows
from .rules import validate, snapshot

def effective(db, vid, day):
    weekday=date.fromisoformat(day).weekday()
    lessons=[l for l in rows(db,vid) if l['slot']//6==weekday]
    events={e.lesson:e for e in db.scalars(select(ExceptionDay).where(
        ExceptionDay.version==vid,ExceptionDay.date==day))}
    result=[]
    for lesson in lessons:
        event=events.get(lesson['id'])
        if event and event.cancelled: continue
        if event: lesson.update(slot=event.slot,room=event.room)
        result.append(lesson)
    return result

def change(actor, data):
    with transaction() as db:
        term=lock_term(db)
        if term.published != data['version']:
            raise ValueError('Published version changed; reload')
        version=db.get(Version,term.published)
        if version.revision != data['expected_revision']:
            raise ValueError('Published revision changed; reload')
        source=next((l for l in rows(db,version.id)
                     if l['id']==data['lesson']),None)
        weekday=date.fromisoformat(data['date']).weekday()
        if not source or source['slot']//6!=weekday:
            raise ValueError('Session does not occur on that weekday')
        if not data['cancelled'] and data['slot']//6 != weekday:
            raise ValueError('Move must remain on the selected date')
        event=db.scalar(select(ExceptionDay).where(
            ExceptionDay.version==version.id,ExceptionDay.lesson==source['id'],
            ExceptionDay.date==data['date']))
        if not event:
            event=ExceptionDay(version=version.id,lesson=source['id'],
                               date=data['date']);db.add(event)
        event.cancelled=data['cancelled'];event.slot=data['slot']
        event.room=data['room'];db.flush()
        # Term lock serializes all edits: check complete effective day's occupancy.
        validate(snapshot(db,term),effective(db,version.id,data['date']),False)
        version.revision+=1
        db.add(Outbox(message=f"Timetable exception on {data['date']}"))
        record(db,actor,'dated.change',{'date':data['date'],'lesson':source['id']})

