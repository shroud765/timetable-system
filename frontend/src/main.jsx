/* M01/M11: role-aware UI; browser talks only to the authenticated API. */
/* M01/M11: role-aware UI; browser talks only to the authenticated API. */
import React, { useState, useEffect, useRef } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";
const TAIL = 6;
const INTERACTIVE =
  "a, button, input, select, textarea, label, summary, [role='button']";

export default function MouseTracer() {
  const dot = useRef(null);
  const ring = useRef(null);
  const tail = useRef([]);

  useEffect(() => {
    const fine = window.matchMedia(
      "(hover: hover) and (pointer: fine)",
    ).matches;
    const calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!fine || calm) return;

    const mouse = { x: -100, y: -100 };
    const ringPos = { x: -100, y: -100 };
    const trail = Array.from({ length: TAIL }, () => ({ x: -100, y: -100 }));
    let raf = 0;

    const move = (e) => {
      mouse.x = e.clientX;
      mouse.y = e.clientY;
      document.documentElement.classList.add("tracer-on");
      const hot = e.target instanceof Element && e.target.closest(INTERACTIVE);
      ring.current?.classList.toggle("is-hot", !!hot);
    };
    const down = () => ring.current?.classList.add("is-down");
    const up = () => ring.current?.classList.remove("is-down");
    const leave = () => document.documentElement.classList.remove("tracer-on");

    const frame = () => {
      ringPos.x += (mouse.x - ringPos.x) * 0.16;
      ringPos.y += (mouse.y - ringPos.y) * 0.16;
      if (dot.current)
        dot.current.style.transform = `translate3d(${mouse.x}px,${mouse.y}px,0)`;
      if (ring.current)
        ring.current.style.transform = `translate3d(${ringPos.x}px,${ringPos.y}px,0)`;
      let prev = ringPos;
      trail.forEach((p, i) => {
        p.x += (prev.x - p.x) * 0.35;
        p.y += (prev.y - p.y) * 0.35;
        const el = tail.current[i];
        if (el) el.style.transform = `translate3d(${p.x}px,${p.y}px,0)`;
        prev = p;
      });
      raf = requestAnimationFrame(frame);
    };

    window.addEventListener("mousemove", move, { passive: true });
    window.addEventListener("mousedown", down);
    window.addEventListener("mouseup", up);
    document.addEventListener("mouseleave", leave);
    raf = requestAnimationFrame(frame);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mousedown", down);
      window.removeEventListener("mouseup", up);
      document.removeEventListener("mouseleave", leave);
    };
  }, []);

  return (
    <div className="tracer" aria-hidden="true">
      {Array.from({ length: TAIL }, (_, i) => (
        <span
          key={i}
          className="tracer-tail"
          ref={(el) => (tail.current[i] = el)}
          style={{ opacity: 0.22 - i * 0.03, width: 8 - i, height: 8 - i }}
        />
      ))}
      <span className="tracer-ring" ref={ring} />
      <span className="tracer-dot" ref={dot} />
    </div>
  );
}
let csrf = "";
async function api(path, method = "GET", data) {
  const response = await fetch("/api" + path, {
    method,
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", "X-CSRF": csrf },
    body: data === undefined ? undefined : JSON.stringify(data),
  });
  const result = await response.json();
  if (!response.ok)
    throw Error(
      typeof result.detail === "string"
        ? result.detail
        : JSON.stringify(result.detail || result),
    );
  return result;
}
const days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"];
const offlineKey = "timetable-explicit-offline-copy";
function Form({ title, fields, submit, button = "Save" }) {
  return (
    <form
      onSubmit={async (e) => {
        e.preventDefault();
        const form = e.currentTarget;
        const values = Object.fromEntries(new FormData(form));
        fields.forEach((f) => {
          if (f.type === "number") values[f.name] = Number(values[f.name]);
        });
        await submit(values);
      }}
    >
      <h3>{title}</h3>
      {fields.map((f) => (
        <label key={f.name}>
          {f.label || f.name}
          {f.options ? (
            <select name={f.name} required>
              {f.options.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          ) : (
            <input
              name={f.name}
              type={f.type || "text"}
              required
              defaultValue={f.value}
              min={f.min}
              max={f.max}
              maxLength={f.type === "password" ? 256 : 100}
              autoComplete={f.autoComplete}
            />
          )}
        </label>
      ))}
      <button>{button}</button>
    </form>
  );
}
function Chart({ points, field, label }) {
  const valid = points
    .map((p) => p[field])
    .filter((v) => typeof v === "number");
  const max = Math.max(1, ...valid);
  let path = "";
  let connected = false;
  points.forEach((p, i) => {
    const v = p[field];
    if (typeof v !== "number") {
      connected = false;
      return;
    }
    const x = 5 + (i * 290) / Math.max(1, points.length - 1),
      y = 85 - (75 * v) / max;
    path += (connected ? " L" : " M") + x + "," + y;
    connected = true;
  });
  return (
    <div>
      <h3>{label}</h3>
      {valid.length ? (
        <>
          <svg viewBox="0 0 300 95" role="img" aria-label={label}>
            <path d={path} fill="none" stroke="#16746a" strokeWidth="2" />
          </svg>
          <small>Observed range 0–{max.toFixed(1)}; last 60 samples</small>
        </>
      ) : (
        <p>No fresh measurement available.</p>
      )}
    </div>
  );
}
function App() {
  const [user, U] = useState(null),
    [error, E] = useState(""),
    [message, M] = useState("");
  const [master, S] = useState(null),
    [view, V] = useState(null),
    [versions, VS] = useState([]);
  const [jobs, J] = useState([]),
    [draft, D] = useState(null),
    [notices, N] = useState([]);
  const [tab, T] = useState("Timetable"),
    [filter, F] = useState(""),
    [day, DAY] = useState("");
  const [offline, O] = useState(false),
    [gateway, G] = useState(null),
    [points, P] = useState([]);
  const [audit, A] = useState([]),
    [metric, MT] = useState(null),
    [busy, B] = useState(false);
  async function perform(fn) {
    B(true);
    E("");
    M("");
    try {
      await fn();
      M("Completed");
    } catch (e) {
      E(e.message);
    } finally {
      B(false);
    }
  }
  async function refresh() {
    const next = await api("/published" + (day ? "?day=" + day : ""));
    V(next);
    O(false);
    N(await api("/notices"));
    if (user?.role !== "student") S(await api("/master"));
    if (user?.role === "admin") {
      VS(await api("/versions"));
      J(await api("/jobs"));
    }
  }
  useEffect(() => {
    api("/me")
      .then((u) => {
        csrf = u.csrf;
        U(u);
      })
      .catch(() => {});
  }, []);
  useEffect(() => {
    if (user) perform(refresh);
  }, [user, day]);
  useEffect(() => {
    if (!user || user.role !== "admin") return;
    const timer = setInterval(() => {
      api("/jobs")
        .then(J)
        .catch(() => {});
    }, 3000);
    return () => clearInterval(timer);
  }, [user]);
  useEffect(() => {
    if (tab !== "Gateway" || user?.role !== "admin") return;
    let active = true;
    const update = () =>
      api("/gateway")
        .then((g) => {
          if (!active) return;
          G(g);
          const s = g.snapshot,
            latest = s?.controller?.latest;
          if (!s?.controller_log_fresh) return;
          P((old) =>
            old.at(-1)?.timestamp === latest?.timestamp
              ? old
              : [
                  ...old,
                  {
                    timestamp: latest?.timestamp,
                    latency: latest?.erp_latency_ms,
                    backlog: latest?.backlog_bytes,
                  },
                ].slice(-60),
          );
        })
        .catch((e) => E(e.message));
    update();
    const timer = setInterval(update, 6000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [tab, user]);
  const options = (kind) =>
    (master?.resources || [])
      .filter((r) => r.kind === kind)
      .map((r) => ({ value: r.id, label: r.name + " (#" + r.id + ")" }));
  function offlineView() {
    try {
      const saved = JSON.parse(localStorage.getItem(offlineKey));
      if (!saved) throw Error("No explicitly saved offline copy");
      V(saved.data);
      O(true);
      M("Offline copy saved " + new Date(saved.at).toLocaleString());
    } catch (e) {
      E(e.message);
    }
  }
  async function signout() {
    await api("/logout", "POST");
    localStorage.removeItem(offlineKey);
    U(null);
    V(null);
    S(null);
    D(null);
    csrf = "";
  }
  if (!user)
    return (
      <main>
        <h1>Timetable Lab</h1>
        <p>MySQL + FastAPI + React</p>
        <Form
          title="Sign in"
          fields={[
            { name: "username" },
            { name: "password", type: "password" },
          ]}
          button="Sign in"
          submit={(v) =>
            perform(async () => {
              const r = await api("/login", "POST", v);
              csrf = r.csrf;
              const u = await api("/me");
              U(u);
            })
          }
        />
        <p role="alert">{error}</p>
        <button onClick={offlineView}>Open saved offline copy</button>
        {offline && (
          <>
            <p className="warning">
              Local read-only copy. No server freshness check. This device's
              users can see this explicitly saved copy.
            </p>
            <Schedule data={view} />
          </>
        )}
      </main>
    );
  const tabs = [
    "Timetable",
    ...(user.role === "student" ? [] : ["Academic data", "Availability"]),
    ...(user.role === "admin"
      ? ["Planning", "Changes", "Gateway", "Diagnostics"]
      : []),
    "Notices",
  ];
  return (
    <>
      <header>
        <div>
          <strong>Timetable Lab</strong>
          <small>
            MySQL edition • {user.name} / {user.role}
          </small>
        </div>
        <button onClick={() => perform(signout)}>
          Sign out & clear offline copy
        </button>
      </header>
      <nav>
        {tabs.map((t) => (
          <button key={t} aria-pressed={tab === t} onClick={() => T(t)}>
            {t}
          </button>
        ))}
      </nav>
      <main>
        <h1>{tab}</h1>
        {busy && <p>Working…</p>}
        <p role="alert" className="error">
          {error}
        </p>
        <p role="status">{message}</p>
        {tab === "Timetable" && (
          <>
            <div className="toolbar">
              <button onClick={() => perform(refresh)}>Refresh</button>
              <label>
                Specific date (blank = weekly plan)
                <input
                  type="date"
                  value={day}
                  onChange={(e) => DAY(e.target.value)}
                />
              </label>
              <label>
                Filter by name
                <input value={filter} onChange={(e) => F(e.target.value)} />
              </label>
              <a href="/api/export.csv">Export weekly CSV</a>
              <button onClick={() => window.print()}>Print / Save PDF</button>
              <button
                onClick={() => {
                  if (!view?.version) return;
                  if (
                    confirm(
                      "Save this timetable on this device? Anyone using this browser can open the saved copy.",
                    )
                  ) {
                    localStorage.setItem(
                      offlineKey,
                      JSON.stringify({ at: Date.now(), data: view }),
                    );
                    M("Saved locally");
                  }
                }}
              >
                Save offline copy
              </button>
              <button onClick={offlineView}>Read saved copy</button>
            </div>
            {offline && (
              <p className="warning">
                OFFLINE COPY: read-only; may be outdated. {message}
              </p>
            )}
            <Schedule data={view} filter={filter} />
          </>
        )}
        {tab === "Academic data" && (
          <>
            <ResourceTable data={master} />
            {user.role === "admin" && (
              <div className="grid">
                <Form
                  title="Add resource"
                  fields={[
                    {
                      name: "kind",
                      options: ["teacher", "cohort", "room"].map((x) => ({
                        value: x,
                        label: x,
                      })),
                    },
                    { name: "name" },
                    {
                      name: "size",
                      label: "Capacity / cohort size (teacher = 1)",
                      type: "number",
                      value: 1,
                      min: 1,
                      max: 10000,
                    },
                  ]}
                  submit={(v) =>
                    perform(async () => {
                      await api("/resources", "POST", v);
                      await refresh();
                    })
                  }
                />
                <Form
                  title="Add teaching requirement"
                  fields={[
                    { name: "course" },
                    {
                      name: "teacher",
                      type: "number",
                      options: options("teacher"),
                    },
                    {
                      name: "cohort",
                      type: "number",
                      options: options("cohort"),
                    },
                    {
                      name: "sessions",
                      type: "number",
                      value: 3,
                      min: 1,
                      max: 10,
                    },
                    {
                      name: "duration",
                      type: "number",
                      value: 1,
                      min: 1,
                      max: 3,
                    },
                  ]}
                  submit={(v) =>
                    perform(async () => {
                      await api("/requirements", "POST", v);
                      await refresh();
                    })
                  }
                />
              </div>
            )}
          </>
        )}
        {tab === "Availability" && (
          <div className="grid">
            <Form
              title="Replace blocked slots"
              fields={[
                {
                  name: "resource",
                  type: "number",
                  options: (master?.resources || [])
                    .filter(
                      (r) => user.role === "admin" || r.id === user.teacher,
                    )
                    .map((r) => ({ value: r.id, label: r.name })),
                },
                {
                  name: "slots",
                  label: "Comma-separated slot IDs; use none to clear",
                  value: "none",
                },
              ]}
              submit={(v) =>
                perform(async () => {
                  await api("/availability", "PUT", {
                    resource: v.resource,
                    slots:
                      v.slots === "none" ? [] : v.slots.split(",").map(Number),
                  });
                  await refresh();
                })
              }
            />
            <section>
              <h3>Slot numbering</h3>
              <p>
                Monday 0–5; Tuesday 6–11; Wednesday 12–17; Thursday 18–23;
                Friday 24–29. Periods are abstract slots; configure clock times
                later.
              </p>
              <pre>{JSON.stringify(master?.blocks, null, 2)}</pre>
            </section>
            {user.role === "admin" && (
              <Form
                title="Constraint policy"
                fields={[
                  {
                    name: "max_daily",
                    type: "number",
                    value: master?.policy.max_daily,
                    min: 1,
                    max: 6,
                  },
                  {
                    name: "late_weight",
                    type: "number",
                    value: master?.policy.late_weight,
                    min: 0,
                    max: 100,
                  },
                ]}
                submit={(v) =>
                  perform(async () => {
                    await api("/policy", "PUT", v);
                    await refresh();
                  })
                }
              />
            )}
          </div>
        )}
        {tab === "Planning" && (
          <>
            <p>
              Generate a draft, inspect it, then publish. Generation runs in the
              worker.
            </p>
            <button
              disabled={busy}
              onClick={() =>
                perform(async () => {
                  await api("/jobs", "POST", { key: crypto.randomUUID() });
                  await refresh();
                })
              }
            >
              Generate timetable
            </button>
            <button
              onClick={() =>
                perform(async () => {
                  const r = await api("/versions", "POST");
                  D(await api("/versions/" + r.id));
                  await refresh();
                })
              }
            >
              New manual draft
            </button>
            <h3>Jobs</h3>
            {jobs.map((j) => (
              <div className="row" key={j.id}>
                #{j.id} {j.state} {j.result?.status}
                {j.result?.version && (
                  <button
                    onClick={() =>
                      perform(async () =>
                        D(await api("/versions/" + j.result.version)),
                      )
                    }
                  >
                    Open result
                  </button>
                )}
                {["queued", "running"].includes(j.state) && (
                  <button
                    onClick={() =>
                      perform(async () => {
                        await api("/jobs/" + j.id + "/cancel", "POST");
                        await refresh();
                      })
                    }
                  >
                    Cancel
                  </button>
                )}
              </div>
            ))}
            <h3>Versions</h3>
            {versions.map((v) => (
              <button
                key={v.id}
                onClick={() =>
                  perform(async () => D(await api("/versions/" + v.id)))
                }
              >
                #{v.id} {v.state}
              </button>
            ))}
            {draft && (
              <DraftEditor
                key={draft.version + ":" + draft.revision}
                draft={draft}
                master={master}
                save={(lessons) =>
                  perform(async () => {
                    await api("/versions/" + draft.version, "PUT", {
                      expected_revision: draft.revision,
                      lessons,
                    });
                    D(await api("/versions/" + draft.version));
                    await refresh();
                  })
                }
                publish={() =>
                  perform(async () => {
                    await api(
                      "/versions/" + draft.version + "/publish",
                      "POST",
                      {
                        expected_revision: draft.revision,
                        expected_published: master.published,
                      },
                    );
                    D(await api("/versions/" + draft.version));
                    await refresh();
                  })
                }
              />
            )}
          </>
        )}
        {tab === "Changes" && (
          <>
            <p>
              Cancel or move a session on one date. It keeps the same teacher
              and cohort.
            </p>
            <Schedule data={view} />
            <Form
              title="Dated change"
              fields={[
                {
                  name: "lesson",
                  type: "number",
                  options: (view?.lessons || []).map((l) => ({
                    value: l.id,
                    label: "Session #" + l.id,
                  })),
                },
                { name: "date", type: "date" },
                {
                  name: "cancelled",
                  options: [
                    { value: "false", label: "Move" },
                    { value: "true", label: "Cancel" },
                  ],
                },
                { name: "slot", type: "number", value: 0, min: 0, max: 29 },
                { name: "room", type: "number", options: options("room") },
              ]}
              submit={(v) =>
                perform(async () => {
                  await api("/exceptions", "POST", {
                    ...v,
                    cancelled: v.cancelled === "true",
                    version: view.version,
                    expected_revision: view.revision,
                  });
                  await refresh();
                })
              }
            />
          </>
        )}
        {tab === "Gateway" && (
          <>
            <p>
              The existing Ubuntu controller owns automatic profile selection.
            </p>
            {["start", "stop"].map((action) => (
              <button
                key={action}
                onClick={() => {
                  if (confirm(action + " the managed gateway services?"))
                    perform(async () => {
                      const r = await api("/gateway", "POST", { action });
                      if (!r.accepted) throw Error(r.error || "Not accepted");
                      M("Accepted; check last action and service status");
                    });
                }}
              >
                {action} gateway
              </button>
            ))}
            <p>
              {gateway?.available
                ? "Adapter connected"
                : "Unavailable / not configured"}
            </p>
            <p>
              {gateway?.snapshot?.controller_log_fresh
                ? "Controller measurements fresh"
                : "Measurements missing or stale. Charts retain historical samples only."}
            </p>
            <div className="grid">
              <Chart
                points={points}
                field="latency"
                label="ERP probe latency (ms)"
              />
              <Chart
                points={points}
                field="backlog"
                label="Queue backlog (bytes)"
              />
            </div>
            <pre>{JSON.stringify(gateway, null, 2)}</pre>
          </>
        )}
        {tab === "Diagnostics" && (
          <>
            <button
              onClick={() =>
                perform(async () => {
                  A(await api("/audit"));
                  MT(await api("/metrics"));
                })
              }
            >
              Refresh diagnostics
            </button>
            <pre>{JSON.stringify(metric, null, 2)}</pre>
            <pre>{JSON.stringify(audit, null, 2)}</pre>
          </>
        )}
        {tab === "Notices" && (
          <>
            <button onClick={() => perform(refresh)}>Refresh</button>
            {notices.map((n) => (
              <p key={n.id}>{n.message}</p>
            ))}
            {!notices.length && (
              <p>No notices yet. The worker delivers them.</p>
            )}
          </>
        )}
      </main>
    </>
  );
}
function ResourceTable({ data }) {
  return (
    <>
      <h3>Resources</h3>
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Kind</th>
            <th>Name</th>
            <th>Size</th>
          </tr>
        </thead>
        <tbody>
          {data?.resources.map((r) => (
            <tr key={r.id}>
              <td>{r.id}</td>
              <td>{r.kind}</td>
              <td>{r.name}</td>
              <td>{r.size}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <h3>Teaching requirements</h3>
      <pre>{JSON.stringify(data?.requirements, null, 2)}</pre>
    </>
  );
}
function Schedule({ data, filter = "" }) {
  if (!data?.version) return <p>No published timetable yet.</p>;
  const names = Object.fromEntries(
    data.snapshot.resources.map((r) => [r.id, r.name]),
  );
  const courses = Object.fromEntries(
    data.snapshot.requirements.map((r) => [r.id, r.course]),
  );
  return (
    <>
      <p>
        Version {data.version}, revision {data.revision}.{" "}
        {data.date
          ? "Date " + data.date
          : "Recurring weekly plan; select a date to include exceptions."}
      </p>
      <table>
        <thead>
          <tr>
            {["ID", "Day", "Period", "Course", "Teacher", "Cohort", "Room"].map(
              (x) => (
                <th key={x}>{x}</th>
              ),
            )}
          </tr>
        </thead>
        <tbody>
          {data.lessons
            .filter((l) =>
              [
                courses[l.requirement],
                names[l.teacher],
                names[l.cohort],
                names[l.room],
              ]
                .join(" ")
                .toLowerCase()
                .includes(filter.toLowerCase()),
            )
            .map((l) => (
              <tr key={l.id}>
                <td>{l.id}</td>
                <td>{days[Math.floor(l.slot / 6)]}</td>
                <td>
                  {(l.slot % 6) + 1}–{(l.slot % 6) + l.duration}
                </td>
                <td>{courses[l.requirement]}</td>
                <td>{names[l.teacher]}</td>
                <td>{names[l.cohort]}</td>
                <td>{names[l.room]}</td>
              </tr>
            ))}
        </tbody>
      </table>
    </>
  );
}
function DraftEditor({ draft, master, save, publish }) {
  const [lessons, L] = useState(draft.lessons.map(({ id, ...row }) => row));
  const [req, R] = useState(master?.requirements[0]?.id || "");
  const rooms = master?.resources.filter((r) => r.kind === "room") || [];
  function edit(i, k, v) {
    L((old) => old.map((r, j) => (j === i ? { ...r, [k]: Number(v) } : r)));
  }
  return (
    <section>
      <h2>
        Draft/version #{draft.version}: {draft.state}
      </h2>
      <p>Slot = day × 6 + period offset. Server checks every occupied slot.</p>
      <table>
        <thead>
          <tr>
            <th>Requirement</th>
            <th>Room</th>
            <th>Start slot</th>
            <th>Duration</th>
            <th>Remove</th>
          </tr>
        </thead>
        <tbody>
          {lessons.map((l, i) => (
            <tr key={i}>
              <td>{l.requirement}</td>
              <td>
                <select
                  value={l.room}
                  onChange={(e) => edit(i, "room", e.target.value)}
                >
                  {rooms.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.name}
                    </option>
                  ))}
                </select>
              </td>
              <td>
                <input
                  type="number"
                  min="0"
                  max="29"
                  value={l.slot}
                  onChange={(e) => edit(i, "slot", e.target.value)}
                />
              </td>
              <td>{l.duration}</td>
              <td>
                <button
                  onClick={() => L((old) => old.filter((_, j) => j !== i))}
                >
                  Remove
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {draft.state === "draft" && (
        <>
          <select value={req} onChange={(e) => R(Number(e.target.value))}>
            {master.requirements.map((r) => (
              <option key={r.id} value={r.id}>
                {r.course}
              </option>
            ))}
          </select>
          <button
            onClick={() => {
              const r = master.requirements.find((r) => r.id === Number(req));
              if (r && rooms.length)
                L((old) => [
                  ...old,
                  {
                    requirement: r.id,
                    teacher: r.teacher,
                    cohort: r.cohort,
                    room: rooms[0].id,
                    slot: 0,
                    duration: r.duration,
                  },
                ]);
            }}
          >
            Add session
          </button>
          <button onClick={() => save(lessons)}>Validate & save draft</button>
        </>
      )}
      <button
        onClick={() => {
          if (
            confirm(
              "Publish the saved server version? Unsaved edits are not included.",
            )
          )
            publish();
        }}
      >
        Publish saved version
      </button>
    </section>
  );
}
createRoot(document.getElementById("root")).render(
  <>
    <MouseTracer />
    <App />
  </>,
);
