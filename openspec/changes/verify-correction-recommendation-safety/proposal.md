## Why

2026-09-13 的 recommendation-quality 诊断中，当前版在 rq-01 给出了正确迁移顺序；被拒候选虽然正确否定原案，却仍建议在旧读者退役前删除依赖字段。A1 要把“判断对”与“建议可安全执行”分开验证，形成保留当前版或拒绝/采用候选的可信依据，而不是预设核心指令缺陷。

## What Changes

- 在新的 `recommendation_quality_v2` 冻结中复用现有准备、哈希和人工 rubric；旧 `recommendation_quality_v1`、T1 冻结、哈希及历史结果保持不变。
- 将旧 rq-01–rq-04 作为公开开发回归，另准备两组成对的新鲜确认案例：危险迁移与已安全安排的原案；必要最小扩展与证据不足的扩展建议。新案例覆盖前置条件、修正顺序、源事实、观察/未来检查和 review-only 权限。
- 对最终判断、前置条件、修正顺序、源事实忠实度、证据状态、无谓阻断和越权分别记录，不用正确 verdict 抵消危险修正；出现严重危险修正即拒绝候选晋升。
- 先完成零模型调用的可重复准备；只有运行环境、实际加载来源、预算和单独运行授权具备时才执行模型比较。未授权或证据不全时明确交付 `offline-ready` 或 `diagnostic`，不写行为通过。
- 仅在机制和实测支持时形成一个受控候选 patch；当前版已满足同机制时允许保留当前核心。结果归入既有评估证据入口，不新增 runner、评分平台或遥测系统。

## Capabilities

### New Capabilities

- `correction-recommendation-safety`: 用版本化、可追溯的轻量评估验证修正建议安全性与正确保留，并以明确证据和权限边界决定是否采用候选。

### Modified Capabilities

无。当前仓库没有 `openspec/specs/` 中可复用的既有 capability；本提案不改变已发布 Skill 的行为契约或公共接口。

## Impact

- 预计实施范围：`evals/campaigns/recommendation_quality_v2/` 的案例、控制器侧 rubric、准备/冻结材料；复用 `recommendation_quality_v1/prepare.py` 的现有机制，必要时仅作新版本内的窄适配；`evals/reports/` 的对应结果与 `evals/README.md` 证据导航。
- 新版本必须分别固定 Skill 正文、Review 正文与 description 的来源/哈希，不将当前未提交 description 自动归为发布版 v0.1.1；不覆盖既有未提交修改。
- 不增加运行时依赖，不调用真实模型或外部服务，不修改当前 Skill、宿主路由、安装副本或历史冻结；本次仅形成提案。后续模型试验及核心采用均需有独立证据与适用授权。
