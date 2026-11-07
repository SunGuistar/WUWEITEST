# Scorer 评分执行流程图（4.4.1）

> 依据：`validator.py`（入口）、`program_judge.py`（程序评分）、`fresh_owner_policy.py`（结算）、
> `frozen_owner_policy.json`（历史记录）、`scorer_behavior.md`（披露说明）。
> 标注【缺失】的组件在考试包快照中不存在，相关行为无法执行验证。

```
评分入口  validator.py:main()
│
├─① 接收工件路径（目录则拼 门店客流变化归因说明.xlsx）        validator.py:16-18
├─② 存在性/非空检查 → 否则直接 0 分                          validator.py:19-21
│
├─③ 计算 SHA-256                                            validator.py:22
├─④ 查 frozen_owner_policy.json["artifacts"]                validator.py:23-24
│   │
│   ├─【命中历史】── 直接返回预存 reward/completion ──────┐    validator.py:25-30
│   │     （replay_mode: frozen-owner-ledger-exact-policy） │
│   │                                                     │
│   └─【未命中】                                          │
│       ├─⑤ openpyxl 物理可读性检查 → 不可读则 0 分        │  validator.py:31-38
│       ├─⑥ LLM_JUDGE_MODE 分支                          │
│       │   ├─ replay: bound_cache.load_recorded(semantic-cache)   validator.py:43-44
│       │   │           【缺失 bound_cache.py / semantic-cache/ → 快照不可运行】
│       │   └─ fresh:  校验 runtime 哈希 → 调 llm_judge/judge.py   validator.py:45-60
│       │               【缺失 llm_judge/ 目录 → 快照不可运行】
│       ├─⑦ program_judge.score(artifact, decision)        │
│       │   ├─ 读 llm_judge/contract.json 契约表            │  program_judge.py:60 【缺失】
│       │   ├─ 按契约 keys/表头 在工作簿中定位并绑定记录     │  program_judge.py:63-127
│       │   │   （header 恢复、别名、单位换算、trace 推断）   │
│       │   ├─ 逐记录数值比对 equal()（精度量子化容忍）      │  program_judge.py:129-148
│       │   ├─ 聚合 owners → completion[owner]              │  program_judge.py:161-166
│       │   └─ 检测 evaluator_instruction_adoption          │  program_judge.py:168
│       │       （工件含给评分器的指令 → 标记，主流程判 0） │
│       ├─⑧ fresh_owner_policy.settle_owner()               │
│       │   ├─ R6 按控制类型拆 R6A–R6F                      │  fresh_owner_policy.py:40-41
│       │   ├─ r9_dependency(): 公式×关键词启发式           │  fresh_owner_policy.py:6-21
│       │   ├─ r8_traceability(): 来源关键词扫描            │  fresh_owner_policy.py:22-32
│       │   └─ 仅结算 5 个 Owner：                          │  fresh_owner_policy.py:3,42-43
│       │       R4 23.4493% / R5 5.5576% / R6B 30% / R6E 35% / R9 5.9931%
│       │       credit = 1.0 if c==1 else α·c              │  fresh_owner_policy.py:4
│       │       （α: 0.8 / 0.8 / 0.8 / 0.8 / 0.7）           │  fresh_owner_policy.py:4
│       └─⑨ adoption 判 0；返回 strict_score                │  validator.py:68-72
│
└──────────────────────────────────────────────────────────┘
```

## 关键路径结论

1. **两条互斥路径**：命中 frozen 哈希 → 纯回放历史分（不重新评分）；未命中 → 依赖缺失运行时的"未见工件"路径。
2. **五份 Rollout 全部命中 frozen**（hash 逐一核对一致）→ 当前分数是历史记录回放，**不是当前源码重算结果**。
3. **快照不可独立运行**：`bound_cache.py`、`semantic-cache/`、`llm_judge/`（含 contract.json）均不存在，
   `scorer_behavior.md` 自述"not a standalone runnable verifier"——4.4.5/4.4.6 对新工件的结论只能是源码级推演。
4. **实际结算只发生一次**（validator.py:67 settle_owner），其权重表是最终分的唯一来源。
