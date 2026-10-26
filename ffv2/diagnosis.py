"""Evidence-gated graph diagnosis. Suspected origins are hypotheses, never proof."""

import json

from ffv2.models import Finding, Judgment, Run
from ffv2.providers import Provider


def judge_input(source: str, inputs: dict, output: dict) -> dict:
    def strip(value):
        if isinstance(value, dict):
            return {k: strip(v) for k, v in value.items() if k not in {"confidence", "reasoning"}}
        if isinstance(value, list):
            return [strip(v) for v in value]
        return value

    return {"source": source, "inputs": strip(inputs), "output": strip(output)}


def assess(provider: Provider, source: str, inputs: dict, output: dict, budget: int) -> Judgment:
    data = judge_input(source, inputs, output)
    unavailable = Judgment(
        model=provider.model,
        status="unavailable",
        assessment="inconclusive",
        uncertainty="Judge unavailable or invalid; pipeline quality is unknown",
    )
    if len(json.dumps(data)) > budget:
        unavailable.uncertainty = "Judge context budget exceeded; no truncation performed"
        return unavailable
    try:
        raw, _ = provider.generate("judge", dict(data, schema=Judgment.model_json_schema()))
        judgment = Judgment.model_validate_json(raw)
        judgment.model = provider.model
        if any(not valid_citation(c, source) for issue in judgment.issues for c in issue.citations):
            judgment.status = "invalid"
            judgment.assessment = "inconclusive"
            judgment.uncertainty = "Citation validation failed"
        return judgment
    except Exception:
        return unavailable


def valid_citation(citation, source: str) -> bool:
    return (
        citation.source_id == "document"
        and citation.end > citation.start
        and source[citation.start : citation.end] == citation.quote
    )


def descendants(run: Run, step_id: str) -> set[str]:
    found: set[str] = set()
    for step in run.pipeline.steps:
        if step_id in step.dependencies or found.intersection(step.dependencies):
            found.add(step.id)
    return found


def analyze(run: Run) -> Finding:
    finding = Finding()
    latest = {a.step_id: a for a in run.attempts}
    uncertain = []
    supported: dict = {}
    for step in run.pipeline.steps:
        attempt = latest.get(step.id)
        if attempt is None:
            uncertain.append(f"{step.id}: no completed attempt")
            continue
        if attempt.result.status == "failed":
            finding.origins.append(step.id)
            finding.evidence.append({"step_id": step.id, "technical_error": attempt.result.error})
            continue
        if attempt.result.status == "skipped":
            continue
        j = attempt.judgment
        if j is None or j.status != "assessed" or j.assessment == "inconclusive":
            uncertain.append(f"{step.id}: missing or inconclusive judgment")
            continue
        if j.assessment == "acceptable":
            if j.issues or j.source_correct is False:
                uncertain.append(f"{step.id}: contradictory assessment")
            continue
        valid_issues = [
            i
            for i in j.issues
            if i.citations and all(valid_citation(c, run.source) for c in i.citations)
        ]
        if not valid_issues or j.source_correct is not False:
            uncertain.append(
                f"{step.id}: allegation lacks verified evidence or contradicts assessment"
            )
            continue
        supported[step.id] = valid_issues
        propagated = j.input_faithful is True and all(
            issue.inherited_from
            and all(
                parent in supported and step.id in descendants(run, parent)
                for parent in issue.inherited_from
            )
            for issue in valid_issues
        )
        if propagated:
            finding.symptoms.append(step.id)
        elif j.input_faithful is False:
            finding.origins.append(step.id)
        else:
            uncertain.append(f"{step.id}: propagation versus new error unresolved")
        finding.evidence.extend(
            {"step_id": step.id, **i.model_dump(mode="json")} for i in valid_issues
        )
    finding.potentially_affected = sorted(
        set().union(*(descendants(run, s) for s in finding.origins)) - set(finding.origins)
    )
    finding.alternatives = uncertain
    if uncertain:
        finding.abstention_reason = "; ".join(uncertain)
    elif not finding.origins and not finding.symptoms:
        finding.label = "No supported issue found; judge correctness is not guaranteed"
    return finding
