import { useId } from "react";

type Step = { id: string; dependencies: string[] };
type Attempt = { step_id: string; result: { status: string } };
const labels: Record<string, string> = {
  document: "Source document",
  extract: "Extract facts",
  classify: "Classify document",
  summarize: "Summarize",
};
const connections = [
  {
    from: "document",
    to: "extract",
    wide: "M200 145 H275 V70 H350",
    narrow: "M115 80 V125 H72 V180",
  },
  {
    from: "document",
    to: "classify",
    wide: "M200 175 H275 V260 H350",
    narrow: "M205 80 V125 H230 V180",
  },
  {
    from: "extract",
    to: "summarize",
    wide: "M530 70 H620 V145 H700",
    narrow: "M72 280 V340 H115 V400",
  },
  {
    from: "classify",
    to: "summarize",
    wide: "M530 260 H620 V175 H700",
    narrow: "M230 280 V340 H205 V400",
  },
  {
    from: "document",
    to: "summarize",
    wide: "M110 200 V330 H790 V200",
    narrow: "M250 40 H312 V445 H250",
  },
];

export function PipelineGraph({
  steps,
  attempts,
  selected,
  onSelect,
  origins = [],
  symptoms = [],
}: {
  steps: Step[];
  attempts: Attempt[];
  selected: string;
  onSelect: (id: string) => void;
  origins?: string[];
  symptoms?: string[];
}) {
  const marker = useId().replaceAll(":", "");
  const edges = connections.filter((edge) =>
    steps.some(
      (step) => step.id === edge.to && step.dependencies.includes(edge.from),
    ),
  );
  return (
    <figure className="pipeline-figure" aria-label="Pipeline dependency graph">
      <div className="pipeline-canvas">
        {(["wide", "narrow"] as const).map((layout) => (
          <svg
            key={layout}
            className={`pipeline-lines ${layout}`}
            viewBox={layout === "wide" ? "0 0 900 360" : "0 0 320 500"}
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            <defs>
              <marker
                id={`${marker}-${layout}`}
                viewBox="0 0 10 10"
                refX="9"
                refY="5"
                markerWidth="7"
                markerHeight="7"
                orient="auto-start-reverse"
              >
                <path d="M0 0 L10 5 L0 10 Z" fill="currentColor" />
              </marker>
            </defs>
            {edges.map((edge) => (
              <path
                key={`${edge.from}-${edge.to}`}
                data-edge={`${edge.from}-${edge.to}`}
                d={edge[layout]}
                className={
                  edge.to === selected || edge.from === selected
                    ? "edge-active"
                    : ""
                }
                markerEnd={`url(#${marker}-${layout})`}
              />
            ))}
          </svg>
        ))}
        <div className="pipeline-node node-document">
          <span className="node-kicker">INPUT</span>
          <strong>Source document</strong>
          <small>Original evidence</small>
        </div>
        {steps.map((step) => (
          <button
            key={step.id}
            className={`pipeline-node node-${step.id}`}
            aria-pressed={selected === step.id}
            onClick={() => onSelect(step.id)}
          >
            <span className="node-kicker">
              {origins.includes(step.id)
                ? "SUSPECTED ORIGIN"
                : symptoms.includes(step.id)
                  ? "OBSERVED SYMPTOM"
                  : "PIPELINE STEP"}
            </span>{" "}
            <strong>{labels[step.id] || step.id}</strong>{" "}
            <small>
              {attempts.filter((a) => a.step_id === step.id).at(-1)?.result
                .status || "pending"}
            </small>
          </button>
        ))}
      </div>
      <figcaption>
        Arrows show which inputs each step uses. Select a step to inspect its
        output. Extraction and classification run independently; the summary
        also reads the original document.
      </figcaption>
      <details>
        <summary>Read dependencies as a list</summary>
        <ul>
          {edges.map((edge) => (
            <li key={`${edge.from}-${edge.to}`}>
              {labels[edge.to]} uses {labels[edge.from].toLowerCase()}.
            </li>
          ))}
        </ul>
      </details>
    </figure>
  );
}
