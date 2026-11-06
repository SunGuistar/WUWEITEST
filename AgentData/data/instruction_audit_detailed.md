# 专项审查报告：Instruction 是否足以形成公平且可验证的 Agent 评测任务

> 审查对象：`restaurant-portfolio-traffic-change-audit/instruction.md` 及其与 materials、Gold、经营规范、solve.py、Rubric、Scorer 的关系。
> 方法：逐项语义审查 + 源码静态分析 + 与阶段二 Independent Baseline / Gold 412 项校验结果（`fact_baseline.json`、`data/audit.db`）交叉印证。
> 所有结论区分：已确认事实 / 推断 / 待确认。

## 1. 执行摘要

**总体结论：有条件通过。**

| 维度 | 结论 | 依据 |
|---|---|---|
| 任务可行性 | 通过 | 台账可支持两期间全部计算，Independent Baseline 已独立复算且 Gold 412 项一致 |
| Instruction 完整性 | 有条件通过 | 任务目标、交付物、结构宽容、不可省略要素明确；但绝对影响公式、零值语义、正式采用定义缺失，靠材料与 Rubric 补全 |
| 业务定义清晰度 | 有条件通过 | 净变化分母、带符号贡献核心口径清晰；状态/影响公式仅在材料口径说明（中文）与 Rubric 中明确，Instruction（英文）未直接给出 |
| 公平性 | 不通过（评测机制层面） | Scorer 未声明维度 R9（公式依赖）与 Rubric"公式或静态值均可"直接冲突；实际结算权重与声明权重不一致；R8/R9 依赖关键词启发式 |
| 可验证性 | 通过 | 全部数值链可程序化验证（program_judge 契约表）；语义结论（最大推动/净抵消）依赖 LLM 语义判定，标记为 Semantic Review |
| 评测有效性 | 有条件通过 | 已知工件走 frozen 回放、未见工件走另一套权重，两条路径可比性差 |

核心判断：**任务本身可执行、结果可客观验证，Instruction 经最小修复即可公平；但当前评分实现（Scorer）存在与 Instruction/Rubric 矛盾的隐含要求，是公平性的主要威胁，且问题不在 Instruction 文本本身。**

## 2. Instruction 需求解析（REQ 清单）

| ID | Instruction 原文位置 | 需求 | 业务含义 |
|---|---|---|---|
| REQ-001 | 第 1 段 "first create an empty deliverable skeleton at /workspace/output/门店客流变化归因说明.xlsx" | 先建空骨架再渐进写入 | 交付过程要求（不影响内容评分） |
| REQ-002 | 第 1 段 "progressively write the analysis in Chinese" | 中文输出 | 语言约束 |
| REQ-003 | 第 1 段 "first provide the brand-wide total conclusion, followed by the store portfolio bridge and daypart contributions" | 每期间：先品牌结论，后组合桥与餐段 | 结论优先结构（与 Rubric R7 一致） |
| REQ-004 | 第 1 段 "Original values, absolute changes, the denominator ..., signed contributions, store status, period, traffic unit, and reconciliation relationships must all be recalculable and traceable to the ledger" | 原值/绝对变化/分母/带符号贡献/状态/期间/单位/勾稽关系可重算且可追溯 | 核心正确性要求 |
| REQ-005 | 第 2 段 "Deliver only this one editable XLSX" | 只交一个可编辑 XLSX | 交付物形式 |
| REQ-006 | 第 2 段 "Sheet names, column names, sheet order, and wide/long table format may differ, but neither comparison period, the three impact categories ..., the three dayparts, all status boundaries, offsetting effects, nor the formally adopted conclusions may be omitted" | 结构可差异；期间/三类影响/三餐段/状态边界/抵消效应/正式采用结论不可省略 | 结构宽容 + 内容下限 |
| REQ-007 | 第 2 段 "The source file is read-only, and no internet access" | 源文件只读、禁网 | 环境约束 |
| REQ-008 | 第 2 段 "Before entering any values, first review the existing operating procedures in the environment" | 录入前先查阅环境中的经营操作规范 | 流程要求；暗指环境存在规范文件 |
| REQ-009 | 【交付提示】"可直接运行 python3 /workspace/solution/solve.py ..." | 提供一键生成脚本 | 辅助提示；暗示脚本存在于环境 |

## 3. 业务指标定义审查

