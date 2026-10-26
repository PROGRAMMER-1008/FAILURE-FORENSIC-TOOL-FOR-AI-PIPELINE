export const stepName = (id: string) =>
  ({
    extract: "Fact extraction",
    classify: "Document classification",
    summarize: "Summary",
  })[id] || id;
type Finding = {
  origins: string[];
  symptoms: string[];
  abstention_reason: string | null;
};
export function FindingSummary({
  status,
  finding,
}: {
  status: string;
  finding: Finding | null;
}) {
  const finished = ["succeeded", "failed", "cancelled"].includes(status);
  return (
    <section className="finding-summary" aria-label="Investigation summary">
      <p className="eyebrow">START HERE</p>
      <h2>
        {!finished
          ? "Your document is being processed"
          : finding?.origins.length
            ? "A possible problem needs your review"
            : !finding || finding.abstention_reason
              ? "There is not enough evidence for a conclusion"
              : status === "succeeded"
                ? "No supported problem was identified"
                : "This investigation did not complete successfully"}
      </h2>
      <p>
        {status === "succeeded"
          ? "All processing steps finished. This does not guarantee that their answers are correct."
          : status === "failed"
            ? "At least one processing step failed. Inspect its error before judging the content."
            : status === "cancelled"
              ? "Processing was stopped. Some outputs may be missing."
              : "Completed outputs appear below as the worker records them."}
      </p>
      {finding && (
        <dl className="summary-facts">
          <div>
            <dt>Where the problem may start</dt>
            <dd>
              {finding.origins.map(stepName).join(", ") || "Not established"}
            </dd>
          </div>
          <div>
            <dt>Where it also appears</dt>
            <dd>
              {finding.symptoms.map(stepName).join(", ") ||
                "No downstream error established"}
            </dd>
          </div>
        </dl>
      )}
      <p>
        <strong>Your next step:</strong> Compare the original text with the
        selected output, then record whether you agree. Automated findings are
        suggestions, not proven causes.
      </p>
    </section>
  );
}

export function CorrectionEditor({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  if (!value)
    return (
      <p className="field-help">
        Start by copying the recorded facts below. Then edit the values you have
        checked against the source.
      </p>
    );
  let parsed: {
    entities?: { name: string; value: string; entity_type: string }[];
  };
  try {
    parsed = JSON.parse(value);
  } catch {
    return (
      <p role="alert">
        The advanced JSON is invalid. Fix its syntax or copy the recorded facts
        again.
      </p>
    );
  }
  if (
    !parsed ||
    !Array.isArray(parsed.entities) ||
    !parsed.entities.every(
      (e) => e && typeof e.name === "string" && typeof e.value === "string",
    )
  )
    return (
      <p>
        Use the advanced JSON editor to supply an entities array with name,
        value and entity_type fields.
      </p>
    );
  if (!parsed.entities.length)
    return (
      <p>
        No facts were extracted. Use the advanced JSON editor to add a missing
        fact.
      </p>
    );
  return (
    <div className="correction-fields">
      {parsed.entities.map((entity, index) => (
        <label key={index}>
          Corrected value {index + 1}{" "}
          <span className="field-help">
            {entity.name} · {entity.entity_type}
          </span>
          <input
            value={entity.value}
            onChange={(event) => {
              const entities = parsed.entities!.map((item, i) =>
                i === index ? { ...item, value: event.target.value } : item,
              );
              onChange(JSON.stringify({ ...parsed, entities }, null, 2));
            }}
          />
        </label>
      ))}
    </div>
  );
}
