import json
from ffv2.import_legacy import migrate


def test_import_dry_run_backup_and_idempotency(tmp_path, store):
    legacy = tmp_path / "legacy"
    traces = legacy / "traces"
    traces.mkdir(parents=True)
    data = {"trace_id": "legacy-1", "doc_id": "synthetic", "spans": []}
    (traces / "one.json").write_text(json.dumps(data))
    (traces / "bad.json").write_text("broken")
    report = migrate(legacy, store)
    assert report["corrupt"] == ["bad.json"]
    assert report["orphans"] == ["one.json"]
    assert store.list_runs() == []
    report = migrate(legacy, store, True, tmp_path / "backup")
    assert report["imported"] == 1
    assert store.list_runs()[0]["created_at"] is None
    assert migrate(legacy, store)["duplicates"] == 1
    assert (traces / "one.json").read_text() == json.dumps(data)
