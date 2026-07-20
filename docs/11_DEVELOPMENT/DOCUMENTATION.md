# Documentation Contributions

Documentation is part of the public API.

## Required Page Status

Every page describing product behavior must be one of:

- **Available in 0.21** (or the first shipped milestone when still current)
- **Experimental**
- **Partially available**
- **Future design**
- **Normative specification**
- **Internal project plan**

Future design must not be described as a complete or runnable current example.

## Local Checks

Documentation-only changes do not require the entire pytest suite. Run the
documentation consistency and strict site-build gates:

```bash
uv run python scripts/check_docs.py
uv run python scripts/build_docs.py
```

`check_docs.py` invokes `check_runnable_docs.py`. Run the full baseline pytest
command from [Testing](TESTING.md) when documentation accompanies a code,
plugin, or executable behavior change.

`scripts/build_docs.py` runs `mkdocs build --strict` and sets
`NO_MKDOCS_2_WARNING=1` so Material's MkDocs 2.0 advisory does not appear
(unrelated to this project's content).

The example test imports and runs `examples/quickstart.py`. Documentation CI
also checks release-version consistency and rejects future-backend claims in
the runnable examples index.

Pages labeled **Status: Available** and presented as runnable must identify a
companion source file in `examples/`. Register the page/source pair in
`scripts/check_runnable_docs.py`; the docs gate verifies that the file exists
and **syntax-compiles** (`py_compile`). Core examples such as
`examples/quickstart.py` also **execute** in CI. Optional-backend companions
are executed in their dependency-group jobs when marked as such—do not claim
every companion is executed by the syntax gate alone.

## Writing Rules

- Lead with the user outcome.
- State prerequisites and expected output.
- Use only shipped APIs in beginner documentation.
- Put proposed APIs in the Future Design section.
- Link to the compatibility matrix rather than duplicating dependency ranges.
- Update the changelog, status page, and navigation when release boundaries
  change.