### 3.1 品牌总客流 —— 定义充分（经材料补全）
Instruction 未直接给公式，但 "total brand-wide in-store traffic" + 台账结构（6 店 × 3 餐段，合计行 422/481，见台账客流对比_2024!E22）使唯一合理解释为全部门店各餐段之和。统计范围（全部门店）、单位（千人次，口径说明!B4）、期间（两对相邻年度）均可确认。无重复/遗漏口径。判断：清晰。

### 3.2 品牌净变化 —— 定义充分
方向（本期−基期）由 "changes across consecutive years"、Gold（净增+48/+59）与 Rubric R4 共同锁定；绝对变化与百分比变化均出现在 Gold/Rubric（12.8342%/13.9810%）。基期为零的情形本材料不存在；若发生，增长率需声明不适用（Rubric 未覆盖，属残余风险，低）。判断：清晰。

### 3.3 门店状态 —— 定义在材料中，Instruction 未重申（关键缺口）
三分类唯一定义在台账口径说明!B5（中文）："持续经营指两期均营业；新开门店上期不在经营范围；关闭门店本期不在经营范围"。Instruction 英文术语（continuing / newly opened / closed）与中文口径的映射需 Agent 自行完成。本材料中：
- 零客流 ≠ 无经营：新开基期、关闭本期的 0 是"不在范围"占位（E5/E6 证据：客流对比_2024!F16:F18=0 而 E16:E18=7/34/48）；真实零客流不存在。
- 缺失记录：本材料无缺失；同比对新开/关闭"不适用、留空"（口径说明!B6）——不适用 ≠ 零 ≠ 缺失，三者在本材料中被显式区分。
- 更名/业态变化：不存在；业态字段不参与状态判定。
判断：**数值上无歧义，但 Instruction 未向 Agent 提示占位 0 的语义**，理解偏差会直接错判状态与同比边界（见问题 P5）。

### 3.4 门店绝对影响 —— 公式不在 Instruction 中（关键缺口）
公式仅见于 Rubric R4："The closed-store impact must be the negative of base-period traffic, and the newly opened-store impact must be positive current-period traffic"。Instruction 只要求 "absolute changes" 可追溯。本材料中各公式恰好收敛到同一数值（新开 89−0=89=本期；关闭 0−64=−64=−基期），**结果无多种解释**；但 Agent 若不知道"关闭=−基期"的约定，采用"本期−基期"也得同一答案——数值无歧义、口径依赖 Rubric。判断：结果可验证，定义依赖 Rubric 补全。

### 3.5 净变化分母 —— 定义清晰
Instruction 明确 "the denominator of the brand-wide net change"。全部组合桥与餐段贡献共用该分母（Gold 门店组合桥!F 列、餐段归因!H 列均为 48/59）。误用门店自身/餐段自身作分母即破坏闭合（Gold 控制 Sheet 有断言）。本材料分母非零。判断：清晰。

### 3.6 带符号贡献 —— 核心清晰，范围未提示
贡献 = 绝对影响 / 净变化分母，符号保留（Gold：新开 +185.4167%、关闭 −133.3333%）。贡献之和=1（Gold 控制!D6:F6/D14:F14）。Instruction 未提示结果可超出 0%–100%，Agent 若强行归一化或截断将破坏闭合。净变化为零时贡献不可定义（本材料未发生，Rubric 无规则）。判断：公式清晰，取值范围需经验提示。

### 3.7 餐段贡献 —— 定义充分（经 Gold/Rubric 补全）
早餐/午餐/晚餐范围由台账餐段列唯一确定；餐段增量 = 本期−基期（按餐段全部门店）；三类分量公式同 3.4（按餐段）；闭合：分量之和 = 餐段增量，三餐段增量之和 = 净变化（Gold 餐段归因!K 列闭合差全 0）。必须区分"餐段总增量 / 三分量 / 带符号贡献"三层——Rubric R5 明确禁止以"仅持续门店变化"或"餐段自身同比"冒充品牌贡献。判断：清晰。

### 3.8 抵消效应 —— 语义充分
"offsetting effects" 未定义，但由带符号贡献体系自然支撑：正贡献（新开、持续）与负贡献（关闭、负向餐段）相抵得到净变化。最大正向推动 = argmax(带符号贡献或增量)（晚餐，两期间均成立，Gold 变化归因说明!E2/E9）；净抵消 = 负增量餐段（早餐，期间一）。判断：语义常识 + 数值可验证。

