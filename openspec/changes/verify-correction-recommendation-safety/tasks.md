## 1. 固定范围与输入

- [ ] 1.1 记录 `recommendation_quality_v1`、T1、历史结果与当前 dirty Skill 的字节哈希基线；确认旧 rq-01 current 正确、候选危险、其余六单元未运行，选定新冻结的确切正文/description 来源。
- [ ] 1.2 结合已有完整输出写明 A1 的失败机制与采用判据；只在不同且有依据的机制成立时准备一个受控最小 patch，否则选择 current-only 并记录候选缺席；不改现行核心。

## 2. 新版本案例与冻结

- [ ] 2.1 在 `evals/campaigns/recommendation_quality_v2/` 中将旧四题标为开发回归，新增迁移危险/安全与必要扩展/证据不足两对四题；给出结构差异和暴露记录，把 source fidelity、观察/未来检查及 review-only artifact 冲突验收写入同组案例。
- [ ] 2.2 沿用人工 rubric，为 verdict、前提、顺序、源事实、证据状态、无谓阻断、权限分别给出可判定的 gold 与反例；明确危险纠正/越权拒绝晋升、unknown/不适用和语义早停，不引入新评分平台或总分。
- [ ] 2.3 冻结案例、rubric、精确指令及来源/哈希、可选 candidate patch、condition mapping 与物化规则，生成材料 manifest digest；新鲜确认题在候选设计后冻结，gold 与映射仅留 controller；后续材料变更（含 current-only 后补 candidate）另开冻结版本，不回填后续运行信息。

## 3. 零模型调用的准备与验收

- [ ] 3.1 仅在 v2 内窄适配现有 prepare 的 case IDs、条件组装和来源记录，复用临时 patch/精确 prompt/hash 机制；拒绝覆盖输出、base 漂移和 gold 泄漏，不新增 runner 或改 T0 schema。
- [ ] 3.2 在两个全新目录重复物化并比较 prompt/source/manifest 的有效内容与哈希；定向检查 case/gold 对应、current-only、有候选时 patch 校验及 gold/映射未进入目标提示；对比旧冻结和既有 dirty source 哈希未变。
- [ ] 3.3 编写 v2 README 的复现命令与限制，记录 `offline-ready`、零模型调用和后续运行门槛；该状态只证明准备材料有效，不标行为已通过。

## 4. 真实行为试验（条件任务，需单独运行授权）

- [ ] 4.1 仅在准备验收后，确认可用执行路径、完整输出/实际工具记录/加载来源获取方式；取得适用授权，将宿主、模型/effort/config、执行顺序/重复数/停止规则及调用/费用预算保存为绑定材料 manifest digest 的不可变运行说明，随现有运行产物保存，不回填材料冻结、prompt 或 manifest；profile 若改变实际提示/比较条件，先形成新材料冻结。未知值明确标记；条件不足时停在 offline-ready，不启动模型或扩建 runner。
- [ ] 4.2 仅在 4.1 门槛全部满足后，按冻结顺序执行开发回归与新鲜确认单元，逐单元保留完整输出、实际配置/加载和 usage 可见值；按规则停止、保留失败/未运行状态，不自动重试或修改参数刷结果。
- [ ] 4.3 对满足记录边界的完整输出执行去条件标识的人工分项评分，保留引文、case/gold 依据和暴露记录；无法盲评则降级非盲诊断，未满足既有契约不送 T0、不伪造 receipt 或 usage。
- [ ] 4.4 根据分项证据拒绝危险/越权候选或记录保留当前版；有候选时给出仅针对当前冻结的采用建议，无候选不声称增益；不应用 patch，不改现行核心。

## 5. 交付与范围核对

- [ ] 5.1 在现有 `evals/README.md` 证据入口链接 v2：仅离线完成时声明准备状态；获准运行后才在 `evals/reports/` 记录对应真实结果、逐单元状态、限制、未知成本与采用建议，保留历史报告。
- [ ] 5.2 检查本 change 的实施增量仅含 v2 与对应证据导航/结果；既有 dirty source 和本 change 规划文件不属于待清理越界内容，不回滚或覆盖他人改动；重核旧冻结、现行 Skill/Review、既有未提交 description 及安装副本未被本次实施修改。任务 4 未获准/未运行时保持未完成并标明条件，不能将全 change 写为行为验收通过。
