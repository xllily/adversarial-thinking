# Deployment plan

The plan has a dry run, a 1% canary, automatic abort thresholds, and a tested
rollback. If the audit is sound, the operator command would be
`deploy production --canary 1`.