### 3.9 正式采用结论 —— 定义缺失（低中风险）
Instruction 要求不得省略 "the formally adopted conclusions"，但从未定义"正式采用"指什么：人工确认程序？会议决议？单候选原则？环境中不存在任何确认机制（无经营规范、无审批文件）。唯一合理解释：交付工作簿中明确陈述的品牌级结论即为"正式采用"。Gold 用"采用"标记（门店组合桥!I 列）只是展示标记，不代表程序性确认。Agent 间解释可能分化（如有的附加"假设与限制"节，有的只给结论）。Rubric R7 检查结论内容而非采用程序。判断：定义不完整，但按最简合理解释不影响评分；建议修复。

### 3.10 原值与勾稽 —— 定义充分
"recalculable and traceable to the ledger" 未规定追溯粒度；Gold 实现为"来源表 + 来源单元格区间"（原值追溯!K:L），Rubric R2 要求 76 个原值与 门店×业态×餐段×期间×状态×单位 绑定。闭合（组合桥、餐段）为 Gold 控制 Sheet 的硬断言。判断：清晰、可程序化验证。

### 3.11 补充发现：英文 Instruction 与中文材料的语言鸿沟
全部业务口径（状态定义、同比规则、单位）以中文存在于材料中，Instruction 为英文。映射本身不难（术语一一对应），但 REQ-008 要求"先查阅经营规范"而规范不存在（见问题 P2），实际上把口径发现责任完全转嫁给 Agent 的材料阅读行为。这是可完成性与公平性的温和风险，而非致命缺陷。

## 4. 需求—材料—Gold—评分映射矩阵

| REQ | 业务定义 | 定义清晰度 | 材料证据 | 经营规范证据 | Gold 位置 | Rubric | Scorer 实际行为 | 歧义 | 公平性风险 | 独立验证法 | 结论 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 001 空骨架 | 过程要求 | 清晰 | — | 无规范 | — | 不评分 | 不检查 | 无 | 无 | 人工 | 可验证（不影响分数） |
| 002 中文 | 语言 | 清晰 | — | — | 全簿中文 | R1 隐含 | semantic units 判定 | 无 | 低 | Semantic | 通过 |
| 003 先结论后桥 | 结构 | 清晰 | — | — | 变化归因说明!B-E | R7(9%) | R7 在 contract owners 中（fresh 路径权重被 R4-R9 取代，见 P4） | 无 | 中 | Semantic | 条件通过 |
| 004 八要素可重算可追溯 | 核心正确性 | 清晰 | 台账全表 | 口径说明!B4-B6 | 六 Sheet | R2-R6 | program_judge 契约表逐项；R8 关键词扫描 | 追溯粒度未规定 | 低 | Programmatic | 通过 |
| 005 单 XLSX | 形式 | 清晰 | — | — | — | R1(5%) | validator 物理可读性检查 | 无 | 无 | Programmatic | 通过 |
| 006 结构宽容+不可省略 | 结构/内容下限 | 清晰 | — | — | 全簿 | R1 + Equivalences | program_judge 支持 header recovery 与别名；但 R8/R9 依赖固定关键词（见 P3） | 同义改写可能失分 | 高 | Programmatic+Semantic | 条件通过 |
| 007 只读/禁网 | 环境约束 | 清晰 | 源文件 | — | — | 未评分 | 不检查 | 无 | 无 | 无法程序化验证 | 通过（信任约束） |
| 008 先查经营规范 | 流程 | **缺失** | 无独立规范文件 | **不存在** | — | 未评分 | 不检查 | Agent 找不到规范的行为分化 | 中 | 无法验证 | 不通过（见 P2） |
| 009 solve.py 提示 | 辅助脚本 | **无法确认** | 考试包内无该脚本 | /workspace/solution 不可见 | — | 未评分 | 不检查 | 脚本是否存在未知 | 高 | 待确认 | 不通过（见 P1） |
| 状态三分类 | 口径 | 材料内清晰 | 口径说明!B5 | 无 | 门店状态!E | R3(18%) | T_R3 表逐项 | 占位 0 语义未提示 | 高 | Programmatic | 条件通过 |
| 绝对影响公式 | 计算 | Rubric 内清晰 | 台账 | 无 | 组合桥!E | R4(25%) | T_R4 表 min 叶子 | Instruction 未给公式 | 中 | Programmatic | 条件通过 |
| 带符号贡献 | 计算 | 清晰 | 台账 | 无 | 组合桥!G/餐段归因!I | R4/R5 | T_R4/T_R5 | 超 100% 未提示 | 中 | Programmatic | 通过 |
| 最大推动/净抵消 | 语义结论 | 语义清晰 | 台账 | 无 | 变化归因说明!E2/E9 | R7 | semantic units（LLM 判定） | 无 | 低 | Semantic Review | 通过 |
| 正式采用结论 | 概念 | **不完整** | — | 无确认机制 | 组合桥!I"采用" | R7 内容级 | 不检查采用程序 | 多种解释 | 低 | Manual Review | 条件通过 |

