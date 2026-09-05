# Dual-write rollout

Keep the old and new fields through the mixed-version window. Start with a 1%
canary, abort on any dual-write gap, and preserve rollback until every legacy
reader is retired.

The credible countermodel is that a deployed legacy worker bypasses dual-write.
