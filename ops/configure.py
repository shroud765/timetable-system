"""Create private local configuration once; never overwrite existing secrets."""
import os
import secrets
from pathlib import Path
root=Path(__file__).resolve().parents[1]
if any((root/name).exists() for name in ('.env','app.env','gateway.token')):
    raise SystemExit('Configuration already exists; no changes made')
dbpw=secrets.token_hex(24);rootpw=secrets.token_hex(24)
token=secrets.token_urlsafe(32)
files={'.env':f'MYSQL_PASSWORD={dbpw}\nMYSQL_ROOT_PASSWORD={rootpw}\n',
       'app.env':f'DATABASE_URL=mysql+pymysql://timetable:{dbpw}@127.0.0.1:3307/timetable?charset=utf8mb4\n'
                 'APP_ORIGIN=http://127.0.0.1:8000\n'
                 'GATEWAY_URL=http://127.0.0.1:8767\n'
                 f'GATEWAY_TOKEN={token}\n',
       'gateway.token':token+'\n'}
for name,data in files.items():
    fd=os.open(root/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:f.write(data)
print('Created .env, app.env and gateway.token (private permissions)')
