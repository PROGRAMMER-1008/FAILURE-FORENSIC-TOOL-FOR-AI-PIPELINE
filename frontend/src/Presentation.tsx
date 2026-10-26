type Json = Record<string, unknown>;

export function OutputView({ value }: { value: unknown }) {
  if (value === null || value === undefined) return <p>No output recorded.</p>;
  if (Array.isArray(value))
    return value.length ? (
      <ul className="output-list">
        {value.map((item, index) => (
          <li key={index}>
            <OutputView value={item} />
          </li>
        ))}
      </ul>
    ) : (
      <p>None recorded.</p>
    );
  if (typeof value === "object")
    return (
      <dl className="output-fields">
        {Object.entries(value as Json).map(([key, item]) => (
          <div key={key}>
            <dt>{key.replaceAll("_", " ")}</dt>
            <dd>
              <OutputView value={item} />
            </dd>
          </div>
        ))}
      </dl>
    );
  return <span className="output-value">{String(value)}</span>;
}

export function WorkflowGuide() {
  return (
    <section className="workflow-guide" aria-label="How to investigate">
      <div>
        <p className="eyebrow">YOUR FIRST INVESTIGATION</p>
        <h2>From document to a verified finding</h2>
        <p>
          Start with the invented invoice. Follow the evidence, then decide
          whether the diagnosis holds up.
        </p>
      </div>
      <ol className="guide-grid">
        <li>
          <span className="guide-number">01</span>
          <h3>Run a document</h3>
          <p>Extract facts, classify the document and generate a summary.</p>
          <a href="#new">Choose a source →</a>
        </li>
        <li>
          <span className="guide-number">02</span>
          <h3>Inspect the evidence</h3>
          <p>
            Compare the source with each output. An origin is a suspected
            starting point; a symptom is a later observed error.
          </p>
        </li>
        <li>
          <span className="guide-number">03</span>
          <h3>Review and test</h3>
          <p>
            Record your judgment. Edit an output and replay dependent steps to
            test a possible correction.
          </p>
        </li>
      </ol>
    </section>
  );
}
