# Timetable Lab - MySQL edition

A runnable teaching prototype for the 16-module timetable roadmap. It uses
React, FastAPI, SQLAlchemy/PyMySQL, MySQL 8.4 and OR-Tools CP-SAT. The eBPF
integration connects to Deepak's already installed Module-8 gateway manager.
It does not contain a replacement kernel classifier or fabricate gateway data.

## Implemented scope and boundaries

- One institution, one repeating teaching week, five days, six periods per day.
- Admin/teacher/student sessions, CSRF checks and server-side role enforcement.
- Teachers, cohorts and rooms; teaching requirements; blocked slots; daily limits.
- One teacher and one cohort per requirement; room capacity; one-to-three-slot
  sessions. No equipment, qualification or elective-group model in this release.
- Manual draft editing, independent conflict validation, SQL occupancy uniqueness.
- Background CP-SAT jobs with idempotency, lease recovery and commit-safe cancellation.
- Atomic publication and history; prior versions can be republished only while
  their input revision still matches. No automatic rollback across changed inputs.
- Dated cancellation/room/time moves on the same weekday. Automatic substitute
  teacher selection and incremental repair are not implemented.
- Versioned bounded read cache; explicitly saved local read-only offline copy.
  A full offline application shell/service worker and offline edits are not included.
- Transactional outbox to deduplicated in-app notices; CSV export and browser
  print-to-PDF. External email/SMS/WhatsApp and ICS export are not included.
- Live gateway state, historical latency/backlog charts and managed start/stop.
  Existing controller decides NORMAL/PROTECTED. This prototype does not issue
  competing manual profile changes.
- Basic API latency samples/audit; schema bootstrap, backup and separate restore test.
  Future schema changes need numbered migrations. This is not a production SaaS.

The earlier PDF recommended PostgreSQL. This package explicitly supersedes that
database choice: the application uses MySQL 8.4 with InnoDB and PyMySQL.
SQLite appears only in isolated automated tests, not the deployment path.

## Prerequisites

Use Ubuntu with Python 3.12, its venv package, Docker Engine with Compose v2,
and internet access to download Python packages and the MySQL container.
The prebuilt React frontend is included. To rebuild it use Node.js 22.12+ and npm.
Docker installation is environment-specific; follow https://docs.docker.com/engine/install/ubuntu/.
Check `docker compose version` before continuing. If Docker needs sudo, use it
consistently for Docker commands; do not run the application API as root.

Gateway controls additionally require the existing namespaces, shaping tree,
`/home/deepak/backend/manage.py`, controller, collector and BPF loaders installed
and working. A database server alone is enough to use the timetable application.

## 1. Transfer and extract (Mac, then Ubuntu)

Download timetable-system.zip to Downloads on your Mac. In Mac Terminal:

```bash
scp ~/Downloads/timetable-system.zip deepak@192.168.64.2:/home/deepak/
ssh deepak@192.168.64.2
```

Use your current VM address if different. In Ubuntu:

```bash
python3 -m zipfile -e ~/timetable-system.zip ~/
cd ~/timetable-system
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python ops/configure.py
docker compose up -d --wait mysql
set -a
source app.env
set +a
python -m app.manage migrate
python -m app.manage seed
python -m app.manage user admin admin
python -m app.manage user student student
python -m app.manage user teacher teacher --teacher 1
python -m ops.mysql_checks
```