## 5. 公平性分析

### 5.1 合理结构差异 —— 文本允许，实现部分允许（风险）
Rubric 明确：Sheet 名/列名/顺序/布局/公式与静态值/同义措辞均不扣分；program_judge 实现了表头恢复（actual_header_recovery）与别名绑定（aliases），结构上确有容忍。**但** R8（追溯）与 R9（公式依赖）是固定关键词启发式（fresh_owner_policy.py:6-32）：R8 要求行文本同时含期间+门店+餐段+("来源"|"源"|"追溯")，R9 要求"总/分母""组合/贡献""餐段/贡献"等词与公式共现。使用"出处""依据""溯源"或纯静态值的等价正确答案会失分——与 Rubric 的等价性承诺矛盾。

### 5.2 合理业务等价表达 —— 数值容忍良好，语义依赖 LLM
equal()（program_judge.py:29-44）支持显示精度量子化（≤0.0001）、千/万元单位换算、百分号与负数括号；等价边界处理较好。剩余风险在语义单元（LLM judge，replay 模式用预录缓存）：措辞不同的正确结论依赖语义判定质量，且 semantic-cache 绑定使不同运行环境可能拿到不同判定版本。

### 5.3 隐含要求清单
1. **R9 公式依赖**：Rubric/Instruction 均声明公式非必需，Scorer 却给公式共现 5.99% 权重且 partial credit 封顶 0.7（fresh_owner_policy.py:3-4）——纯静态值全对答案必然损失约 1.8-6% 分数。**高严重度。**
2. **R8 追溯关键词**：Instruction 只要求 "traceable"，未要求特定措辞；Scorer 以关键词存在性计分。
3. **同比边界**：Rubric R3 要求"correct year-over-year boundary"且禁止用占位 0 伪造同比——Instruction 未要求输出同比，Agent 未写同比是否失分取决于 contract 绑定，存在 Instruction 未要求却被检查（且可能扣分）的情形。
4. **持续经营 ≠ 品牌总量 / 状态不得跨期覆盖**：Rubric R6 明确要求，Instruction 未写明。
5. **frozen 路径**：hash 命中直接回放历史分（validator.py:24-30），内容相同但文件不同的工件与新工件走不同结算，跨工件可比性差。

### 5.4 相同条件核查
- 相同原始材料：是（所有 rollout 同任务包）。
- 相同经营规范：环境不存在规范，所有 Agent 面对同样缺失（条件相同，但 REQ-008 落空）。
- 相同脚本访问：solve.py 在考试包中不存在，/workspace 环境不可见——**无法确认，标记待确认**。若真实环境同样无脚本，则提示为误导信息；若部分 Agent 环境有脚本而部分没有，则条件不一致（公平性灾难，需向评测方确认）。
- 评分路径：frozen/replay/fresh 三种模式受环境与 hash 影响，非 Agent 可控因素介入结算。

## 6. 可验证性分析

| 类别 | 内容 | 验证方式 |
|---|---|---|
| Programmatic | 76 原值、12 状态、6 组合桥链、6 餐段链（含三分量）、闭合断言、单位换算 | program_judge 契约表 + 阶段二 Independent Baseline（fact_baseline.json，全部通过） |
| Semantic Review | 中文结论、先结论后桥结构、最大推动/净抵消语义、"正式采用"表述 | LLM semantic units（replay 用预录缓存，可审计但非确定） |
| Manual Review | REQ-007 只读/禁网合规、REQ-008 规范查阅行为、正式采用程序 | 无法程序化，需运行日志/人工 |
| Not Verifiable | solve.py 实际存在性与权限、所有 Agent 环境一致性、semantic-cache 判定正确性 | 材料不足，需评测方提供 |

