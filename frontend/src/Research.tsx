import { useEffect, useState } from "react";
import { OutputView } from "./Presentation";
type Json = Record<string, unknown>;
async function load<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(
    "/api/v1" + path,
    body
      ? {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      : {},
  );
  const data = await response.json();
  if (!response.ok)
    throw new Error(data.error || data.detail || "Request failed");
  return data;
}
export function Comparison({ id }: { id: string }) {
  const [data, setData] = useState<{
    before: Json;
    after: Json;
    score: Json | null;
    changed_steps: string[];
    limitation: string;
  } | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    load<typeof data>(`/runs/${id}/comparison`)
      .then(setData)
      .catch((e) => setError(String(e)));
  }, [id]);
  return (
    <section>
      <h2>Original versus replay</h2>
      {error && <p role="alert">{error}</p>}
      {data ? (
        <>
          <p>Changed outputs: {data.changed_steps.join(", ") || "None"}</p>
          <div className="two-columns">
            <div>
              <h3>Original</h3>
              <OutputView value={data.before} />
            </div>
            <div>
              <h3>Replay</h3>
              <OutputView value={data.after} />
            </div>
          </div>
          <h3>Explicit expected-output scoring</h3>
          <pre>
            {data.score
              ? JSON.stringify(data.score, null, 2)
              : "Unavailable: no explicit step-keyed expected output supplied."}
          </pre>
          <p>{data.limitation}</p>
        </>
      ) : (
        <p>Loading comparison…</p>
      )}
    </section>
  );
}
export function Dataset({ readonly }: { readonly: boolean }) {
  const [cases, setCases] = useState<
    { id: string; family: string; split: string; payload: Json }[]
  >([]);
  const [versions, setVersions] = useState<
    { id: string; name: string; created_at: string }[]
  >([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [name, setName] = useState("Reviewed feedback");
  const [error, setError] = useState("");
  const [preview, setPreview] = useState<Json | null>(null);
  const [offset, setOffset] = useState(0);
  const refresh = () =>
    load<typeof versions>("/datasets/versions").then(setVersions);
  useEffect(() => {
    load<typeof cases>(`/datasets?limit=25&offset=${offset}`)
      .then(setCases)
      .catch((e) => setError(String(e)));
    refresh().catch((e) => setError(String(e)));
  }, [offset]);
  return (
    <>
      <h1>Review dataset</h1>
      <p>
        Feedback is separate from frozen synthetic test families. Conflicting
        and unclear reviews are excluded. A frozen snapshot preserves the labels
        known at that time.
      </p>
      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
      <section>
        <h2>Eligible feedback cases</h2>
        {cases.length ? (
          cases.map((item) => (
            <div key={item.id}>
              <label className="check">
                <input
                  type="checkbox"
                  checked={selected.includes(item.id)}
                  onChange={(e) =>
                    setSelected(
                      e.target.checked
                        ? [...selected, item.id]
                        : selected.filter((id) => id !== item.id),
                    )
                  }
                />
                {item.id.slice(0, 8)} · {item.split} · family{" "}
                {item.family.slice(0, 10)}
              </label>
              <details>
                <summary>Label, provenance and expected output</summary>
                <pre>{JSON.stringify(item.payload, null, 2)}</pre>
              </details>
            </div>
          ))
        ) : (
          <p>No eligible feedback cases yet. Review an investigation first.</p>
        )}
        <div className="actions">
          <button
            disabled={!offset}
            onClick={() => setOffset(Math.max(0, offset - 25))}
          >
            Previous
          </button>
          <button
            disabled={cases.length < 25}
            onClick={() => setOffset(offset + 25)}
          >
            Next
          </button>
        </div>
        <label>
          Snapshot name
          <input value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <button
          disabled={readonly || !selected.length || !name.trim()}
          onClick={async () => {
            try {
              await load("/datasets/versions", { name, case_ids: selected });
              await refresh();
              setSelected([]);
            } catch (e) {
              setError(String(e));
            }
          }}
        >
          Freeze selected cases
        </button>
      </section>
      <section>
        <h2>Immutable versions</h2>
        {versions.map((version) => (
          <p key={version.id}>
            <button
              onClick={() =>
                load<Json>(`/datasets/versions/${version.id}/export`)
                  .then(setPreview)
                  .catch((e) => setError(String(e)))
              }
            >
              {version.name} · {version.id.slice(0, 10)}
            </button>{" "}
            <a href={`/api/v1/datasets/versions/${version.id}/export`} download>
              Export sanitized JSON
            </a>
          </p>
        ))}
        {preview && <pre>{JSON.stringify(preview, null, 2)}</pre>}
      </section>
    </>
  );
}
export function Experiments({ readonly }: { readonly: boolean }) {
  const [reports, setReports] = useState<{ id: string; report: Json }[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const refresh = () => load<typeof reports>("/experiments").then(setReports);
  useEffect(() => {
    refresh().catch((e) => setError(String(e)));
  }, []);
  return (
    <>
      <h1>Experiments</h1>
      <p>
        Run the 72-case synthetic mechanics benchmark. This does not measure
        real-model accuracy or human agreement.
      </p>
      {error && <p role="alert">{error}</p>}
      <section>
        <button
          disabled={readonly || busy}
          onClick={async () => {
            setBusy(true);
            try {
              await load("/experiments", {
                mode: "synthetic",
                dataset_version: "curated-mechanics-1",
                idempotency_key: crypto.randomUUID(),
              });
              await refresh();
            } catch (e) {
              setError(String(e));
            } finally {
              setBusy(false);
            }
          }}
        >
          {busy ? "Running fixture checks…" : "Run synthetic benchmark"}
        </button>
        <p>
          Real-model experiments: not run. A separately configured
          producer/judge, explicit call budget and actual hardware are required.
        </p>
      </section>
      {reports.map((item) => (
        <section key={item.id}>
          <h2>Fixture report {item.id.slice(0, 10)}</h2>
          <pre>{JSON.stringify(item.report, null, 2)}</pre>
          <a href={`/api/v1/experiments/${item.id}/results`}>
            Inspect paginated case results
          </a>
        </section>
      ))}
    </>
  );
}
