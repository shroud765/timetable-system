"""M02: hashed passwords, expiring sessions, CSRF and roles."""
import hashlib
import secrets
import time
from fastapi import HTTPException, Request
from sqlalchemy import select
from .config import ORIGIN
from .db import User, LoginSession, transaction

def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt),
        n=16384, r=8, p=1).hex()
    return salt + ':' + digest

def matches(password, stored):
    return secrets.compare_digest(password_hash(password,
        stored.split(':')[0]), stored)

def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()

def login(username, password):
    denied = False
    with transaction() as db:
        user = db.scalar(select(User).where(User.username == username)
                         .with_for_update())
        if not user or user.locked_until > time.time():
            denied = True
        elif not matches(password, user.password):
            user.failed += 1
            if user.failed >= 5:
                user.locked_until = time.time() + 60
                user.failed = 0
            denied = True
        else:
            user.failed = 0
            token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            db.add(LoginSession(token=token_hash(token), user_id=user.id,
                csrf=csrf, expires=time.time()+8*3600))
    if denied:
        raise HTTPException(401, 'Invalid credentials or temporarily locked')
    return token, csrf

def require(request: Request, roles=('admin','teacher','student')):
    token = request.cookies.get('session','')
    with transaction() as db:
        session = db.get(LoginSession, token_hash(token))
        if not session or session.expires < time.time():
            raise HTTPException(401, 'Sign in required')
        user = db.get(User, session.user_id)
        if user.role not in roles:
            raise HTTPException(403, 'This role cannot perform that action')
        if request.method not in ('GET','HEAD'):
            origin = request.headers.get('origin')
            if origin and origin != ORIGIN:
                raise HTTPException(403, 'Origin mismatch')
            if not secrets.compare_digest(request.headers.get('x-csrf',''),
                                          session.csrf):
                raise HTTPException(403, 'CSRF token missing or invalid')
        return dict(id=user.id, name=user.username, role=user.role,
                    teacher=user.teacher, csrf=session.csrf)

