"""M13/M14: authenticated fixed gateway API; never return invented metrics."""
import json
import urllib.request
from .config import GATEWAY_URL,GATEWAY_TOKEN

def call(path, action=None):
    if not GATEWAY_URL or not GATEWAY_TOKEN:
        return {'available':False,'error':'Gateway adapter is not configured'}
    request=urllib.request.Request(GATEWAY_URL+path,
        data=json.dumps({'action':action}).encode() if action else None,
        headers={'Authorization':'Bearer '+GATEWAY_TOKEN,
                 'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(request,timeout=8) as response:
            return json.load(response)
    except Exception as error:
        return {'available':False,'error':str(error)}

