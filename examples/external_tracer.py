"""A fixed external integration, not arbitrary user-authored executable pipelines."""
from ffv2.db import engine
from ffv2.models import Envelope, PipelineVersion, Run, Step
from ffv2.privacy import fingerprint
from ffv2.settings import Settings
from ffv2.store import Store
from ffv2.tracer import Tracer


def main():
    store=Store(engine(Settings().database_url))
    step=Step(id="normalize",name="Normalize whitespace",dependencies=["document"])
    pipeline=PipelineVersion(id="external-normalize-1",steps=[step])
    run=store.enqueue(Run(source="Synthetic   text",source_hash=fingerprint("Synthetic   text"),pipeline=pipeline),"external-normalize-example")
    claim=store.claim("external-integration")
    if not claim or claim["run_id"] != run.id:
        raise RuntimeError("Use a dedicated empty database for this example")
    run.status="running"
    with Tracer(store,run,claim).step(step,{"document":run.source},"python","whitespace-1") as attempt:
        attempt.result=Envelope(status="succeeded",provider="python",model="whitespace-1",output={"text":" ".join(run.source.split())})
    run.status="succeeded"
    store.checkpoint(run,claim,"succeeded",terminal=True)


if __name__=="__main__":
    main()
