# Fit Check API

The API owns metadata, provider keys, image workflows, and provenance. It runs
without cloud credentials in `PROVIDER_MODE=mock` and writes demo media plus a
canonical provenance manifest to `LOCAL_MEDIA_ROOT`.

For local development from the repository root:

```bash
cp .env.example .env
make install
make dev-api
```

See the root [README](../../README.md) for the complete setup and the GMI/B2
activation checklist.

