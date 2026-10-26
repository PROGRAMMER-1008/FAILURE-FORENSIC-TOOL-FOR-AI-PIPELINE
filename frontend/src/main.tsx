import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";
import {
  FindingSummary,
  CorrectionEditor,
  stepName,
} from "./InvestigationHelp";
import { PipelineGraph } from "./PipelineGraph";
import { OutputView, WorkflowGuide } from "./Presentation";
import { Comparison, Dataset, Experiments } from "./Research";

type Json = Record<string, unknown>;
type Attempt = {
  id: string;
  step_id: string;
  number: number;
  dependencies: string[];
  inputs: Json;
  result: {
    status: string;
    output: Json | null;
    raw_response: string;
    error: string | null;
    provider: string;
    model: string;
    elapsed_seconds: number;
  };
  judgment: Json | null;
};
type Run = {
  pipeline: { steps: { id: string; dependencies: string[] }[] };
  id: string;
  status: string;
  quality: string;
  revision: number;
  source: string;
  parent_id: string | null;
  config: Json;
  attempts: Attempt[];
  finding: {
    revision: number;
    origins: string[];
    symptoms: string[];
    potentially_affected: string[];
    abstention_reason: string | null;
    label: string;
    evidence: Json[];
    alternatives: string[];
  } | null;
};
type Row = {
  id: string;
  status: string;
  quality: string;
  created_at: string | null;
};
type Config = {
  ai_ready: boolean;
  credential_status: string;
  mode: string;
  provider: string;
  producer_model: string;
  judge_model: string;
  correlated_judge: boolean;
  sample: string;
  max_characters: number;
  groq_daily_calls: number;
  groq_max_completion_tokens: number;
  retention: string;
};
const terminal = (status: string) =>
  ["succeeded", "failed", "cancelled"].includes(status);
