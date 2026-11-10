"""M16: initial migration, demo data and explicit user creation."""
import argparse
import getpass
from sqlalchemy import select,text
from .db import (Base,engine,transaction,Term,Resource,Requirement,User)
from .auth import password_hash

def migrate():
    # Initial schema only. Future upgrades need a numbered reviewed migration.
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE IF NOT EXISTS schema_version '
                          '(version INTEGER PRIMARY KEY)'))
        version=conn.execute(text('SELECT version FROM schema_version')).scalar()
    if version not in (None,1): raise RuntimeError('Unsupported schema version')
    Base.metadata.create_all(engine)
    if version is None:
        with engine.begin() as conn:
            conn.execute(text('INSERT INTO schema_version VALUES (1)'))
    with transaction() as db:
        if not db.get(Term,1):
            db.add(Term(id=1,revision=1,policy={'max_daily':5,'late_weight':1}))

def seed():
    with transaction() as db:
        from .db import lock_term
        term=lock_term(db)
        if db.scalar(select(Resource.id).limit(1)):
            raise RuntimeError('Seed only into an empty resource catalogue')
        a=Resource(kind='teacher',name='Teacher A',size=1)
        b=Resource(kind='teacher',name='Teacher B',size=1)
        cohort=Resource(kind='cohort',name='CSE Semester 3',size=40)
        room=Resource(kind='room',name='Room 101',size=50)
        db.add_all([a,b,cohort,room]);db.flush()
        db.add_all([Requirement(course='Database Systems',teacher=a.id,
            cohort=cohort.id,sessions=3,duration=1),
            Requirement(course='Operating Systems Lab',teacher=b.id,
            cohort=cohort.id,sessions=2,duration=2)])
        term.revision+=1

def create_user(username,role,password,teacher=None):
    if len(password)<12: raise ValueError('Use at least 12 password characters')
    with transaction() as db:
        if db.scalar(select(User).where(User.username==username)):
            raise ValueError('User already exists')
        if role=='teacher':
            r=db.get(Resource,teacher)
            if not r or r.kind!='teacher': raise ValueError('Valid teacher ID required')
        db.add(User(username=username,role=role,password=password_hash(password),
                    teacher=teacher if role=='teacher' else None))

def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('migrate');sub.add_parser('seed')
    u=sub.add_parser('user');u.add_argument('username')
    u.add_argument('role',choices=['admin','teacher','student'])
    u.add_argument('--teacher',type=int)
    args=p.parse_args()
    if args.command=='migrate': migrate()
    elif args.command=='seed': seed()
    else:
        pw=getpass.getpass('New password (12+ characters): ')
        if pw!=getpass.getpass('Repeat password: '): raise ValueError('Passwords differ')
        create_user(args.username,args.role,pw,args.teacher)
    print('Done')

if __name__=='__main__': main()

