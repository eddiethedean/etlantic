# Contributing

Pipelantic welcomes contributions to documentation, typed authoring APIs,
validation, planning, plugins, tests, and examples.

Preserve the boundaries established in the manifesto and foundations
documentation: Pipelantic owns the logical model; plugins own execution;
standards own semantics.

## Before You Start

Read:

- [Manifesto](../PIPELANTIC_MANIFESTO.md)
- [Design Principles](../02_FOUNDATIONS/DESIGN_PRINCIPLES.md)
- [Architecture](../02_FOUNDATIONS/ARCHITECTURE.md)
- [Design Decisions](DESIGN_DECISIONS.md)

## Scope Test

Ask:

1. Does this concern portable modeling, validation, or planning?
2. Is it execution behavior that belongs in a plugin?
3. Is it data-contract operational behavior that belongs in ContractModel?
4. Is it contract meaning that belongs in ODCS, DTCS, or DPCS?

Pipelantic owns the logical model. Plugins own execution. Standards own
semantics.

## Development Setup

```bash
git clone https://github.com/eddiethedean/pipelantic.git
cd pipelantic
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mkdocs build --strict
```

`uv sync` installs runtime dependencies, the editable package, and the `dev`
group (pytest, ruff, mkdocs). See [Installation](../01_GETTING_STARTED/INSTALLATION.md)
for more detail.

Use the supported Python versions documented in `pyproject.toml`.

## Making a Change

1. Open or identify an issue.
2. Confirm the architectural owner of the feature.
3. Add an ADR for difficult-to-reverse architectural changes.
4. Add tests before or with implementation.
5. Update affected documentation.
6. Add a changelog fragment when required.
7. Run local quality checks.

## Pull Requests

Pull requests should include:

- Problem statement
- Proposed behavior
- Public API impact
- Contract or plugin compatibility impact
- Tests
- Documentation changes
- Performance or security considerations

Keep pull requests focused. Separate unrelated refactoring from behavior
changes.

## Public API Changes

Changes to root imports, authoring syntax, plugin protocols, `PipelinePlan`, or
generated contract meaning require extra review.

Before adding a public abstraction, demonstrate at least two concrete consumers
or one complete end-to-end workflow that needs it.

## Documentation Contributions

Documentation should:

- Lead with the user outcome
- Use consistent terms from the glossary
- Distinguish proposed APIs from implemented APIs
- Link to normative standards instead of duplicating them
- Include executable examples where possible
- Avoid claiming that Pipelantic executes work owned by plugins

## Plugin Contributions

Core plugins should:

- Depend only on public SDK interfaces
- Declare accurate capabilities
- Pass conformance tests
- Normalize diagnostics and failures
- Avoid importing heavy dependencies until needed
- Document supported backend versions

Third-party plugins may be maintained independently and distributed through
Python package entry points.

## Testing

Run the narrowest relevant tests during development and the full suite before
submission.

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

Commands are provisional until the implementation toolchain is committed.

## Commit Messages

Use concise, imperative summaries:

```text
Add typed multi-output step model
Validate SQL dialect capabilities during planning
Document plugin cancellation semantics
```

## Code of Conduct

Be respectful, specific, and constructive. Review the work rather than the
person. Assume good intent while asking for evidence on correctness,
compatibility, and architecture.

## Security Issues

Do not report credential leaks, arbitrary code execution, unsafe reference
resolution, or other vulnerabilities through a public issue. Follow the
repository security policy.

