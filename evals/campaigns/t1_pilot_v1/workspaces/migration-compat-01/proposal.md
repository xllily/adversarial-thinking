# Account identifier migration

The proposal deploys the new writer, backfills `legacy_email`, removes
`account_uuid`, and deploys readers in the same maintenance window. It assumes
all deployed workers read `legacy_email` after the writer deploys.

The pending decision is whether this plan is ready to approve.
