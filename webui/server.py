"""
Thin API layer over the existing storage + analysis modules.
No pipeline logic lives here - this purely exposes what
pipeline/storage.py and analysis/root_cause.py already produce,
as JSON, for the web frontend to render. The one exception is
/api/analyze, which runs a NEW document through the live pipeline.

Run from project root:
    uvicorn webui.server:app --reload --port 8000

Then open http://localhost:8000 in a browser.
"""

import sys
import os
import tempfile
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from pipeline.storage import list_traces, load_trace, load_eval_dataset, save_trace
from pipeline.traced_pipeline import run_traced_pipeline
from pipeline.file_extraction import extract_text_from_file, UnsupportedFileType
from analysis.root_cause import analyze_trace
from analysis.judge import judge_all_spans

app = FastAPI(title="Failure Forensics API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _span_to_dict(span):
    return {
        "step_name": span.step_name,
        "input_summary": span.input_summary,
        "output_summary": span.output_summary,
        "confidence": span.confidence,
        "latency_seconds": round(span.latency_seconds, 2),
        "success": span.success,
        "judge_score": span.judge_score,
        "judge_reasoning": span.judge_reasoning,
    }


def _finding_to_dict(finding):
    return {
        "root_cause_step": finding.root_cause_step,
        "category": finding.category.value,
        "evidence": finding.evidence,
        "confidence_in_diagnosis": finding.confidence_in_diagnosis,
        "downstream_steps_affected": finding.downstream_steps_affected,
    }


@app.get("/api/traces")
def get_traces():
    """List all traces with their diagnosis (if judged)."""
    rows = list_traces()
    result = []
    for row in rows:
        trace = load_trace(row["trace_id"])
        has_judge_data = any(s.judge_score is not None for s in trace.spans)
        finding = analyze_trace(trace) if has_judge_data else None
        result.append({
            "trace_id": trace.trace_id,
            "doc_id": trace.doc_id,
            "status": trace.status.value,
            "flagged_bad": trace.flagged_bad,
            "has_judge_data": has_judge_data,
            "finding": _finding_to_dict(finding) if finding else None,
        })
    return result


@app.get("/api/traces/{trace_id}")
def get_trace_detail(trace_id: str):
    """Full detail for one trace: all spans, raw document, diagnosis."""
    trace = load_trace(trace_id)
    has_judge_data = any(s.judge_score is not None for s in trace.spans)
    finding = analyze_trace(trace) if has_judge_data else None

    return {
        "trace_id": trace.trace_id,
        "doc_id": trace.doc_id,
        "status": trace.status.value,
        "flagged_bad": trace.flagged_bad,
        "raw_document_text": trace.final_output.raw_document.raw_text if trace.final_output else "",
        "spans": [_span_to_dict(s) for s in trace.spans],
        "finding": _finding_to_dict(finding) if finding else None,
    }


@app.get("/api/eval-dataset")
def get_eval_dataset():
    """The growing, human-confirmed eval dataset."""
    cases = load_eval_dataset(ground_truth_only=True)
    return cases


@app.post("/api/traces/{trace_id}/review")
def submit_review(trace_id: str, review: dict):
    """
    Records a human's verdict on a trace's diagnosis - confirming,
    correcting, or marking it unclear. This is the same feedback-loop
    logic review_traces.py already used from the command line; this
    endpoint just makes it reachable from the web UI.
    """
    import uuid
    from datetime import datetime, timezone
    from pipeline.models import EvalCase, ReviewVerdict
    from pipeline.storage import save_eval_case, mark_trace_flagged

    trace = load_trace(trace_id)
    finding = analyze_trace(trace)

    if finding.root_cause_step is None:
        raise HTTPException(status_code=400, detail="This trace has no root cause finding to review.")

    verdict_str = review.get("verdict")
    if verdict_str not in ("confirmed", "corrected", "unclear"):
        raise HTTPException(status_code=400, detail="verdict must be 'confirmed', 'corrected', or 'unclear'.")

    failing_step = finding.root_cause_step
    bad_output = next((s.output_summary for s in trace.spans if s.step_name == failing_step), "")

    category = review.get("category") or finding.category.value
    correct_output = review.get("correct_output", "")
    notes = review.get("notes", "")

    case = EvalCase(
        eval_case_id=str(uuid.uuid4()),
        source_trace_id=trace.trace_id,
        doc_id=trace.doc_id,
        original_input_text=trace.final_output.raw_document.raw_text if trace.final_output else "",
        failing_step=failing_step,
        bad_output=bad_output,
        correct_output=correct_output,
        failure_category=category,
        verdict=ReviewVerdict(verdict_str),
        reviewer_notes=notes,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    save_eval_case(case)
    mark_trace_flagged(trace_id)

    return {"status": "saved", "eval_case_id": case.eval_case_id}


@app.get("/api/stats")
def get_stats():
    """Summary numbers for the overview page."""
    rows = list_traces()
    traces = [load_trace(r["trace_id"]) for r in rows]
    judged = [t for t in traces if any(s.judge_score is not None for s in t.spans)]
    findings = [analyze_trace(t) for t in judged]
    flagged = [f for f in findings if f.root_cause_step is not None]
    ground_truth = load_eval_dataset(ground_truth_only=True)

    return {
        "traces_recorded": len(traces),
        "reviewed_by_judge": len(judged),
        "root_causes_found": len(flagged),
        "confirmed_eval_cases": len(ground_truth),
    }


@app.post("/api/analyze")
async def analyze_document(file: UploadFile = File(...)):
    """
    Accepts an uploaded file, extracts its text, runs it through the
    REAL pipeline (extraction -> classification -> summarization),
    judges every span, saves the trace, and returns full detail -
    the same shape as GET /api/traces/{trace_id}.

    This calls the actual Ollama-backed pipeline synchronously, so it
    will take roughly as long as running test_judge.py on one document
    (several LLM calls in sequence). The frontend shows a simulated
    step-by-step progress indicator while this request is in flight,
    since a single POST response doesn't give us true incremental
    streaming without a lot of extra plumbing (websockets/SSE) - noted
    here plainly rather than implying this is literal live streaming.
    """
    allowed_extensions = {".txt", ".pdf", ".docx"}
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail=f"Unsupported file type '{ext}'. Use .txt, .pdf, or .docx.")

    # Save the upload to a temp file so our extraction functions (which
    # expect a file path, matching how they'd be used outside the API
    # too) can read it.
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        raw_text = extract_text_from_file(tmp_path)
    except UnsupportedFileType as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        # e.g. scanned PDF with no extractable text - a real, expected failure mode
        raise HTTPException(status_code=422, detail=str(e))
    finally:
        os.unlink(tmp_path)  # clean up the temp file regardless of outcome

    if not raw_text.strip():
        raise HTTPException(status_code=422, detail="No text could be extracted from this file.")

    doc_id = os.path.splitext(file.filename)[0]

    # Run the actual pipeline - this is the same function test_judge.py
    # and test_traced_pipeline.py use, just triggered from an upload
    # instead of a hardcoded sample string.
    trace = run_traced_pipeline(doc_id, raw_text)
    trace.spans = judge_all_spans(trace.spans)
    save_trace(trace)

    finding = analyze_trace(trace)

    return {
        "trace_id": trace.trace_id,
        "doc_id": trace.doc_id,
        "status": trace.status.value,
        "flagged_bad": trace.flagged_bad,
        "raw_document_text": trace.final_output.raw_document.raw_text if trace.final_output else "",
        "spans": [_span_to_dict(s) for s in trace.spans],
        "finding": _finding_to_dict(finding),
    }


# Serve the frontend itself
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR), name="assets")


@app.get("/")
def serve_index():
    index_path = os.path.join(os.path.dirname(__file__), "index.html")
    return FileResponse(index_path)


@app.get("/favicon.ico")
def favicon():
    # No favicon asset exists yet - return an empty 204 instead of a
    # noisy 404 in the server logs every time a browser auto-requests it.
    from fastapi import Response
    return Response(status_code=204)