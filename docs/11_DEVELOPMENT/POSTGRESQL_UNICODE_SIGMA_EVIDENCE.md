---
title: PostgreSQL Unicode Sigma Evidence
description: Reproducible PostgreSQL 16 arm64 evidence for Unicode final-sigma parity.
status: verified
---

# PostgreSQL Unicode Sigma Evidence

Issue [#127](https://github.com/eddiethedean/etlantic/issues/127) tracked a
portable `dtcs:lower` mismatch on PostgreSQL 16 arm64 when the compiler lowered
each code point without retaining the surrounding sigma context.

The PostgreSQL compiler now derives final-sigma context from Unicode data known
at compile time. It does not use PostgreSQL's locale-sensitive `UPPER` or
`LOWER` functions to classify neighboring characters. The runtime still uses
PostgreSQL for execution, so the same compiled plan is exercised across
collations and architectures.

## Arm64 verification

The issue reproduction was verified on 2026-09-12 with the official
`postgres:16` arm64 image:

| Property | Observed value |
| --- | --- |
| PostgreSQL | 16.14 on `aarch64-unknown-linux-gnu` |
| Architecture | arm64 host and PostgreSQL server |
| Database encoding | UTF8 |
| Database collation | `en_US.utf8` |
| Database ctype | `en_US.utf8` |
| Locale provider | `c` |

The focused PostgreSQL release-blocker tests passed with:

```bash
ETLANTIC_SQL_URL='postgresql+psycopg://postgres:postgres@127.0.0.1:55432/etlantic' \
  uv run pytest -q tests/portable_conformance/test_review_blockers.py -m sql
```

The result was `10 passed, 1 skipped, 6 deselected`. The full SQL and portable SQL
suites also passed with `51 passed, 1 skipped, 165 deselected`.

The regression corpus covers non-final and final sigma, word boundaries,
case-ignorable punctuation, and combining marks. Examples include:

| Input | Expected `dtcs:lower` |
| --- | --- |
| `A-Σ` | `a-σ` |
| `AΣ-B` | `aς-b` |
| `AΣ:B` | `aσ:b` |
| `A'Σ` | `a'ς` |
| `AΣ'B` | `aσ'b` |

The dedicated CI evidence step prints both the runner and PostgreSQL server
architectures, plus the server version, encoding, locale, and locale provider.
The assertions keep the proof bound to PostgreSQL 16 and a valid UTF-8 database
environment.
