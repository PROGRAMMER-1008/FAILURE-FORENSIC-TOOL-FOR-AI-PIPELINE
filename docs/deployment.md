# Local deployment packaging

The Docker image was built locally, verified as uid 10001, and smoke-tested for migration/readiness/restart. No publication or hosting occurred. Do not call this production-ready.

```powershell
docker compose build
docker compose up -d db
docker compose --profile tools run --rm migrate
docker compose up -d frontend api worker
```

The reference compose file is a **local synthetic setup**: API published only on loopback; PostgreSQL has no published port and uses trust auth inside the local compose network. Never reuse that database auth policy for private hosting. Migration is a separate release action. Workers do not race migrations.

For a public read-only demo, prepare a separate synthetic database locally, stop its worker, and set FF_MODE=demo and FF_PROVIDER=fake on its API. Hosting/proxy publication requires owner action. No live progress should be described as recorded-demo playback.

Private Linux VM procedure: configure a maintained OIDC proxy and TLS termination; set FF_MODE=private, exact trusted proxy IPs and one allowed subject; keep API accessible only from that proxy. Replace local PostgreSQL trust authentication with injected credentials and restricted networking. Use encrypted persistent volumes and private backups. Set resource limits for API/parser/worker. Do not forward client-supplied identity headers. The real proxy/identity-provider setup has not been deployed or validated in this session.

Release: backup, verify restore in a disposable DB, build locally, run explicit migration once, start API/worker, check liveness/readiness and synthetic smoke flow. Rollback uses the previous image only if schema-compatible; otherwise restore the verified pre-release backup to a new volume. Never downgrade/drop production tables automatically. No measured RPO/RTO or hosting cost is claimed.
