"""SQLite tests are functional tests; MySQL locking is checked separately."""
import os
import tempfile
from pathlib import Path
os.environ['TESTING']='1'
os.environ['DATABASE_URL']='sqlite:///'+str(Path(tempfile.mkdtemp())/'test.db')
os.environ['APP_ORIGIN']='http://testserver'
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.api import app
from app.db import (Base,engine,transaction,Term,Job,User,Version,Occupancy,
                    ExceptionDay,Notice,Session)
from app.manage import migrate,seed,create_user
from app.rules import snapshot,validate
from app.solver import solve
from app.jobs import enqueue,run_once,cancel
from app.timetable import rows,replace_draft
from app.publish import publish
from app.cache import cache,published
from app.exports import deliver,csv_export
from app.changes import change

@pytest.fixture(autouse=True)
def clean():
    Base.metadata.create_all(engine)
    with transaction() as db:
        term=db.get(Term,1)
        if term: term.published=None
    Base.metadata.drop_all(engine);migrate();seed();cache.clear()
    create_user('admin','admin','long-test-password')
    create_user('student','student','long-test-password')
    create_user('teacher','teacher','long-test-password',1)

def client(role='admin'):
    c=TestClient(app)
    r=c.post('/api/login',json={'username':role,'password':'long-test-password'})
    assert r.status_code==200
    c.headers['X-CSRF']=r.json()['csrf']
    return c

def generated():
    jid=enqueue('admin','unique-job-key');assert run_once()
    with transaction() as db:
        job=db.get(Job,jid);assert job.state=='succeeded',job.result
        return job.result['version']

def test_auth_roles_csrf_and_origin():
    c=TestClient(app);assert c.get('/api/published').status_code==401
    s=client('student')
    assert s.post('/api/jobs',json={'key':'abcdefgh'}).status_code==403
    a=client();a.headers.pop('X-CSRF')
    assert a.post('/api/versions').status_code==403
    a=client();a.headers['Origin']='https://other.invalid'
    assert a.post('/api/versions').status_code==403

def test_login_lockout_commits():
    c=TestClient(app)
    for _ in range(5):
        assert c.post('/api/login',json={'username':'admin','password':'wrong'}).status_code==401
    assert c.post('/api/login',json={'username':'admin','password':'long-test-password'}).status_code==401

def test_teacher_cannot_modify_other_resource():
    c=client('teacher')
    assert c.put('/api/availability',json={'resource':2,'slots':[0]}).status_code==403
    assert c.put('/api/availability',json={'resource':1,'slots':[0]}).status_code==200

def test_solver_validates_full_schedule():
    with transaction() as db: snap=snapshot(db,db.get(Term,1))
    result=solve(snap);assert result['status'] in ('FEASIBLE','OPTIMAL')
    validate(snap,result['lessons']);assert len(result['lessons'])==5

def test_conflicting_manual_edit_rolls_back():
    vid=generated()
    with transaction() as db: before=rows(db,vid)
    invalid=[{k:v for k,v in l.items() if k!='id'} for l in before]
    for l in invalid: l['slot']=0
    with pytest.raises(ValueError): replace_draft('admin',vid,1,invalid)
    with transaction() as db:
        assert rows(db,vid)==before
        assert db.get(Version,vid).revision==1

def test_database_occupancy_constraint():
    generated()
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        with transaction() as db:
            row=db.scalar(select(Occupancy).limit(1))
            db.add(Occupancy(version=row.version,lesson=row.lesson,
                             resource=row.resource,slot=row.slot))

def test_stale_edit_and_publication():
    vid=generated()
    with pytest.raises(ValueError): replace_draft('admin',vid,99,[])
    with transaction() as db: db.get(Term,1).revision+=1
    with pytest.raises(ValueError): publish('admin',vid,1,None)
    assert published()['version'] is None

def test_publish_notices_cache_export():
    vid=generated();publish('admin',vid,1,None)
    assert published()['version']==vid
    assert 'blocks' not in published()['snapshot']
    assert deliver()==1;assert deliver()==0
    with transaction() as db: assert len(list(db.scalars(select(Notice))))==3
    assert 'Database Systems' in csv_export()
    with pytest.raises(ValueError): publish('admin',vid,1,None)

def test_cancel_and_idempotency():
    first=enqueue('admin','same-idempotency')
    assert enqueue('admin','same-idempotency')==first
    cancel('admin',first);assert not run_once()

def test_expired_job_recovery():
    jid=enqueue('admin','lease-recovery')
    with transaction() as db:
        j=db.get(Job,jid);j.state='running';j.lease=0;j.owner='dead'
    assert run_once()
    with transaction() as db: assert db.get(Job,jid).state=='succeeded'

def test_cancelled_owner_cannot_commit(monkeypatch):
    from app import jobs
    original=jobs.solve
    jid=enqueue('admin','cancel-during-solve')
    def cancelled(snap):
        cancel('admin',jid);return original(snap)
    monkeypatch.setattr(jobs,'solve',cancelled)
    assert run_once()
    with transaction() as db:
        assert db.get(Job,jid).state=='cancelled'
        assert not list(db.scalars(select(Version)))

def test_date_cancellation_and_cache_revision():
    from datetime import date,timedelta
    vid=generated();publish('admin',vid,1,None)
    old=published()
    with transaction() as db: lesson=rows(db,vid)[0]
    when=(date(2026,10,26)+timedelta(days=lesson['slot']//6)).isoformat()
    before=published(when)
    change('admin',dict(version=vid,expected_revision=1,lesson=lesson['id'],
        date=when,cancelled=True,slot=lesson['slot'],room=lesson['room']))
    after=published(when)
    assert len(after['lessons'])==len(before['lessons'])-1
    assert after['revision']==2 and old['revision']==1

def test_route_validation_and_no_shell_arguments():
    c=client()
    assert c.post('/api/gateway',json={'action':'rm -rf /'}).status_code==422
    assert c.post('/api/gateway',json={'action':'start','command':'anything'}).status_code==422
    assert c.put('/api/availability',json={'resource':1,'slots':[30]}).status_code==422
    assert c.get('/api/gateway').json()['available'] is False

def test_mysql_schema_compiles():
    from sqlalchemy.schema import CreateTable
    from sqlalchemy.dialects.mysql import dialect
    for table in Base.metadata.sorted_tables:
        sql=str(CreateTable(table).compile(dialect=dialect()))
        assert 'CREATE TABLE' in sql

