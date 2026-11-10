"""M13/M14 adapter for Deepak's EXISTING Module-8 managed gateway.
Run on the Ubuntu host as root; web API stays unprivileged.
The existing manager/controller retain BPF and QoS ownership.
"""
import argparse
import json
import os
import secrets
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--home',type=Path,default=Path('/home/deepak'))
    p.add_argument('--port',type=int,default=8767)
    p.add_argument('--token-file',type=Path,required=True)
    args=p.parse_args()
    if os.geteuid()!=0: raise SystemExit('Gateway adapter requires root')
    manager=args.home/'backend/manage.py'
    if not manager.is_file(): raise SystemExit('Existing Module-8 manager missing')
    token=args.token_file.read_text().strip()
    if len(token)<32: raise SystemExit('Use a random token of at least 32 characters')
    lock=threading.Lock();state={'busy':False,'last_action':None}
    def execute(action):
        try:
            # No shell, no user-supplied arguments, no forced BPF deletion.
            r=subprocess.run(['/usr/bin/python3',str(manager),action],
                capture_output=True,text=True,timeout=210)
            state['last_action']={'action':action,'exit_code':r.returncode,
                'output':(r.stdout+r.stderr)[-6000:],'finished_at':time.time()}
        except Exception as error:
            state['last_action']={'action':action,'error':str(error)}
        finally: state['busy']=False;lock.release()
    class Handler(BaseHTTPRequestHandler):
        def send(self,status,data):
            body=json.dumps(data).encode();self.send_response(status)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store');self.end_headers()
            self.wfile.write(body)
        def authorised(self):
            if self.headers.get('Origin'):
                self.send(403,{'error':'Browser origins not accepted'});return False
            supplied=self.headers.get('Authorization','')
            if not secrets.compare_digest(supplied,'Bearer '+token):
                self.send(401,{'error':'Unauthorised'});return False
            return True
        def do_GET(self):
            if not self.authorised(): return
            if self.path!='/status': self.send(404,{});return
            if state['busy']:
                self.send(200,dict(state,available=True,snapshot=None));return
            try:
                r=subprocess.run(['/usr/bin/python3',str(manager),'status'],
                    capture_output=True,text=True,timeout=6)
                if r.returncode: raise RuntimeError(r.stderr[-500:])
                data=json.loads(r.stdout)
                self.send(200,dict(state,available=True,snapshot=data,
                                   read_at=time.time()))
            except Exception as error:
                self.send(200,dict(state,available=False,error=str(error)))
        def do_POST(self):
            if not self.authorised(): return
            if self.path!='/action': self.send(404,{});return
            try:
                length=int(self.headers.get('Content-Length','0'))
                if length<1 or length>128: raise ValueError()
                data=json.loads(self.rfile.read(length))
                if set(data)!={'action'} or data['action'] not in ('start','stop'):
                    raise ValueError()
            except Exception: self.send(400,{'error':'Invalid action'});return
            if not lock.acquire(False): self.send(409,{'error':'Busy'});return
            state['busy']=True
            threading.Thread(target=execute,args=(data['action'],),daemon=True).start()
            self.send(202,{'accepted':True,'action':data['action']})
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    print('Gateway adapter: loopback only; existing controller owns adaptation')
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()

if __name__=='__main__': main()

