# px4-reqcheck

Reproducible telemetry validation pipeline for evaluating PX4 flight logs against machine-readable requirements.

> Status: implementation phase Week 0. No measured results are published yet.

This project uses only public PX4 logs and synthetic fixtures. It contains no employer data.

## Development

```bash
uv sync --all-groups
make test
```

The final pipeline and claims will be documented only after their reproduction gates pass.
