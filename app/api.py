"""Integration router: M01-M16 connect through one same-origin API."""
from datetime import date
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, OperationalError
from . import auth, master, jobs, timetable, publish, changes, cache, exports
from . import gateway, observability
from .config import ORIGIN,SECURE_COOKIE
from .db import (transaction, Term, Version, User, Resource, Job,
                 LoginSession, Notice, Audit, engine)
from .rules import snapshot

class Input(BaseModel):
    model_config=ConfigDict(extra='forbid')

class Login(Input):
    username: str=Field(min_length=1,max_length=100)
    password: str=Field(min_length=1,max_length=256)

class ResourceInput(Input):
    kind: Literal['teacher','cohort','room']
    name: str=Field(min_length=1,max_length=100)
    size: int=Field(ge=1,le=10000)

class RequirementInput(Input):
    course: str=Field(min_length=1,max_length=100)
    teacher: int=Field(ge=1)
    cohort: int=Field(ge=1)
    sessions: int=Field(ge=1,le=10)
    duration: int=Field(ge=1,le=3)

class BlocksInput(Input):
    resource: int=Field(ge=1)
    slots: list[int]=Field(max_length=30)

class PolicyInput(Input):
    max_daily: int=Field(ge=1,le=6)
    late_weight: int=Field(ge=0,le=100)

class JobInput(Input):
    key: str=Field(min_length=8,max_length=100)

class LessonInput(Input):
    requirement: int=Field(ge=1)
    teacher: int=Field(ge=1)
    cohort: int=Field(ge=1)
    room: int=Field(ge=1)
    slot: int=Field(ge=0,le=29)
    duration: int=Field(ge=1,le=3)

class DraftInput(Input):
    expected_revision: int=Field(ge=1)
    lessons: list[LessonInput]=Field(max_length=1000)

class PublishInput(Input):
    expected_revision: int=Field(ge=1)
    expected_published: int | None

class ChangeInput(Input):
    version: int=Field(ge=1)
    expected_revision: int=Field(ge=1)
    lesson: int=Field(ge=1)
    date: date
    cancelled: bool=False
    slot: int=Field(ge=0,le=29)
    room: int=Field(ge=1)

class ActionInput(Input):
    action: Literal['start','stop']

app=FastAPI(title='Timetable Lab - MySQL edition',version='1.0')
observability.install(app)

@app.exception_handler(ValueError)
async def invalid(_, error):
    return JSONResponse({'detail':str(error)},status_code=409)

@app.exception_handler(PermissionError)
async def denied(_, error):
    return JSONResponse({'detail':str(error)},status_code=403)

@app.exception_handler(IntegrityError)
async def constraint(_, error):
    return JSONResponse({'detail':'Database constraint rejected the change'},409)

@app.exception_handler(OperationalError)
async def unavailable(_, error):
    return JSONResponse({'detail':'Database busy/unavailable; reload before retrying'},503)

@app.post('/api/login')
def sign_in(data:Login, request:Request, response:Response):
    if request.headers.get('origin') not in (None,ORIGIN):
        raise HTTPException(403,'Origin mismatch')
    token,csrf=auth.login(data.username,data.password)
    response.set_cookie('session',token,httponly=True,secure=SECURE_COOKIE,
                        samesite='strict',max_age=8*3600)
    return {'csrf':csrf}

@app.post('/api/logout')
def sign_out(request:Request,response:Response):
    auth.require(request)
    with transaction() as db:
        session=db.get(LoginSession,auth.token_hash(request.cookies['session']))
        db.delete(session)
    response.delete_cookie('session')
    return {'ok':True}

@app.get('/api/me')
def me(request:Request): return auth.require(request)

@app.get('/api/master')
def master_data(request:Request):
    auth.require(request,('admin','teacher'))
    with transaction() as db:
        term=db.get(Term,1)
        return {**snapshot(db,term),'published':term.published}

@app.post('/api/resources')
def resource(data:ResourceInput,request:Request):
    user=auth.require(request,('admin',))
    return {'id':master.add_resource(user['name'],data.model_dump())}

@app.post('/api/requirements')
def requirement(data:RequirementInput,request:Request):
    user=auth.require(request,('admin',))
    return {'id':master.add_requirement(user['name'],data.model_dump())}

@app.put('/api/availability')
def availability(data:BlocksInput,request:Request):
    user=auth.require(request,('admin','teacher'))
    if any(s<0 or s>29 for s in data.slots):
        raise HTTPException(422,'Slots must be in 0..29')
    master.set_blocks(user,data.resource,data.slots)
    return {'ok':True}