Enter new passwords when prompted. No default passwords are included. The seed
creates Teacher A (#1), Teacher B (#2), cohort #3 and room #4. Run seed only once.
The configure command generates private passwords/token and refuses to overwrite
existing files. `.env`, `app.env` and `gateway.token` must not be shared or committed.
Do not delete the MySQL volume to fix an ordinary application error.

## 2. Start API and worker in separate Ubuntu terminals

Terminal A (keep open):

```bash
cd ~/timetable-system
source .venv/bin/activate
set -a
source app.env
set +a
uvicorn app.api:app --host 127.0.0.1 --port 8000
```

Terminal B (another SSH connection):

```bash
cd ~/timetable-system
source .venv/bin/activate
set -a
source app.env
set +a
python -m app.worker
```

The API serves the bundled frontend on the same origin. No CORS configuration is
required. A third Mac terminal exposes it locally:

```bash
ssh -N -L 8000:127.0.0.1:8000 deepak@192.168.64.2
```

Open http://127.0.0.1:8000 on the Mac. Keep the tunnel open. APP_ORIGIN in app.env
must match the browser address. For public deployment add HTTPS/reverse proxy,
set the correct HTTPS APP_ORIGIN, use secure cookies and tighten DB privileges.
The local Compose setup gives the timetable DB user migration privileges for
learning; split migration/runtime credentials before public deployment.

## 3. Demonstrate the timetable workflow

1. Sign in as admin. Inspect Academic data and seeded requirements.
2. Planning -> Generate timetable. The worker claims the job and solves it.
3. Open result; inspect the candidate. Save any manual changes first.
4. Publish saved version. A partial/incomplete schedule cannot be published.
5. Timetable -> Refresh. Student accounts can view the published schedule.
6. Notices appear after the worker delivers publication events.
7. Change availability. Old candidates now fail publication until regenerated.
8. Changes: choose a session, a date matching its weekday, and cancel/move it.
9. Timetable: select that date to view its exceptions. Blank date shows the
   recurring weekly plan. Weekly CSV excludes date-specific exceptions.
10. Save an offline copy only on a device you trust. Anyone using that browser
    can open the saved copy. Sign out clears it. It is not an encrypted vault.

## 4. Connect the existing Ubuntu eBPF gateway (optional)

First verify its known commands work outside this application. Stop any separately
launched unmanaged monitors in their original terminals; do not delete foreign hooks.
The existing manager performs its own ownership checks.

```bash
sudo python3 ~/backend/manage.py status
sudo python3 ~/timetable-system/gateway/agent.py \
  --home /home/deepak \
  --token-file /home/deepak/timetable-system/gateway.token
```

The adapter binds only to 127.0.0.1:8767. `ops/configure.py` wrote the matching token
to app.env. In the admin UI, open Gateway. Start/stop requests are asynchronous;
inspect last_action.exit_code and the snapshot, not only "accepted".
Keep the root adapter process running. Its use of the existing manager means
six services and their probes can start/stop; it is not a timetable server start.

The built-in ERP probe remains your existing demo probe. It does NOT measure the
new timetable API. New HTTPS/API endpoints need explicit classifier rules and
an authenticated or intentionally limited health probe before any timetable
performance claims. Loopback and SSH-tunnel traffic bypass your test namespace
gateway unless you deliberately configure the test routing. This is a management
integration, not evidence that eBPF has accelerated MySQL.

## 5. Tests and MySQL performance checks

```bash
cd ~/timetable-system
source .venv/bin/activate
python -m pytest -q
set -a
source app.env
set +a
python -m ops.mysql_checks
```

Tests create an isolated SQLite file and override their own process configuration.
They never drop your MySQL tables. The MySQL checks use two actual connections to
test a term-row lock; run during a quiet period, not alongside editors.
`ops/query_review.sql` contains an EXPLAIN ANALYZE read and index inspection.
Run it after publication, using a MySQL client on your test database. Capture SQL
execution separately from HTTP latency. Tiny seed data is not a performance benchmark.

Observed local verification is recorded in VALIDATION.md. MySQL-specific checks,
live eBPF actions and full browser interaction must still be run on your machine.

## 6. Backup, restore and shutdown

```bash
bash ops/backup.sh
```

This prints an actual backup filename. Pass that filename as the argument to
`bash ops/restore_test.sh`. The restore script creates a new `timetable_restore`
database and fails if that database already exists. It never replaces live data.
Do not run schema migrations during the backup; the snapshot assumes InnoDB tables.
Secure the backups and copy them to separate storage as part of real operations.

Ctrl+C stops API or worker in its own terminal. A worker stopped mid-solve leaves
a lease that can be reclaimed after 120 seconds (up to three attempts). Normal
solves have a 10-second search limit, plus model building. Cancellation prevents
result commit; it does not immediately kill the running solver computation.
Use `docker compose stop mysql` to stop the database while retaining its volume.
Stopping the gateway adapter does not stop the managed gateway stack; use the
existing manager or its UI action for that separately.

## 7. Change the frontend

```bash
cd ~/timetable-system/frontend
npm ci
npm run build
```

Restart the API if frontend/dist did not exist when it started. The package lock
is included; dependencies and generated dist bundles are not hand-written modules.

## Module-to-file index

| Module | Authored source |
|---|---|
| M01 Frontend | frontend/src/main.jsx, style.css, index.html |
| M02 Identity | app/auth.py; role-protected routes in app/api.py |
| M03 Academic data | app/master.py |
| M04 Rules | app/rules.py; policy/availability in master.py |
| M05 MySQL | app/db.py, config.py, ops/query_review.sql |
| M06 Draft editing | app/timetable.py |
| M07 Solver | app/solver.py |
| M08 Jobs | app/jobs.py, app/worker.py |
| M09 Publication | app/publish.py |
| M10 Dated changes | app/changes.py |
| M11 Cache | app/cache.py; explicit local copy in main.jsx |
| M12 Notices/export | app/exports.py |
| M13 Telemetry integration | app/gateway.py, gateway/agent.py |
| M14 QoS integration | same adapter; existing controller owns decisions |
| M15 Audit/metrics | app/observability.py; Audit + record in db.py |
| M16 Operations | app/manage.py, compose.yaml, ops scripts |

## API and database design notes

Open /docs while the API is running for field-level API documentation. All
protected routes still require a valid session; interactive mutations also need
the X-CSRF token from /api/me. app/api.py contains the full route wiring.
Database state consists of terms, resources, requirements, blocks, users,
login_sessions, versions, lessons, occupancy, jobs, exceptions, audit, outbox,
notices and schema_version. All application writes to planning/publication state
lock the singleton term row before validating. Resource IDs have one shared
registry, allowing actual foreign keys for teacher/room/cohort occupancy.

Each process uses a pool of four MySQL connections with no overflow. Budget the
sum across API/worker processes. MySQL uses REPEATABLE READ for consistent cached
reads. The controller does not execute SQL and cannot improve a bad query plan.
The cache is bounded to 32 views and keyed by version/revision/date. This release
loads a bounded institution timetable; for large institutions push filters and
pagination into SQL instead of returning the whole version.

No runtime SQL credentials, session cookies or generated tokens are included in
the downloadable package. Treat this as a locally validated prototype, then
complete the real MySQL, browser and Ubuntu integration checks before deployment.
