"""M07: choose exactly one (room,start) per required teaching session."""
from collections import defaultdict
from ortools.sat.python import cp_model
from .rules import candidates, validate

def solve(snap):
    model=cp_model.CpModel(); variables=[]; busy=defaultdict(list)
    daily=defaultdict(list); objective=[]
    for req in snap['requirements']:
        opts=list(candidates(snap,req))
        if not opts:
            return {'status':'INFEASIBLE','reason':'No eligible slot/room'}
        for occurrence in range(req['sessions']):
            choices=[]
            for room,slot in opts:
                x=model.new_bool_var(f"r{req['id']}_{occurrence}_{room}_{slot}")
                choices.append(x)
                variables.append((x,req,room,slot))
                if len(variables)>50000:
                    raise ValueError('Prototype model-size limit exceeded')
                for rid in (room,req['teacher'],req['cohort']):
                    for occupied in range(slot,slot+req['duration']):
                        busy[rid,occupied].append(x)
                daily[req['teacher'],slot//6].append(x*req['duration'])
                objective.append(x*(slot%6)*snap['policy']['late_weight'])
            model.add_exactly_one(choices)
    for values in busy.values():
        model.add(sum(values)<=1)
    for values in daily.values():
        model.add(sum(values)<=snap['policy']['max_daily'])
    model.minimize(sum(objective))
    solver=cp_model.CpSolver()
    solver.parameters.max_time_in_seconds=10
    solver.parameters.num_search_workers=1
    solver.parameters.random_seed=42
    status=solver.solve(model)
    result={'status':solver.status_name(status),'seconds':solver.wall_time}
    if status in (cp_model.OPTIMAL,cp_model.FEASIBLE):
        lessons=[dict(requirement=r['id'],teacher=r['teacher'],
            cohort=r['cohort'],duration=r['duration'],room=room,slot=slot)
            for x,r,room,slot in variables if solver.value(x)]
        validate(snap,lessons)
        result.update(lessons=lessons,score=solver.objective_value)
    return result

