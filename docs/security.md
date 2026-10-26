# Security and privacy

This is not a security certification. Local defaults bind loopback; no wildcard CORS. Private document data may remain in your database, backups and manually exported files even when known secret formats are redacted.

Redaction occurs before persistence and on exports. It covers authorization/bearer tokens and selected credential key patterns, not all personal data. Sanitized raw responses are explicitly marked redacted and are not necessarily byte-identical. No arbitrary code/tools are available to the judge. Context overflow returns an explicit failure rather than pretending truncated input was fully verified.

The document parser checks MIME/signatures, UTF-8, PDF pages and DOCX expansion, and runs in a killable child with a 10-second timeout. This is process isolation, not a complete OS sandbox or hard memory cgroup. Deployment resource limits remain necessary. Do not publish the legacy API in webui/server.py; it remains an unauthenticated historical implementation.

Private mode is single-owner: use a maintained OIDC proxy to authenticate users, strip client identity headers, then supply X-Auth-Request-User. Configure exact trusted proxy peer IPs and the one authorized subject. The API checks the socket peer, not X-Forwarded-For. Block direct API access at the network/firewall; expose only TLS proxy ingress. Keep DB/metrics/Ollama private. Proxy cookies must be Secure, HttpOnly and SameSite, with proxy CSRF protections. Real identity-provider expiry/CSRF flows have not been exercised here.

Run Uvicorn with `--no-proxy-headers` in private mode (the image default) so forwarded client IPs cannot replace the socket peer used by the trust check. `deploy/nginx-private.example.conf` and `deploy/oauth2-proxy.example.cfg` show the auth-request boundary; customize and validate them with a real identity provider before exposure. In this arrangement nginx, not oauth2-proxy, is the configured trusted API peer.

Demo mode rejects all mutations, even if frontend controls are bypassed. Seed only synthetic data into its dedicated database. No arbitrary uploads or live paid inference. Existing committed real-looking legacy traces have unverified provenance and are not copied into v2 demos or images.

Deletion: `uv run python -m ffv2.operations delete-run UUID` requires a terminal run and deletion of child replays first; relational attempts/reviews/events/cases cascade. Frozen dataset references block deletion unless `--include-snapshots` explicitly authorizes deletion of containing snapshots. That privacy deletion path is tested. Uploaded bytes are not retained by v2. Manual exports/backups require separate expiry; immediate deletion from backups is not promised.

`scripts/scan_secrets.py` reports paths/categories only, excludes .env/private data, and is a limited working-tree scanner. It is not a full Git-history secret audit. If the owner finds published credentials, revoke/rotate them; no history rewrite is performed by this project setup.
