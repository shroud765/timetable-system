"""M11: bounded process cache keyed by immutable/read revision and date."""
from collections import OrderedDict
from copy import deepcopy
from threading import Lock
from time import time
from .db import Term, Version, transaction
from .timetable import rows
from .changes import effective

cache=OrderedDict();lock=Lock()

def published(day=None):
    with transaction() as db:
        term=db.get(Term,1)
        if not term.published: return {'version':None,'lessons':[]}
        version=db.get(Version,term.published)
        key=(version.id,version.revision,day)
        with lock:
            if key in cache:
                result=deepcopy(cache[key]);cache.move_to_end(key)
                return result
        result=dict(version=version.id,revision=version.revision,
            input_revision=version.input_revision,read_at=time(),
            date=day,lessons=effective(db,version.id,day) if day else rows(db,version.id),
            snapshot={k:version.snapshot[k] for k in ('resources','requirements')})
        with lock:
            cache[key]=deepcopy(result)
            while len(cache)>32: cache.popitem(last=False)
        return result

