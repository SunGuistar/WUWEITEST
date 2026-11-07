# 3.1 Rollout 材料盘点

## 1. 文件完整性与可读性

五份 Rollout 全部存在、可正常打开读取，无损坏、无无法解析文件。

| 文件 | 大小(字节) | SHA256(前16位) | Sheet 数 | 非空单元格 |
|---|---:|---|---:|---:|
| rollout-01 | 64,770 | 0bac0d2d1dc784fb1e19bd3f93054f1ba6a312ab43f3ad0e3cbca19b39021d14 | 9 | 2005 |
| rollout-02.xlsx | 53,713 | 0d0344763b332808935216dd0445323748416a255b43b9fba542c6bd6776eae8 | 8 | 2630 |
| rollout-03.xlsx | 55,648 | 3625ec20aad128f534893db6b0422da4f6ed2165c05653b9abea95af84369747 | 8 | 2645 |
| rollout-04.xlsx | 48,570 | b19cc1b1f8d58780d19b849e9c52ab8b989a04fe2daefa5ee41a25ff98e621b0 | 8 | 2141 |
| rollout-05.xlsx | 50,056 | a0fb49a60039c653c7ea138ddbc65c63aa4f018bcb777f59a57afec8ecb7d52b | 9 | 2058 |

（SHA256 为完整 64 位值，用于全程完整性核对；考试包文件只读，盘点全程未修改。）

## 2. 工作表清单（每份实际结构）

| Rollout | 工作表 |
|---|---|
| rollout-01 | 归因说明、品牌总览、组合桥接、餐段归因、门店明细、核验清单、源口径说明、源台账_2024、源台账_2025 |
| rollout-02 | 00_说明与结论、01_品牌总览、02_组合桥接、03_时段归因、04_状态边界、05_门店时段明细、06_源数据追溯、07_勾稽检查 |
| rollout-03 | 结论摘要、门店组合桥接、餐段归因、门店明细、源数据追溯、状态边界、勾稽检查、口径说明 |
| rollout-04 | 总览结论、组合桥接、餐段归因、状态边界、门店明细、源表映射、核对检查、分析说明 |
| rollout-05 | 说明与结论、品牌总览、组合桥、时段贡献、业态核对、门店状态边界、明细追溯、勾稽检查、源数据映射 |

结构差异显著（Sheet 命名、数量、顺序均不同），符合 Instruction 允许的结构差异范围；均包含与"组合桥 / 餐段（时段）归因 / 状态边界 / 明细追溯 / 勾稽检查"对应的表，未发现明显缺类。注意：rollout-01 无独立"状态边界"表，状态信息应在门店明细中（审计时确认）；rollout-04/05 的餐段贡献表行列较精简，需确认三分量覆盖。

## 2.1 审计目标 Sheet 定位（餐段贡献表 / 门店状态信息）

| Rollout | 餐段贡献表（检查链 A） | 门店状态信息（检查链 B） |
|---|---|---|
| rollout-01 | 餐段归因 | 门店明细（无独立状态边界表，状态列在门店明细内） |
| rollout-02 | 03_时段归因 | 04_状态边界 |
| rollout-03 | 餐段归因 | 状态边界 |
| rollout-04 | 餐段归因 | 状态边界 |
| rollout-05 | 时段贡献 | 门店状态边界 |

## 3. 当前分数与对应关系

来源：`rollouts/current_scores.md`（Recorded score version: restaurant-owner-policy-v4）。

| Rollout | Source trial | Condition | Current strict reward |
|---|---|---|---:|
| rollout-01.xlsx | task__9NYNkoK | with skill | 0.294424 |
| rollout-02.xlsx | task__HZj2iEM | with skill | 0.294424 |
| rollout-03.xlsx | task__QACxUwm | with skill | 0.944424 |
| rollout-04.xlsx | task__XAtZhSh | with skill | 0.350000 |
| rollout-05.xlsx | task__jfvsoaF | with skill | 1.000000 |

文件与评分对应关系明确：5 个文件 ↔ 5 条评分记录（rollout-01: 0.294424、rollout-02: 0.294424、rollout-03: 0.944424、rollout-04: 0.350000、rollout-05: 1.000000），无缺漏、无重复。当前分数仅作待审查对象，不作为质量依据。

## 4. 盘点结论

- 五份文件齐全、可读、无损坏；结构各异但要素齐备，满足进入逐份审计的条件。
- 3.1 完成，未开始 3.2 及业务审计。

## 附：完整 SHA256

已在上表第 3 列记录各文件完整 64 位 SHA256，盘点与审计全程以此核对文件完整性。
