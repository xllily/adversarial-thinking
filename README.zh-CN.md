# Adversarial Thinking

[English](README.md) · [Agent 导航](llms.txt)

Adversarial Thinking 是我为 Coding Agent 做的一个实验性 Agent Skill。它只在 Agent 准备确定重要计划、提交评审结论、选择恢复路径或锁定问题框架前运行。

我做它，是因为 Agent 很容易沿着一条看起来合理的路线走得太远。这个 Skill 会要求它提出另一种可信解释，再找出可能改变下一步行动、成本最低的检查。检查结束后，控制权回到原工作流。

当一个决定值得再质疑一次、搜索空间收窄得太早，或连续修复已经和现有证据对不上时，用它。任务风险低且容易回退，或者现有领域方法已经给出答案时，就继续做事，不必额外停下来。

`0.1.0` 仍是实验版本。现有评估不能证明它比默认模型更好。准确的证据边界见[证据说明](#证据说明)。

行为以 [`SKILL.md`](SKILL.md) 为准。这份 README 介绍项目，[`llms.txt`](llms.txt) 帮助 Agent 找到相关文件。它们不会定义另一套工作流。

## 为什么做这个 Skill

Coding Agent 的失败方式经常很相似：过早接受第一个可行方案，评审时为了显得严格而强行找问题，或在因果模型已经失效后继续修补症状。

我想要的是一个足够小的检查点，能打断这些问题，又不会把 Agent 变成长期唱反调的角色。检查强度应该由决策后果、可逆性、不确定性和证据质量决定，而不是由任务有多长决定。

## 如何接入现有流程

这个 Skill 不替换现有工作流，只在上面加一个检查点。它会根据当前任务选择评审、头脑风暴、规划或执行恢复分支。路由规则和各分支要求都在 [`SKILL.md`](SKILL.md#route-by-the-immediate-deliverable) 中。

它不会扩大权限。只读评审仍然只读；仓库文件、Issue、日志和其他材料仍按不可信输入处理；宿主的指令层级与授权规则继续生效。详见 [Authority and composition](SKILL.md#authority-and-composition)。

## 安装

我推荐使用 [Skills CLI](https://github.com/vercel-labs/skills) 完成常规安装。它能从仓库根目录识别 `adversarial-thinking`，支持 Codex、Claude Code 和其他 Agent Skills 宿主。使用前需要安装 Node.js 和 npm。

### 交互式安装

让 CLI 询问目标 Agent 和安装范围：

```sh
npx skills add xllily/adversarial-thinking
```

### Codex

全局安装到 Codex：

```sh
npx skills add xllily/adversarial-thinking --skill adversarial-thinking -g -a codex -y
```

Codex 也提供内置安装器。调用时要明确安装仓库根目录的 Skill：

```text
$skill-installer Install xllily/adversarial-thinking with path "." and name "adversarial-thinking".
```

内置安装器会把 Skill 放到 `$CODEX_HOME/skills/adversarial-thinking`。下一轮对话即可使用。

### Claude Code

全局安装到 Claude Code：

```sh
npx skills add xllily/adversarial-thinking --skill adversarial-thinking -g -a claude-code -y
```

Claude Code 会把它注册为 `/adversarial-thinking`。

### 同时安装到 Codex 和 Claude Code

```sh
npx skills add xllily/adversarial-thinking --skill adversarial-thinking -g -a codex -a claude-code -y
```

## 使用

调用时写明 Skill 名称，并单独指定模式：

```text
$adversarial-thinking 使用 review 模式。评审这个迁移计划，只输出评审结论。
```

```text
$adversarial-thinking 使用 exec 模式。五次修复正在来回震荡。重置因果模型后安全继续。
```

上面的示例使用 Codex 语法。在 Claude Code 中，把 `$adversarial-thinking` 换成 `/adversarial-thinking`。

我没有把各模式注册成独立 Skill。`adversarial-thinking:review` 这类名称无法调用。

## 证据说明

我目前在 [`evals/evals.json`](evals/evals.json) 中公开了 34 条行为规格。第一轮 paired smoke 共记录 18 次新上下文试验，覆盖高风险评审、执行恢复和一个低风险负例。

名义基线和显式加载 Skill 的条件都通过了 9/9，但测试环境中的名义基线仍能发现全局安装的 Skill，因此不能视为无 Skill 基线。这些输出可以作为 smoke 记录，但不能判断这个 Skill 是否造成了退化或增益。

我已经在一个 Codex 环境中验证了 `$adversarial-thinking` 的显式发现和 Review 分支加载。隐式触发、跨模型表现、Token 成本和延迟还没有验证。[评估协议](evals/README.md)与 [2026-08-31 paired smoke 记录](evals/results/2026-08-31-retrospective-ab.md)保留了原始证据和限制。

我把 `0.1.0` 当作实验版本。是否能改善 Agent 行为，还需要隔离正确的对照测试。面对重要的生产决策，也不应该只依赖这一个 Skill。

## 仓库导航

- [`SKILL.md`](SKILL.md)：权威指令与路由契约。
- [`references/`](references)：按任务需要加载的分支说明。
- [`evals/`](evals)：行为规格、评估协议、原始输出与证据边界。
- [`llms.txt`](llms.txt)：供 Agent 使用的导航索引。
- [`CHANGELOG.md`](CHANGELOG.md)：版本记录。

## 贡献

如果修改会影响行为，请补充一个能区分新旧行为的场景，并记录隔离后的无 Skill 基线、启用 Skill 后的输出，以及可获得的宿主和模型信息。

我更愿意根据已经观察到的失败做小范围修正，而不是为假想场景添加宽泛规则。

## 许可证

Apache-2.0。详见 [`LICENSE`](LICENSE)。