export async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(
    "/api/v1" + path,
    body === undefined
      ? {}
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  const result = await response.json();
  if (response.status === 401 && result.error === "sign_in_required") {
    window.location.assign("/auth/login");
    throw new Error("Your session expired. Please sign in again.");
  }
  if (!response.ok)
    throw new Error(
      result.error || result.detail || `Request failed (${response.status})`,
    );
  return result;
}
function Code({ value }: { value: unknown }) {
  return (
    <pre>
      {typeof value === "string" ? value : JSON.stringify(value, null, 2)}
    </pre>
  );
}
function App() {
  const [page, setPage] = useState(location.hash.slice(1) || "overview");
  const [config, setConfig] = useState<Config | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [rows, setRows] = useState<Row[]>([]);
  const [statsLoaded, setStatsLoaded] = useState(false);
  const [search, setSearch] = useState("");
  const [since, setSince] = useState("");
  const [oldest, setOldest] = useState(false);
  const [stats, setStats] = useState<
    { status: string; quality: string; count: number }[]
  >([]);
  const [offset, setOffset] = useState(0);
  const [filter, setFilter] = useState("");
  const [source, setSource] = useState("");
  const [injected, setInjected] = useState(false);
  const [run, setRun] = useState<Run | null>(null);
  const [events, setEvents] = useState<Json[]>([]);
  const [selected, setSelected] = useState("extract");
  const [history, setHistory] = useState<Json[]>([]);
  const [reviewer, setReviewer] = useState("Local reviewer");
  const [verdict, setVerdict] = useState("unclear");
  const [origins, setOrigins] = useState("");
  const [notes, setNotes] = useState("");
  const [expected, setExpected] = useState("");
  const [corrected, setCorrected] = useState("");
  const [notice, setNotice] = useState("");
  const readonly = config?.mode === "demo";
  const go = (target: string) => {
    location.hash = target;
  };
  const act = async (work: () => Promise<void>) => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await work();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => {
    const change = () => {
      setPage(location.hash.slice(1) || "overview");
      setError("");
      setNotice("");
    };
    window.addEventListener("hashchange", change);
    api<Config>("/config")
      .then(setConfig)
      .catch((e) => setError(String(e)));
    return () => window.removeEventListener("hashchange", change);
  }, []);
  useEffect(() => {
    if (page === "overview" || page === "runs") {
      api<{ items: Row[] }>(
        `/runs?limit=12&offset=${offset}&status=${filter}&q=${encodeURIComponent(search)}&oldest_first=${oldest}${since ? "&since=" + encodeURIComponent(new Date(since).toISOString()) : ""}`,
      )
        .then((r) => setRows(r.items))
        .catch((e) => setError(String(e)));
      api<typeof stats>("/stats")
        .then((value) => {
          setStats(value);
          setStatsLoaded(true);
        })
        .catch((e) => setError(String(e)));
    }
  }, [page, offset, filter, search, since, oldest]);
  useEffect(() => {
    if (!page.startsWith("run/")) return;
    const id = page.slice(4);
    let active = true;
    setRun(null);
    setCorrected("");
    setOrigins("");
    setVerdict("unclear");
    setNotes("");
    setExpected("");
    setHistory([]);
    setEvents([]);
    const refresh = () =>
      api<Run>("/runs/" + id).then((r) => {
        if (active) setRun(r);
      });
    refresh().catch((e) => setError(String(e)));
    api<Json[]>(`/runs/${id}/reviews`)
      .then(setHistory)
      .catch((e) => setError(String(e)));
    const stream = new EventSource(`/api/v1/runs/${id}/events`);
    const update = (event: MessageEvent) => {
      if (active) {
        setEvents((items) => [...items.slice(-29), JSON.parse(event.data)]);
        refresh().catch((e) => setError(String(e)));
      }
    };
    for (const kind of [
      "queued",
      "running",
      "step_started",
      "step_finished",
      "step_skipped",
      "cancel_requested",
      "succeeded",
      "failed",
      "cancelled",
    ])
      stream.addEventListener(kind, update as EventListener);
    const poll = window.setInterval(
      () =>
        refresh().catch(() =>
          setNotice("Connection unavailable. Retrying persisted status…"),
        ),
      3000,
    );
    return () => {
      active = false;
      stream.close();
      clearInterval(poll);
    };
  }, [page]);
  useEffect(() => {
    if (run && terminal(run.status))
      setNotice(
        "Execution finished. Diagnosis remains a hypothesis until reviewed.",
      );
  }, [run?.status]);
  const submit = () =>
    act(async () => {
      const result = await api<{ id: string }>("/runs", {
        text: source,
        injected,
        idempotency_key: crypto.randomUUID(),
      });
      go("run/" + result.id);
    });
  const span = run?.attempts.filter((a) => a.step_id === selected).at(-1);
  return (
    <div className="app">
      <a className="skip" href="#main">
        Skip to content
      </a>
      <aside>
        <a className="brand" href="#overview">
          <span className="mark">F/</span>
          <span>
            FAILURE
            <br />
            <b>FORENSICS</b>
          </span>
        </a>
        <p className="eyebrow">DOCUMENT PIPELINE LAB</p>
        <nav aria-label="Primary">
          {[
            ["overview", "Overview"],
            ["new", "New investigation"],
            ["runs", "Runs explorer"],
            ["dataset", "Review dataset"],
            ["experiments", "Experiments"],
            ["settings", "Settings & status"],
          ].map(([key, label]) => (
            <a
              key={key}
              href={"#" + key}
              aria-current={page === key ? "page" : undefined}
            >
              {label}
            </a>
          ))}
        </nav>
        <div className="aside-footer">
          <span className="dot" />{" "}
          {config?.provider === "fake"
            ? "Synthetic provider"
            : config?.provider === "groq"
              ? "Groq cloud API"
              : "Local Ollama"}
          <p>{readonly ? "Recorded demo · read only" : "Local workspace"}</p>
          <small>
            Evidence first.
            <br />
            Certainty earned.
          </small>
        </div>
        {config?.mode === "hosted" && <a href="/auth/logout">Sign out</a>}
      </aside>
      <main id="main">
        <header>
          <span className="eyebrow">
            WORKSPACE /{" "}
            {page.startsWith("run/") ? "INVESTIGATION" : page.toUpperCase()}
          </span>
          <span className="badge">
            {config?.provider === "fake"
              ? "SYNTHETIC · NOT MODEL PERFORMANCE"
              : config?.provider === "groq"
                ? "GROQ CLOUD INFERENCE"
                : "LOCAL INFERENCE"}
          </span>
        </header>
        {config?.ai_ready === false && (
          <p role="status" className="notice">
            AI setup is incomplete. Add your Groq key locally, restart the app,
            then submit a document.{" "}
            <a href="#settings">View setup instructions</a>
          </p>
        )}
        {error && (
          <div role="alert" className="alert">
            {error}
            <button onClick={() => location.reload()}>Reload</button>
          </div>
        )}
        {notice && (
          <p role="status" className="notice">
            {notice}
          </p>
        )}
        {(page === "overview" || page === "runs") && (
          <>
            <div className="title">
              <div>
                <p className="eyebrow">OBSERVE / INVESTIGATE / VERIFY</p>
                <h1>
                  {page === "overview"
                    ? "Find where things went wrong."
                    : "Run explorer"}
                </h1>
                <p>
                  Trace the evidence from source to output. Separate suspected
                  origins from downstream symptoms.
                </p>
              </div>
              <a className="button primary" href="#new">
                + New investigation
              </a>
            </div>
            {page === "overview" && <WorkflowGuide />}
            <div className="metrics">
              <section>
                <p>Recorded runs</p>
                <strong>
                  {statsLoaded ? stats.reduce((n, s) => n + s.count, 0) : "—"}
                </strong>
                <small>Persisted in this workspace</small>
              </section>
              <section>
                <p>Execution failures</p>
                <strong>
                  {statsLoaded
                    ? stats
                        .filter((s) => s.status === "failed")
                        .reduce((n, s) => n + s.count, 0)
                    : "—"}
                </strong>
                <small>Separate from quality findings</small>
              </section>
              <section>
                <p>Suspected quality issues</p>
                <strong>
                  {statsLoaded
                    ? stats
                        .filter((s) => s.quality === "suspected_issue")
                        .reduce((n, s) => n + s.count, 0)
                    : "—"}
                </strong>
                <small>Hypotheses awaiting review</small>
              </section>
            </div>
            <section>
              <div className="section-title">
                <h2>Recent investigations</h2>
                <label>
                  Run ID or source hash
                  <input
                    value={search}
                    onChange={(e) => {
                      setSearch(e.target.value);
                      setOffset(0);
                    }}
                  />
                </label>
                <label>
                  Created since
                  <input
                    type="date"
                    value={since}
                    onChange={(e) => {
                      setSince(e.target.value);
                      setOffset(0);
                    }}
                  />
                </label>
                <label>
                  Order
                  <select
                    value={oldest ? "oldest" : "newest"}
                    onChange={(e) => setOldest(e.target.value === "oldest")}
                  >
                    <option value="newest">Newest first</option>
                    <option value="oldest">Oldest first</option>
                  </select>
                </label>
                <label>
                  Execution{" "}
                  <select
                    value={filter}
                    onChange={(e) => {
                      setFilter(e.target.value);
                      setOffset(0);
                    }}
                  >
                    <option value="">All states</option>
                    {[
                      "queued",
                      "running",
                      "succeeded",
                      "failed",
                      "cancelled",
                    ].map((s) => (
                      <option key={s}>{s}</option>
                    ))}
                  </select>
                </label>
              </div>
              {rows.length ? (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Run</th>
                        <th>Execution</th>
                        <th>Quality</th>
                        <th>Created</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((row) => (
                        <tr key={row.id}>
                          <td>
                            <a href={"#run/" + row.id}>
                              {row.id.slice(0, 8)} →
                            </a>
                          </td>
                          <td>
                            <span className={`state state-${row.status}`}>
                              {row.status}
                            </span>
                          </td>
                          <td>{row.quality.replaceAll("_", " ")}</td>
                          <td>
                            {row.created_at
                              ? new Date(row.created_at).toLocaleString()
                              : "Unknown (legacy)"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="empty">
                  <h3>No investigations yet.</h3>
                  <p>
                    Start with an invented invoice to inspect an injected
                    extraction mistake.
                  </p>
                  <a href="#new">Open a synthetic case →</a>
                </div>
              )}
              <div className="actions">
                <button
                  disabled={!offset}
                  onClick={() => setOffset(Math.max(0, offset - 12))}
                >
                  Previous
                </button>
                <span>Page {offset / 12 + 1}</span>
                <button
                  disabled={rows.length < 12}
                  onClick={() => setOffset(offset + 12)}
                >
                  Next
                </button>
              </div>
            </section>
          </>
        )}
        {page === "new" && (
          <>
            <h1>Start an investigation</h1>
            <p>
              Source content is stored locally after secret redaction. Automated
              redaction does not identify every private detail.
            </p>
            {config?.provider === "groq" && (
              <p className="notice">
                Groq cloud mode: submitting a document sends its redacted text
                and pipeline outputs to Groq for generation and evaluation.
                Calls use your account quota and may incur charges.
              </p>
            )}
            <section>
              <div className="section-title">
                <h2>Document source</h2>
                <button
                  onClick={() => {
                    setSource(config?.sample || "");
                    setInjected(config?.provider === "fake");
                  }}
                >
                  Load invented invoice
                </button>
              </div>
              <label htmlFor="source">
                Document text · maximum {config?.max_characters || 20000}{" "}
                characters
              </label>
              <textarea
                id="source"
                rows={10}
                maxLength={config?.max_characters || 20000}
                value={source}
                onChange={(e) => {
                  setSource(e.target.value);
                  setInjected(false);
                }}
                placeholder="Paste document text or load the synthetic sample"
              />
              <label className="check">
                <input
                  type="checkbox"
                  checked={injected}
                  disabled={
                    config?.provider !== "fake" || source !== config?.sample
                  }
                  onChange={(e) => setInjected(e.target.checked)}
                />{" "}
                Inject a known extraction mistake (synthetic sample only)
              </label>
              <div className="actions">
                <button
                  className="primary"
                  disabled={
                    busy ||
                    readonly ||
                    config?.ai_ready === false ||
                    !source.trim()
                  }
                  onClick={submit}
                >
                  Queue investigation
                </button>
                <label className="upload">
                  Or upload UTF-8 TXT, PDF or DOCX
                  <input
                    type="file"
                    accept=".txt,.pdf,.docx"
                    disabled={busy || readonly || config?.ai_ready === false}
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file)
                        act(async () => {
                          const response = await fetch("/api/v1/uploads", {
                            method: "POST",
                            headers: {
                              "Content-Type": file.type || "text/plain",
                              "Idempotency-Key": crypto.randomUUID(),
                            },
                            body: file,
                          });
                          const result = await response.json();
                          if (!response.ok)
                            throw new Error(result.detail || result.error);
                          go("run/" + result.id);
                        });
                    }}
                  />
                </label>
              </div>
              {readonly && (
                <p>
                  Public recorded demo: submissions are disabled by the server.
                </p>
              )}
              {config?.provider === "fake" && (
                <p className="notice">
                  Fake provider returns fixed synthetic outputs. Arbitrary
                  documents are not meaningfully analyzed.
                </p>
              )}
            </section>
          </>
        )}
        {page.startsWith("run/") &&
          (!run ? (
            <p role="status">Loading persisted investigation…</p>
          ) : (
            <>
              <div className="title">
                <div>
                  <p className="eyebrow">{run.id}</p>
                  <h1>Investigation</h1>
                  <a href={`/api/v1/runs/${run.id}/export`} download>Download investigation</a>
                  <p>
                    <b>{run.status}</b> execution ·{" "}
                    {run.quality.replaceAll("_", " ")}
                  </p>
                </div>
                {!terminal(run.status) && (
                  <button
                    disabled={busy || readonly}
                    onClick={() =>
                      act(async () => {
                        await api(`/runs/${run.id}/cancel`, {});
                        setNotice(
                          "Cancellation requested. An in-flight call may finish.",
                        );
                      })
                    }
                  >
                    Cancel future steps
                  </button>
                )}
              </div>
              <FindingSummary status={run.status} finding={run.finding} />
              {run.parent_id && terminal(run.status) && (
                <Comparison id={run.id} />
              )}{" "}
              {run.parent_id && (
                <p>
                  Replay of{" "}
                  <a href={"#run/" + run.parent_id}>
                    {run.parent_id.slice(0, 8)}
                  </a>
                  . Originals remain unchanged.
                </p>
              )}
              <section>
                <h2>1. Follow the document through each step</h2>
                <PipelineGraph
                  steps={run.pipeline.steps}
                  attempts={run.attempts}
                  selected={selected}
                  onSelect={setSelected}
                  origins={run.finding?.origins}
                  symptoms={run.finding?.symptoms}
                />
              </section>
              <div className="two-columns">
                <section>
                  <h2>2. Check against the original</h2>
                  <p>
                    Read the source alongside the selected output. Check names,
                    amounts and conclusions before accepting the result.
                  </p>
                  <div className="source-text">{run.source}</div>
                  <details>
                    <summary>Why the automated review flagged this run</summary>
                    <p>{run.finding?.label || "Waiting for evidence"}</p>
                    <dl>
                      <dt>Possible starting point</dt>
                      <dd>
                        {run.finding?.origins.map(stepName).join(", ") ||
                          "Not established"}
                      </dd>
                      <dt>Later outputs with observed errors</dt>
                      <dd>
                        {run.finding?.symptoms.map(stepName).join(", ") ||
                          "None established"}
                      </dd>
                    </dl>
                    {run.finding?.abstention_reason && (
                      <p className="notice">
                        Uncertainty: {run.finding.abstention_reason}
                      </p>
                    )}
                    <details>
                      <summary>Technical evidence and alternatives</summary>
                      <Code value={run.finding} />
                    </details>
                  </details>
                </section>
                <section>
                  <h2>Output: {stepName(selected)}</h2>
                  {span ? (
                    <>
                      <p>
                        Attempt {span.number} · {span.result.status} ·{" "}
                        {span.result.elapsed_seconds.toFixed(3)}s
                      </p>
                      <p>
                        {span.result.provider} / {span.result.model}
                      </p>
                      {span.result.error && (
                        <p className="alert">{span.result.error}</p>
                      )}
                      <h3>Output at a glance</h3>
                      <OutputView value={span.result.output} />
                      <details>
                        <summary>Structured output</summary>
                        <Code value={span.result.output} />
                      </details>
                      <details>
                        <summary>Structured input</summary>
                        <Code value={span.inputs} />
                      </details>
                      <details>
                        <summary>Sanitized literal response · redacted</summary>
                        <Code value={span.result.raw_response} />
                      </details>
                      <details>
                        <summary>Evaluator judgment</summary>
                        <Code value={span.judgment} />
                      </details>
                    </>
                  ) : (
                    <p>No attempt recorded yet.</p>
                  )}
                </section>
              </div>
              <section>
                <h2>Source and execution timeline</h2>
                <details>
                  <summary>Stored source (may contain private text)</summary>
                  <Code value={run.source} />
                </details>
                <ol>
                  {run.attempts.map((a) => (
                    <li key={a.id}>
                      {a.step_id} · attempt {a.number} · {a.result.status}
                    </li>
                  ))}
                </ol>
                <details>
                  <summary>Persisted events received this session</summary>
                  <Code value={events} />
                </details>
              </section>
              {terminal(run.status) && (
                <div className="two-columns">
                  <section>
                    <h2>3. Record your review</h2>
                    <p>
                      Decide whether the suspected starting point matches the
                      evidence. Choose Unsure if you cannot tell; you do not
                      need to correct an output to leave a review.
                    </p>
                    <label>
                      Reviewer
                      <input
                        value={reviewer}
                        onChange={(e) => setReviewer(e.target.value)}
                      />
                    </label>
                    <label htmlFor="review-verdict">
                      Verdict
                      <select
                        id="review-verdict"
                        value={verdict}
                        onChange={(e) => setVerdict(e.target.value)}
                      >
                        {[
                          "confirm",
                          "correct",
                          "unclear",
                          "no_issue",
                          "missed_failure",
                        ].map((v) => (
                          <option key={v} value={v}>
                            {
                              {
                                confirm: "Confirm the suspected origin",
                                correct: "Correct the origin label",
                                unclear: "Unsure - evidence is insufficient",
                                no_issue: "No issue found",
                                missed_failure: "Report a missed failure",
                              }[v]
                            }
                          </option>
                        ))}
                      </select>
                    </label>
                    {verdict !== "no_issue" && (
                      <fieldset className="origin-picker">
                        <legend>Where do you think the problem starts?</legend>
                        <p className="field-help">
                          Select the step or steps supported by the source.
                          Leave empty if unsure.
                        </p>
                        {run.pipeline.steps.map((step) => (
                          <label className="check" key={step.id}>
                            <input
                              type="checkbox"
                              checked={origins.split(",").includes(step.id)}
                              onChange={(event) => {
                                const chosen = origins
                                  .split(",")
                                  .filter(Boolean);
                                setOrigins(
                                  (event.target.checked
                                    ? [...chosen, step.id]
                                    : chosen.filter((id) => id !== step.id)
                                  ).join(","),
                                );
                              }}
                            />
                            {stepName(step.id)}
                          </label>
                        ))}
                      </fieldset>
                    )}
                    <label>
                      Notes
                      <textarea
                        value={notes}
                        onChange={(e) => setNotes(e.target.value)}
                      />
                    </label>
                    <details>
                      <summary>
                        Advanced: add expected output for scoring
                      </summary>
                      <p>
                        Optional JSON keyed by step ID. Leave blank when
                        reviewing only the diagnosis.
                      </p>
                      <label>
                        Expected output JSON (optional)
                        <textarea
                          value={expected}
                          onChange={(e) => setExpected(e.target.value)}
                          placeholder="Leave blank if only labeling the diagnosis"
                        />
                      </label>
                    </details>
                    <button
                      className="primary"
                      disabled={busy || readonly}
                      onClick={() =>
                        act(async () => {
                          await api(`/runs/${run.id}/reviews`, {
                            idempotency_key: crypto.randomUUID(),
                            reviewer,
                            revision: run.revision,
                            target_finding_revision: run.finding?.revision || 1,
                            verdict,
                            origins:
                              verdict === "no_issue"
                                ? []
                                : origins
                                    .split(",")
                                    .map((s) => s.trim())
                                    .filter(Boolean),
                            notes,
                            expected_output: expected
                              ? JSON.parse(expected)
                              : null,
                          });
                          setRun(await api<Run>("/runs/" + run.id));
                          setHistory(
                            await api<Json[]>(`/runs/${run.id}/reviews`),
                          );
                          setNotice(
                            "Review saved. Inspect the dataset for label eligibility.",
                          );
                        })
                      }
                    >
                      Save review
                    </button>
                    <details>
                      <summary>
                        Append-only review history ({history.length})
                      </summary>
                      <Code value={history} />
                    </details>
                  </section>
                  <section>
                    <h2>4. Test a correction (optional)</h2>
                    <p>
                      Your original run stays unchanged. Editing a fact creates
                      a new run and updates the summary. The document
                      classification is reused.
                    </p>
                    <p>
                      Copy this run's extraction, edit the incorrect facts, then
                      replay. Copying alone does not correct the output.
                    </p>
                    <button
                      disabled={
                        !run.attempts.some(
                          (a) => a.step_id === "extract" && a.result.output,
                        )
                      }
                      onClick={() =>
                        setCorrected(
                          JSON.stringify(
                            run.attempts
                              .filter((a) => a.step_id === "extract")
                              .at(-1)?.result.output,
                            null,
                            2,
                          ),
                        )
                      }
                    >
                      Copy facts to edit
                    </button>
                    <CorrectionEditor
                      value={corrected}
                      onChange={setCorrected}
                    />
                    <details>
                      <summary>Advanced: edit correction JSON</summary>
                      <label>
                        Corrected extraction JSON
                        <textarea
                          rows={6}
                          value={corrected}
                          onChange={(e) => setCorrected(e.target.value)}
                        />
                      </label>
                    </details>
                    <button
                      disabled={
                        busy ||
                        readonly ||
                        config?.ai_ready === false ||
                        !corrected.trim()
                      }
                      onClick={() =>
                        act(async () => {
                          const result = await api<{ id: string }>(
                            `/runs/${run.id}/replays`,
                            {
                              idempotency_key: crypto.randomUUID(),
                              mode: "reexecute",
                              description:
                                "Human-provided extraction correction",
                              step_id: "extract",
                              corrected_output: JSON.parse(corrected),
                            },
                          );
                          go("run/" + result.id);
                        })
                      }
                    >
                      Run with my correction
                    </button>
                    <button
                      disabled={busy || readonly || config?.ai_ready === false}
                      onClick={() =>
                        act(async () => {
                          const result = await api<{ id: string }>(
                            `/runs/${run.id}/replays`,
                            {
                              idempotency_key: crypto.randomUUID(),
                              mode: "reexecute",
                              description: "Unchanged rerun control",
                            },
                          );
                          go("run/" + result.id);
                        })
                      }
                    >
                      Run again without changes
                    </button>
                    <p>
                      Compare the new result with the original to see what
                      changed. A changed result alone does not prove the
                      suspected cause. Accuracy scores require expected answers
                      supplied by a reviewer.
                    </p>
                  </section>
                </div>
              )}
            </>
          ))}
        {page === "dataset" && <Dataset readonly={readonly} />}
        {page === "experiments" && <Experiments readonly={readonly} />}
        {page === "settings" && (
          <>
            <h1>Settings & status</h1>
            <section className="workflow-guide">
              <p className="eyebrow">CONNECT YOUR AI</p>
              <h2>Groq setup in three steps</h2>
              {config?.mode === "hosted" ? (
                <p>Manage your Groq key in Render's secret environment settings, then redeploy the web service and worker. Never enter the key in this browser.</p>
              ) : <ol>
                <li>
                  Open the project's <code>.env</code> file in your own editor.
                </li>
                <li>
                  Set <code>FF_PROVIDER=groq</code> and paste your key after{" "}
                  <code>FF_GROQ_API_KEY=</code>. Keep the key out of chat and
                  browser fields.
                </li>
                <li>
                  Save, stop the launcher with Ctrl+C, and double-click{" "}
                  <code>start-local.cmd</code> again. Open{" "}
                  <a href="http://127.0.0.1:8001">localhost:8001</a>.
                </li>
              </ol>}
              <p>
                Credential status:{" "}
                <strong>
                  {config?.provider !== "groq"
                    ? "Not needed in the current mode"
                    : config?.credential_status === "missing"
                      ? "Missing — add your key and restart"
                      : "Key configured — not yet verified with Groq"}
                </strong>
              </p>
              <p>
                The key stays on the backend. Groq receives redacted document
                text and intermediate outputs when you submit. A normal run
                makes up to six generation/evaluation calls before retries; your
                account quota applies.
              </p>
              {config?.provider === "groq" && <p>
                This workspace allows up to {config.groq_daily_calls} AI calls per UTC day,
                including evaluation and retries. Each response is capped at {config.groq_max_completion_tokens} output tokens.
                These limits do not set a monetary spending cap on your Groq account.
              </p>}
              <p>
                To try the workflow without AI, use{" "}
                <code>FF_PROVIDER=fake</code>. To change models, edit{" "}
                <code>FF_PRODUCER_MODEL</code> and <code>FF_JUDGE_MODEL</code>.
                Environment variables override the file; changes require a
                restart.
              </p>
            </section>
            <section>
              <h2>Configured execution</h2>
              <Code
                value={
                  config && {
                    mode: config.mode,
                    provider: config.provider,
                    producer_model: config.producer_model,
                    judge_model: config.judge_model,
                    retention: config.retention,
                  }
                }
              />
              {config?.correlated_judge && (
                <p>
                  Producer and judge model settings match. Their errors may be
                  correlated.
                </p>
              )}
              <p>{config?.mode === "hosted"
                ? "This is your private owner workspace. Sessions expire after one hour by default. Sign out when finished; do not share your workspace password."
                : "Private proxy mode requires a trusted authentication proxy and one allowed identity. Hosted owner mode uses the built-in sign-in. There is no cloud fallback."}</p>
            </section>
          </>
        )}
        <footer>
          Failure Forensics v2 · Evidence-backed debugging · Local development
          preview
        </footer>
      </main>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
