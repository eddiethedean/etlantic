# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-07-16

### Added

- First public release as **Pipelantic** (PyPI package `pipelantic`)
- Typed modeling kernel for authoring pipelines without an execution backend
- `Transformation`, `Input`, `Output`, and `Parameter` port annotations
- `Pipeline`, `Source`, `Step`, `Sink`, and subpipeline composition
- Typed `OutputRef` wiring with stable node and port identities
- Structural validation diagnostics (cycles, missing refs, incompatible ports)
- Logical graph inspection and Mermaid diagram generation
- ContractModel integration boundary via `DataContractModel` alias
- uv + ruff toolchain, MkDocs documentation site, shared GitHub Actions
  checks, and tag-triggered PyPI release

[0.1.0]: https://github.com/eddiethedean/pipelantic/releases/tag/v0.1.0