@app.put('/api/policy')
def policy(data:PolicyInput,request:Request):
    user=auth.require(request,('admin',))
    master.set_policy(user['name'],data.model_dump());return {'ok':True}

@app.get('/api/versions')
def versions(request:Request):
    auth.require(request,('admin',))
    with transaction() as db:
        return [dict(id=v.id,name=v.name,state=v.state,revision=v.revision,
                     input_revision=v.input_revision)
            for v in db.scalars(select(Version).order_by(Version.id.desc()).limit(100))]

@app.post('/api/versions')
def draft(request:Request):
    user=auth.require(request,('admin',))
    return {'id':timetable.new_draft(user['name'])}

@app.get('/api/versions/{vid}')
def version(vid:int,request:Request):
    auth.require(request,('admin',))
    with transaction() as db:
        v=db.get(Version,vid)
        if not v: raise HTTPException(404,'Version not found')
        return dict(version=v.id,revision=v.revision,state=v.state,
            snapshot=v.snapshot,lessons=timetable.rows(db,vid))

@app.put('/api/versions/{vid}')
def edit(vid:int,data:DraftInput,request:Request):
    user=auth.require(request,('admin',))
    return {'revision':timetable.replace_draft(user['name'],vid,
        data.expected_revision,[l.model_dump() for l in data.lessons])}

@app.post('/api/versions/{vid}/publish')
def publication(vid:int,data:PublishInput,request:Request):
    user=auth.require(request,('admin',))
    publish.publish(user['name'],vid,data.expected_revision,data.expected_published)
    return {'ok':True}

@app.get('/api/published')
def view(request:Request, day:date|None=None):
    auth.require(request)
    return cache.published(day.isoformat() if day else None)

@app.post('/api/jobs',status_code=202)
def generate(data:JobInput,request:Request):
    user=auth.require(request,('admin',))
    return {'id':jobs.enqueue(user['name'],data.key)}

@app.get('/api/jobs')
def job_list(request:Request):
    auth.require(request,('admin',))
    with transaction() as db:
        return [dict(id=j.id,state=j.state,lease=j.lease,result=j.result,
                     attempts=j.attempts) for j in db.scalars(
            select(Job).order_by(Job.id.desc()).limit(30))]

@app.post('/api/jobs/{jid}/cancel')
def cancellation(jid:int,request:Request):
    user=auth.require(request,('admin',));jobs.cancel(user['name'],jid)
    return {'ok':True}

@app.post('/api/exceptions')
def exception_day(data:ChangeInput,request:Request):
    user=auth.require(request,('admin',))
    changes.change(user['name'],data.model_dump(mode='json'))
    return {'ok':True}

@app.get('/api/notices')
def notices(request:Request):
    user=auth.require(request)
    with transaction() as db:
        return [dict(id=n.id,message=n.message) for n in db.scalars(
            select(Notice).where(Notice.user==user['id'])
            .order_by(Notice.id.desc()).limit(50))]

@app.get('/api/export.csv')
def export(request:Request):
    auth.require(request)
    return Response(exports.csv_export(),media_type='text/csv',
        headers={'Content-Disposition':'attachment; filename="timetable.csv"'})

@app.get('/api/gateway')
def gateway_status(request:Request):
    auth.require(request,('admin',));return gateway.call('/status')

@app.post('/api/gateway')
def gateway_control(data:ActionInput,request:Request):
    user=auth.require(request,('admin',))
    result=gateway.call('/action',data.action)
    with transaction() as db:
        from .db import record
        record(db,user['name'],'gateway.request',{'action':data.action,'result':result})
    return result

@app.get('/api/metrics')
def metrics(request:Request):
    auth.require(request,('admin',));return observability.metrics()

@app.get('/api/audit')
def audit(request:Request):
    auth.require(request,('admin',))
    with transaction() as db:
        return [dict(at=a.at,actor=a.actor,action=a.action,details=a.details)
            for a in db.scalars(select(Audit).order_by(Audit.id.desc()).limit(50))]

@app.get('/health')
def health():
    with engine.connect() as conn: conn.execute(text('SELECT 1'))
    return {'ok':True}

static=Path(__file__).resolve().parents[1]/'frontend'/'dist'
if static.exists(): app.mount('/',StaticFiles(directory=static,html=True),name='ui')

