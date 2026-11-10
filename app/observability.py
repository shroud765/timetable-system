"""M15: bounded per-process latency sample and request IDs."""
import logging
import time
import uuid
from collections import deque
samples=deque(maxlen=500)

def install(app):
    @app.middleware('http')
    async def timed(request,call_next):
        start=time.monotonic();rid=uuid.uuid4().hex
        response=await call_next(request)
        elapsed=(time.monotonic()-start)*1000
        if request.url.path.startswith('/api/'):
            samples.append((elapsed,response.status_code))
            logging.info('request=%s method=%s path=%s status=%d ms=%.2f',
                rid,request.method,request.url.path,response.status_code,elapsed)
        response.headers['X-Request-ID']=rid
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Content-Security-Policy']=("default-src 'self'; "
            "script-src 'self'; style-src 'self'; connect-src 'self'; "
            "frame-ancestors 'none'; base-uri 'none'; object-src 'none'")
        return response

def metrics():
    values=sorted(x[0] for x in samples)
    return {'samples':len(values),'p95_ms':values[int(.95*(len(values)-1))]
        if values else None,'failures':sum(s>=500 for _,s in samples),
        'scope':'Last 500 API requests in this process; not SQL time'}

