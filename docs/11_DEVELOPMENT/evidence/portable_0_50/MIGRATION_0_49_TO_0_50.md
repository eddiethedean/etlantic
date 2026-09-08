# Migration from 0.49 to 0.50

Revalidate stored plans against `etlantic.portable-baseline/1` before running.
Install optional engine packages in lockstep, and treat missing requirement
evidence as a planning failure. Native implementation bodies remain explicit
escape hatches; no implicit fallback is performed.
