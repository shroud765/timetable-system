"""M08: bounded leases; cancelled or superseded owners cannot commit."""
import time
import secrets
from sqlalchemy import select, or_, and_
from .db import Job, Version, transaction, lock_term, record
from .rules import snapshot, validate
from .solver import solve
from .timetable import save_lessons

def enqueue(actor, key):
    with transaction() as db:
        term=lock_term(db)
        old=db.scalar(select(Job).where(Job.key == key))
        if old: return old.id
        job=Job(key=key,revision=term.revision,snapshot=snapshot(db,term))
        db.add(job);db.flush()
        record(db,actor,'job.queued',{'id':job.id})
        return job.id

def cancel(actor, jid):
    with transaction() as db:
        job=db.scalar(select(Job).where(Job.id==jid).with_for_update())
        if not job: raise ValueError('Job not found')
        if job.state in ('queued','running'): job.state='cancelled'
        record(db,actor,'job.cancelled',{'id':jid})

def run_once():
    now=time.time()
    with transaction() as db:
        job=db.scalar(select(Job).where(or_(Job.state=='queued',
            and_(Job.state=='running',Job.lease<now)))
            .order_by(Job.id).with_for_update(skip_locked=True))
        if not job: return False
        if job.attempts>=3:
            job.state='failed';job.result={'error':'Retry budget exhausted'}
            return True
        owner=secrets.token_hex(16); job.owner=owner
        job.state='running';job.lease=now+120;job.attempts+=1
        jid=job.id;snap=job.snapshot
    try:
        result=solve(snap)
    except Exception:
        result={'status':'ERROR','error':'Solver failed; inspect worker log'}
        import logging
        logging.exception('solver job %s',jid)
    with transaction() as db:
        term=lock_term(db)
        job=db.scalar(select(Job).where(Job.id==jid).with_for_update())
        if job.state!='running' or job.owner!=owner or job.lease<time.time():
            return True
        if 'lessons' in result:
            validate(snap,result['lessons'])
            version=Version(name=f'Job {jid}',snapshot=snap,
                            input_revision=job.revision)
            db.add(version);db.flush()
            save_lessons(db,version,result.pop('lessons'))
            result['version']=version.id
            result['stale']=job.revision != term.revision
            job.state='succeeded'
        else: job.state='failed'
        job.result=result
        record(db,'worker','job.finished',{'id':jid,'result':result})
    return True

