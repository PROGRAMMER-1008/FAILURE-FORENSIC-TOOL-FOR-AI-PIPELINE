# Legacy migration

Legacy JSON and SQLite remain untouched by v2. Do not run the old UI against v2 storage.
Apply the new schema first: `uv run alembic upgrade head`.

```powershell
uv run python -m ffv2.import_legacy data
uv run python -m ffv2.import_legacy data --apply --backup backups/legacy-before-v2
```

Dry run reports corrupt files, JSON orphans, missing JSON, duplicates and changed originals.
Apply requires a new backup directory outside source data. IDs are stable UUID5 mappings;
re-import skips unchanged records and reports changed originals rather than overwriting them.
Known timestamps are preserved; unknown timestamps stay null. Legacy reconstructed responses
are not presented as literal provider responses. Legacy judge scores do not become v2 judgments.
Stop the legacy writer before backup/import. SQLite backup uses the backup API.

Rollback: stop v2 processes and launch the legacy application with the preserved original data.
Do not downgrade the v2 schema destructively. Retain the backup under your private retention policy.
History remains unchanged; previously committed private content needs owner review before publication.

Legacy evaluation cases are also imported with stable IDs and original timestamps/outputs.
Their historical verdict is preserved as `legacy_unverified`, because old data lacks a v2
reviewer/target revision. They cannot enter scored snapshots until re-reviewed. Corrupt,
orphan and changed evaluation cases are reported without their document contents.
