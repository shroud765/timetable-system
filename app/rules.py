"""M04: one fixed-slot rule set shared by manual edits and solver."""
from collections import Counter
from .config import MAX_PERIODS, DAYS
from .db import Resource, Requirement, Block
from sqlalchemy import select

def snapshot(db, term):
    return dict(revision=term.revision, policy=term.policy,
        resources=[dict(id=r.id, kind=r.kind, name=r.name, size=r.size)
                   for r in db.scalars(select(Resource).order_by(Resource.id))],
        requirements=[dict(id=r.id, course=r.course, teacher=r.teacher,
            cohort=r.cohort, sessions=r.sessions, duration=r.duration)
            for r in db.scalars(select(Requirement).order_by(Requirement.id))],
        blocks=[[b.resource,b.slot] for b in db.scalars(select(Block))])

def candidates(snap, req):
    resources = {r['id']:r for r in snap['resources']}
    blocked = {tuple(x) for x in snap['blocks']}
    size = resources[req['cohort']]['size']
    for room in snap['resources']:
        if room['kind'] != 'room' or room['size'] < size:
            continue
        for start in range(DAYS * MAX_PERIODS):
            end = start + req['duration']
            if (end-1)//MAX_PERIODS != start//MAX_PERIODS:
                continue
            if any((rid,s) in blocked for rid in
                   (req['teacher'],req['cohort'],room['id'])
                   for s in range(start,end)):
                continue
            yield room['id'], start

def validate(snap, lessons, complete=True):
    reqs = {r['id']:r for r in snap['requirements']}
    used, counts, daily = set(), Counter(), Counter()
    for lesson in lessons:
        req = reqs.get(lesson['requirement'])
        if not req:
            raise ValueError('Unknown teaching requirement')
        if (lesson['room'],lesson['slot']) not in set(candidates(snap,req)):
            raise ValueError('Room capacity, availability or day boundary conflict')
        if any(lesson[k] != req[k] for k in ('teacher','cohort','duration')):
            raise ValueError('Session differs from its teaching requirement')
        counts[req['id']] += 1
        for rid in (req['teacher'],req['cohort'],lesson['room']):
            for slot in range(lesson['slot'],lesson['slot']+req['duration']):
                if (rid,slot) in used:
                    raise ValueError(f'Resource {rid} already occupies slot {slot}')
                used.add((rid,slot))
        daily[(req['teacher'],lesson['slot']//MAX_PERIODS)] += req['duration']
    if any(n > snap['policy']['max_daily'] for n in daily.values()):
        raise ValueError('Teacher daily period limit exceeded')
    for req in reqs.values():
        if counts[req['id']] > req['sessions'] or (
                complete and counts[req['id']] != req['sessions']):
            raise ValueError('Required teaching-session count mismatch')