数值结论（净变化、影响、贡献、闭合）均有明确正确性定义、原始数据支持、可独立计算预期值（阶段二已完成），可验证性充分。语义结论有业务含义与计算依据（argmax、负增量），可由 Semantic Review 覆盖。不存在"重要但完全无法验证"的需求。

## 7. solve.py 专项分析

- **存在性**：考试包内无 solve.py；全 AgentData 检索无该文件。instruction 暗示其位于 /workspace/solution/——被测运行环境，审查者不可见。**待确认**。
- **权限/一致性**：无法确认所有 Agent 是否具有相同访问条件，标记待确认，不推断。
- **业务影响**：若脚本存在且如提示所说可"生成完整归因工作簿"，则它实质提供了完整解题路径——直接读取脚本即得满分答案，任务从"归因分析"退化为"脚本执行"，评测有效性存疑；且脚本可能内嵌 Gold 数字或隐藏口径（无法审查一个不存在的文件）。若脚本不存在，提示为误导，Agent 会在不存在的路径上浪费步骤，行为分化。
- **最小立场**：无论存在与否，当前材料无法验证，必须在答卷中标记为待确认项，而非假设有利或不利。

## 8. 最重要的问题（Top 5）

**P1｜严重程度：高｜solve.py 提示与可访问性无法验证**
证据：instruction【交付提示】；考试包内无 solve.py；全库检索为空。影响：任务可行性提示可能落空；若各 Agent 环境不一致则评测前提崩塌。最小修复：评测方确认脚本存在性与只读权限，或从 instruction 移除该提示。

**P2｜严重程度：高｜REQ-008 要求的经营规范不存在**
证据：instruction 第 2 段；环境中仅有台账口径说明 Sheet（中文），无独立规范文件。影响：流程指令落空；关键口径（状态定义、同比留空、单位）需 Agent 自行从中文材料发现，英文术语映射负担不均。最小修复：提供英文版操作规范文件，或在 instruction 中直接内嵌状态口径与占位零语义。

**P3｜严重程度：高｜Scorer 未声明维度 R9（公式依赖）与 Rubric 矛盾**
证据：scorer_behavior.md"R9 is not one of the seven dimensions"；fresh_owner_policy.py:3-4（权重 5.99%，alpha=0.7 封顶）；rubric/current_rubric.md:17"formulas versus static values ... are not errors"。影响：静态值全对答案最高损失约 6% 且 non-perfect 项折损 30%——假阴性来源，直接违反公开承诺。最小修复：删除 R9 或改为对静态值中性。

**P4｜严重程度：高｜实际结算权重与声明权重不一致**
证据：scoring_params.json（R1-R7 = 5/8/18/25/25/10/9%）；fresh_owner_policy.py:3（实际仅 R4 23.4% + R5 5.6% + R6B 30% + R6E 35% + R9 6%），credit 折扣（0.8/0.7）；validator.py:24 frozen 回放。影响：60% 声明权重在未见工件路径不直接落袋；分数系统性低于完成度；两路径不可比。最小修复：公开真实权重表并解释 R6 拆分逻辑，或对齐两套权重。

**P5｜严重程度：中｜占位零语义与绝对影响公式未在 Instruction 中给出**
证据：口径说明!B5:B6 仅在材料内；Rubric R3/R4 的明确规则在 instruction 中无对应文字；客流对比_2024!F16:F18（新开基期 0）、E19:E21（关闭本期 0）。影响：把占位 0 当真实客流会错判状态/同比；公式缺失使评分依赖 Rubric 隐性补全，只读 instruction 的 Agent 处于信息劣势。最小修复：instruction 增加三句话：状态判定口径、占位 0 语义、三类影响公式。

## 9. 最终结论

Instruction **有条件通过**：任务可行、关键数值链定义清晰且可程序化验证，结构宽容承诺明确；其缺口（P2、P5）均可通过三句话级别的最小修复弥补。

但"公平且可验证的评测"当前**不成立于评分实现层面**：P3（R9 与公开规则矛盾）与 P4（权重不一致）使相同质量的答案因公式有无、路径不同而获得不同分数，这属于评分器缺陷而非 Instruction 缺陷，移交阶段四深入处理。solve.py 与经营规范的存在性（P1/P2）需评测方确认，本审查不做有利推断。

**给招聘方的最小行动清单**：①确认或删除 solve.py 提示；②提供英文操作规范或在 instruction 内嵌状态口径与公式；③删除/中性化 R9；④公开真实结算权重；⑤（阶段四）修复 R8 关键词启发式。
