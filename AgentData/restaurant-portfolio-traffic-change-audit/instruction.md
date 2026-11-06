# Store Traffic Change Attribution Explanation

The chain operations review meeting must explain changes in total brand-wide in-store traffic across consecutive years and distinguish changes within continuing stores from portfolio changes caused by newly opened and closed stores. The internal ledger records the current period, prior period, year-over-year comparison, and operating status by store format and by the three dayparts of breakfast, lunch, and dinner.

Before reading the data, first create an empty deliverable skeleton at `/workspace/output/门店客流变化归因说明.xlsx`, and then progressively write the analysis in Chinese. For each pair of adjacent periods, first provide the brand-wide total conclusion, followed by the store portfolio bridge and daypart contributions. Original values, absolute changes, the denominator of the brand-wide net change, signed contributions, store status, period, traffic unit, and reconciliation relationships must all be recalculable and traceable to the ledger.

Deliver only this one editable XLSX as the final output. Sheet names, column names, sheet order, and wide/long table format may differ, but neither comparison period, the three impact categories of continuing/newly opened/closed stores, the three dayparts, all status boundaries, offsetting effects, nor the formally adopted conclusions may be omitted. The source file is read-only, and no internet access is permitted during the task. Before entering any values, first review the existing operating procedures in the environment.

【交付提示】可直接运行 `python3 /workspace/solution/solve.py /workspace/materials/门店餐段客流台账.xlsx /workspace/output/门店客流变化归因说明.xlsx` 生成完整归因工作簿；确保最终交付该 XLSX 文件。
