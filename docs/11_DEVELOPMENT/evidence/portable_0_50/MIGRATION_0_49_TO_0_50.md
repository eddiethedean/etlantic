# Migration from 0.49 to 0.50

Revalidate stored plans against `etlantic.portable-baseline/1` before running.
Install optional engine packages in lockstep, and treat missing requirement
evidence as a planning failure. Native implementation bodies remain explicit
escape hatches; no implicit fallback is performed.

The checked-in 0.50 evidence index is currently `blocked`/`no-go`; consumers
must not infer baseline qualification from individual engine tests. Re-run the
seven-engine qualification workflow and regenerate the indexed artifacts before
promoting a stored plan or changing an engine's advertised claim surface.
