# Environment Variables (future design)

!!! warning "Future design — most names are proposed 0.37"
    Do **not** treat this page as the 0.36 configuration contract.

    **Shipped today:**

    - [Configuration today](CONFIGURATION_TODAY.md) — env vars the core and
      reference plugins actually read
    - [Runtime configuration](RUNTIME_CONFIGURATION.md) — `ETLANTIC_SQL_URL`,
      Spark test switches
    - [Secrets decision tree](SECRETS_DECISION.md) — how `SecretRef` maps to
      environment variables

ETLantic loads an optional project `etlantic.toml` for `default_profile` but
does **not** auto-read `ETLANTIC_PROFILE`, `ETLANTIC_CONFIG`,
`ETLANTIC_PROJECT`, logging overrides, or output-format overrides in 0.36.

Proposed 0.37 variable names remain out of this page so they are not mistaken
for a shipped contract.
