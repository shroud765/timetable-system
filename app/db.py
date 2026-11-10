"""M05: schema, connection budget and transaction boundaries."""
from contextlib import contextmanager
from sqlalchemy import (create_engine, Column, Integer, String, Double,
    Boolean, JSON, ForeignKey, UniqueConstraint, Index, event, select)
from sqlalchemy.orm import declarative_base, sessionmaker
from .config import DATABASE_URL, TESTING

engine = create_engine(DATABASE_URL, pool_pre_ping=True,
    **({'connect_args': {'check_same_thread': False}} if TESTING
       else {'pool_size': 4, 'max_overflow': 0, 'pool_timeout': 5,
             'isolation_level': 'REPEATABLE READ',
             'connect_args': {'connect_timeout': 5, 'read_timeout': 15,
              'write_timeout': 15,
              'init_command': 'SET SESSION innodb_lock_wait_timeout=5'}}))
if TESTING:
    @event.listens_for(engine, 'connect')
    def sqlite_setup(conn, _):
        conn.execute('PRAGMA foreign_keys=ON')
        conn.execute('PRAGMA busy_timeout=5000')
Session = sessionmaker(engine, expire_on_commit=False)
Base = declarative_base()

class Term(Base):
    __tablename__ = 'terms'
    id = Column(Integer, primary_key=True)
    revision = Column(Integer, nullable=False, default=1)
    published = Column(Integer, ForeignKey('versions.id', use_alter=True))
    policy = Column(JSON, nullable=False, default=dict)

class Resource(Base):
    __tablename__ = 'resources'
    id = Column(Integer, primary_key=True)
    kind = Column(String(12), nullable=False)
    name = Column(String(100), nullable=False)
    size = Column(Integer, nullable=False, default=1)
    __table_args__ = (UniqueConstraint('kind', 'name'),)

class Requirement(Base):
    __tablename__ = 'requirements'
    id = Column(Integer, primary_key=True)
    course = Column(String(100), nullable=False)
    teacher = Column(Integer, ForeignKey('resources.id'), nullable=False)
    cohort = Column(Integer, ForeignKey('resources.id'), nullable=False)
    sessions = Column(Integer, nullable=False)
    duration = Column(Integer, nullable=False, default=1)

class Block(Base):
    __tablename__ = 'blocks'
    id = Column(Integer, primary_key=True)
    resource = Column(Integer, ForeignKey('resources.id'), nullable=False)
    slot = Column(Integer, nullable=False)
    __table_args__ = (UniqueConstraint('resource', 'slot'),)

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String(100), nullable=False, unique=True)
    password = Column(String(256), nullable=False)
    role = Column(String(12), nullable=False)
    teacher = Column(Integer, ForeignKey('resources.id'))
    failed = Column(Integer, nullable=False, default=0)
    locked_until = Column(Double, nullable=False, default=0)

class LoginSession(Base):
    __tablename__ = 'login_sessions'
    token = Column(String(64), primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    csrf = Column(String(64), nullable=False)
    expires = Column(Double, nullable=False)

class Version(Base):
    __tablename__ = 'versions'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    input_revision = Column(Integer, nullable=False)
    revision = Column(Integer, nullable=False, default=1)
    state = Column(String(12), nullable=False, default='draft')
    snapshot = Column(JSON, nullable=False)

class Lesson(Base):
    __tablename__ = 'lessons'
    id = Column(Integer, primary_key=True)
    version = Column(Integer, ForeignKey('versions.id'), nullable=False)
    requirement = Column(Integer, ForeignKey('requirements.id'), nullable=False)
    teacher = Column(Integer, ForeignKey('resources.id'), nullable=False)
    cohort = Column(Integer, ForeignKey('resources.id'), nullable=False)
    room = Column(Integer, ForeignKey('resources.id'), nullable=False)
    slot = Column(Integer, nullable=False)
    duration = Column(Integer, nullable=False)
    __table_args__ = (Index('ix_lesson_cohort', 'version','cohort','slot'),
                     Index('ix_lesson_teacher', 'version','teacher','slot'))

class Occupancy(Base):
    __tablename__ = 'occupancy'
    id = Column(Integer, primary_key=True)
    version = Column(Integer, ForeignKey('versions.id'), nullable=False)
    lesson = Column(Integer, ForeignKey('lessons.id'), nullable=False)
    resource = Column(Integer, ForeignKey('resources.id'), nullable=False)
    slot = Column(Integer, nullable=False)
    __table_args__ = (UniqueConstraint('version','resource','slot'),)

class Job(Base):
    __tablename__ = 'jobs'
    id = Column(Integer, primary_key=True)
    key = Column(String(100), nullable=False, unique=True)
    revision = Column(Integer, nullable=False)
    snapshot = Column(JSON, nullable=False)
    state = Column(String(20), nullable=False, default='queued')
    owner = Column(String(64))
    lease = Column(Double, nullable=False, default=0)
    attempts = Column(Integer, nullable=False, default=0)
    result = Column(JSON)

class ExceptionDay(Base):
    __tablename__ = 'exceptions'
    id = Column(Integer, primary_key=True)
    version = Column(Integer, ForeignKey('versions.id'), nullable=False)
    lesson = Column(Integer, ForeignKey('lessons.id'), nullable=False)
    date = Column(String(10), nullable=False)
    cancelled = Column(Boolean, nullable=False)
    slot = Column(Integer)
    room = Column(Integer, ForeignKey('resources.id'))
    __table_args__ = (UniqueConstraint('version','lesson','date'),)

class Audit(Base):
    __tablename__ = 'audit'
    id = Column(Integer, primary_key=True)
    at = Column(Double, nullable=False)
    actor = Column(String(100), nullable=False)
    action = Column(String(60), nullable=False)
    details = Column(JSON, nullable=False)

class Outbox(Base):
    __tablename__ = 'outbox'
    id = Column(Integer, primary_key=True)
    message = Column(String(300), nullable=False)
    delivered = Column(Boolean, nullable=False, default=False)

class Notice(Base):
    __tablename__ = 'notices'
    id = Column(Integer, primary_key=True)
    event = Column(Integer, ForeignKey('outbox.id'), nullable=False)
    user = Column(Integer, ForeignKey('users.id'), nullable=False)
    message = Column(String(300), nullable=False)
    __table_args__ = (UniqueConstraint('event','user'),)

@contextmanager
def transaction():
    with Session() as db:
        with db.begin():
            # SQLite is a deterministic development test path only.
            if TESTING:
                db.connection().exec_driver_sql('BEGIN IMMEDIATE')
            yield db

def lock_term(db):
    return db.scalar(select(Term).where(Term.id == 1).with_for_update())

def record(db, actor, action, details):
    import time
    db.add(Audit(at=time.time(), actor=actor, action=action, details=details))

