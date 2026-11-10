"""M03/M04: validated academic inputs; serialize with publication."""
from sqlalchemy import select, delete
from .db import (Resource, Requirement, Block, lock_term, transaction, record)

def add_resource(actor, data):
    with transaction() as db:
        term = lock_term(db)
        if db.scalar(select(Resource).where(Resource.kind == data['kind'],
                                             Resource.name == data['name'])):
            raise ValueError('Resource already exists')
        item = Resource(**data); db.add(item); db.flush()
        term.revision += 1
        record(db,actor,'resource.created',{'id':item.id})
        return item.id

def add_requirement(actor, data):
    with transaction() as db:
        term = lock_term(db)
        for key in ('teacher','cohort'):
            resource = db.get(Resource,data[key])
            if not resource or resource.kind != key:
                raise ValueError('Wrong resource type for '+key)
        if len(list(db.scalars(select(Requirement)))) >= 100:
            raise ValueError('Prototype limit: 100 requirements')
        item=Requirement(**data); db.add(item); db.flush()
        term.revision += 1
        record(db,actor,'requirement.created',{'id':item.id})
        return item.id

def set_blocks(user, rid, slots):
    if user['role'] == 'teacher' and user['teacher'] != rid:
        raise PermissionError('Teachers may change only their own availability')
    with transaction() as db:
        term = lock_term(db)
        if not db.get(Resource,rid):
            raise ValueError('Unknown resource')
        db.execute(delete(Block).where(Block.resource == rid))
        db.add_all([Block(resource=rid,slot=s) for s in sorted(set(slots))])
        term.revision += 1
        record(db,user['name'],'availability.changed',{'resource':rid})

def set_policy(actor, data):
    with transaction() as db:
        term = lock_term(db); term.policy = data; term.revision += 1
        record(db,actor,'policy.changed',data)

