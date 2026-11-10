# Validation record - 24 October 2026

Executed in the authoring environment:

- 14 automated tests passed on an isolated SQLite database.
- All SQLAlchemy table definitions compiled to the MySQL dialect.
- React/Vite production build passed.
- Python source compilation passed.

Tests cover authentication, role restrictions, CSRF/origin rejection, login
lockout persistence, teacher availability ownership, solver feasibility and
independent validation, conflicting-edit rollback, database occupancy uniqueness,
stale edit/publication rejection, cache revision, publication/outbox delivery,
CSV output, idempotency, queued/running cancellation, expired leases, dated
cancellation and API action allowlisting.

Not executed here:

- A live MySQL 8.4 server, InnoDB concurrency tests, backup/restore or Docker startup.
- An actual browser visual/interaction test on the user's Mac.
- The existing Ubuntu gateway manager, live BPF attachment or QoS application.

SQLite functional tests do not prove MySQL row-lock behaviour. Run
`python -m ops.mysql_checks` against the configured MySQL server. Do not claim
measured eBPF/SQL performance improvements from these functional tests.

The API test stack emits an upstream httpx/TestClient deprecation warning; it
does not affect these passing tests. Dependencies are pinned in requirements.txt;
the full resolved development environment is recorded in requirements-lock.txt.

Acceptance on your machine: migrate/seed; create users; generate/publish; verify
student restrictions; attempt a conflicting edit; restart worker; inspect fresh
gateway status; perform a backup and restore to the separate test database.
