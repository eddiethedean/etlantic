# Migration from 0.49 to 0.50

0.50 freezes the `dtcs.transform-plan/2` baseline with 12 actions, the kernel and relational `/1` profiles, and explicitly proven `/2` metadata aliases. Replan stored 0.49 descriptors before execution; stale evidence is rejected before I/O.

Plugins must repin every first-party optional package to the matching 0.50 line and rerun the public conformance matrix. Engine selection remains in the Profile; native implementation bodies are separate from the portable body and must not be silently substituted.

Rollback: restore the 0.49 package lock and profile, replan stored plans, and discard 0.50 evidence artifacts. Never execute a stored 0.49 plan with a mismatched compiler fingerprint.
