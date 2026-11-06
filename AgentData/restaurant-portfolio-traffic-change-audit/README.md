# Agent Data 质量审计笔试

请从 `question.md` 开始阅读，并使用 `answer-template.md` 组织答案。本题不要求运行模型、重新生成 rollout、编写代码或修改考试包。

## 文件说明

- `instruction.md`：被测 Agent 收到的任务说明；
- `materials/`：被测 Agent 可见的源台账；
- `gold/expected_answer.xlsx`：当前 Gold，需要与材料相互核验；
- `rollouts/`：5 份真实 Agent 输出及当前评分；
- `probes/`：3 份受控对抗样本，不属于历史 rollout；
- `rubric/current_rubric.md`：当前公开评分规则；
- `scorer/scorer_behavior.md`：当前评分路径的代码无关说明；
- `scorer/` 中的其他文件：可选的源码交叉验证材料；
- `answer-template.md`：推荐答题结构。

## 提交要求

提交一份 `answer.md` 或 PDF。可以使用 AI、脚本或表格工具辅助，但须说明使用方式以及本人独立复核的关键事实。没有最低字数要求，篇幅和格式本身不产生分数。
