# Agent Data 质量审核工具

## 项目背景

本项目用于完成「Agent 评测任务包质量审核（Agent Evaluation Task Package Quality Audit）」笔试题。招聘方提供了一份 Agent 评测任务包 `restaurant-portfolio-traffic-change-audit/`，包含：

- 被测 Agent 的任务说明（`instruction.md`）
- 源数据台账（`materials/门店餐段客流台账.xlsx`）
- Gold 标准答案（`gold/expected_answer.xlsx`）
- 5 份真实 Agent 输出（`rollouts/`）及当前评分
- 3 份受控对抗样本（`probes/`）
- 当前评分规则与评分器说明/源码（`rubric/`、`scorer/`）
- 答卷模板（`answer-template.md`）

## 项目目标

对这份评测任务包进行全面质量审核，回答五个问题：

1. 任务是否可行？能否从源台账独立复算出事实基线？
2. 5 份 rollout 的实际质量如何？当前评分是否合理？
3. 3 个 probe 的缺陷是什么？当前规则会如何误判？
4. 当前评分系统（rubric + scorer）有哪些公平性、可靠性问题？如何重构？
5. 任务包与评分器能否验收？最小修复方案和回归测试是什么？

最终交付物是按 `answer-template.md` 生成的 `answer.md`。

## 技术栈

| 技术 | 用途 |
|---|---|
| Python | 主开发语言 |
| Pandas | 数据读取与统计 |
| OpenPyXL | Excel 解析、公式和单元格追溯 |
| Pydantic | 数据模型与数据校验 |
| SQLite | 结构化数据持久化与来源追溯 |
| JSON | 数据快照、事实基线与审计结果 |
| Pytest | 自动化测试 |

原则：Code First，优先用确定性代码完成解析、计算与核验；AI 只负责辅助分析和语义判断，不代替关键事实核验。

## 目录结构

```text
AgentData/
├── README.md                 # 本文件：项目入口说明
├── AGENT.md                  # AI 开发行为规范
├── docs/
│   ├── DEVELOPMENT_PLAN.md   # 六阶段开发计划与进度管理
│   └── reports/              # 各阶段报告（每阶段一份）
├── restaurant-portfolio-traffic-change-audit/   # 招聘方原始考试包（只读，不得修改）
│   ├── instruction.md
│   ├── materials/
│   ├── gold/
│   ├── rollouts/
│   ├── probes/
│   ├── rubric/
│   ├── scorer/
│   └── answer-template.md
├── data/                     # （待实现）JSON 快照与 SQLite 数据库
├── src/                      # （待实现）解析、计算、审计代码
└── tests/                    # （待实现）自动化测试
```

> `data/`、`src/`、`tests/` 为规划目录，随阶段二及之后创建；原始考试包保持只读。

## 环境准备

```bash
pip install pandas openpyxl pydantic pytest
```

SQLite 为 Python 标准库自带，无需额外安装。

## 各阶段运行方式

> 以下命令为规划内容，具体入口脚本在对应阶段实现后补充：

- 阶段二（事实基线）：解析台账、建立基线、校验 Gold —— 待实现
- 阶段三（Rollout 审计）：逐份提取 rollout 证据并与基线对照 —— 待实现
- 阶段四（Probe 与 Scorer 审计）：分析 probe 缺陷、审查评分器行为 —— 待实现
- 阶段五（Rubric 与回归测试）：新评分标准设计与回归测试用例 —— 待实现
- 阶段六（综合验收）：汇总证据，生成 `answer.md` —— 待实现

**阶段门禁机制**：阶段之间由人工验收控制，每阶段完成后须批准才能进入下一阶段。

**例外——阶段二采用节点质量门禁**：阶段二拆分为 6 个顺序节点（材料盘点与口径 → 数据模型 → 解析与 JSON 标准化 → SQLite 存储 → 事实基线 → 质量校验与阶段验收）。节点验收通过则自动流转到下一节点；不通过则立即中断整个阶段二并汇报失败原因与修复建议；六个节点全部通过后才停止并等待人工批准进入阶段三。各节点验收标准见 `docs/DEVELOPMENT_PLAN.md`。

## 当前开发进度

- [x] 阶段一：项目开发文档建设（README、DEVELOPMENT_PLAN、AGENT）—— 已完成
- [x] 阶段二：材料结构化与事实基线（6 节点自动顺序执行，全部通过；SQL 表人工校验通过）—— 事实基线等待人工验收
- [ ] 阶段三：5 份 Rollout 审计 —— 待开始
- [ ] 阶段四：Probe 与 Scorer 审计 —— 待开始
- [ ] 阶段五：新 Rubric 与回归测试设计 —— 待开始
- [ ] 阶段六：综合验收与答卷生成 —— 待开始

## 交付物说明

| 交付物 | 说明 | 状态 |
|---|---|---|
| README.md | 项目说明（本文件） | 已完成 |
| DEVELOPMENT_PLAN.md | 六阶段进度计划 | 已完成 |
| AGENT.md | AI 开发行为规范 | 已完成 |
| 事实基线（JSON + SQLite） | 阶段二交付 | 已完成（data/fact_baseline.json、data/audit.db） |
| Rollout 审计证据记录 | 阶段三交付 | 待实现 |
| Probe 与评分器诊断 | 阶段四交付 | 待实现 |
| 新 Rubric 与回归测试 | 阶段五交付 | 待实现 |
| answer.md | 最终审核答卷 | 待实现 |
