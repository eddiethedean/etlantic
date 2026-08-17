# Example third-party optimization pass (0.45)

Clone-only demo. From the repository root after `uv sync --locked`:

```bash
uv run python -c "
from examples.optimization_pass_echo.pass_impl import EchoOptimizationPass
from etlantic.testing import run_optimizer_conformance_suite
run_optimizer_conformance_suite(EchoOptimizationPass())
print('echo pass conformance ok')
"
```

Pin: `etlantic>=0.47.0,<0.48`.

Register via entry point group `etlantic.optimization_passes` and allowlist
`example.pass.echo` under `Profile.optimization_pass_allowlist` in production.
