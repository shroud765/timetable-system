"""M12: transactional in-app notices and formula-safe CSV export."""
import csv
import io
from sqlalchemy import select
from .db import Outbox, Notice, User, transaction
from .cache import published

def deliver():
    with transaction() as db:
        events=list(db.scalars(select(Outbox).where(Outbox.delivered==False)
            .with_for_update(skip_locked=True).limit(20)))
        for event in events:
            for uid in db.scalars(select(User.id)):
                db.add(Notice(event=event.id,user=uid,message=event.message))
            event.delivered=True
        return len(events)

def csv_export():
    data=published();out=io.StringIO();writer=csv.writer(out)
    writer.writerow(['version','course','teacher','cohort','room','day','period','duration'])
    if not data['version']: return out.getvalue()
    resources={r['id']:r['name'] for r in data['snapshot']['resources']}
    courses={r['id']:r['course'] for r in data['snapshot']['requirements']}
    def safe(value):
        value=str(value)
        return "'"+value if value.startswith(('=','+','-','@','\t','\r')) else value
    for l in data['lessons']:
        writer.writerow([safe(x) for x in [data['version'],courses[l['requirement']],
            resources[l['teacher']],resources[l['cohort']],resources[l['room']],
            l['slot']//6+1,l['slot']%6+1,l['duration']]])
    return out.getvalue()

