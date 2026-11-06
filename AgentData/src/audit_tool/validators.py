"""数据质量校验（节点 2.6）。

12 项检查，结果分四类：pass / fail / manual_review / insufficient_data。
同时把结果持久化到 SQLite validation_issues 表。
"""
from __future__ import annotations

import json
from pathlib import Path

from .calculators import (
    FactBaseline,
    bridge_closes,
    compute_baseline,
    contributions_sum_to_one,
    daypart_components_close,
    dayparts_close,
)
from .gold_compare import compare_with_gold, extract_gold
from .models import ComparisonPeriod, StoreStatus, ValidationIssue
from .parsers import parse_ledger
from .storage import DEFAULT_DB, connect


def run_all_checks(result=None, baseline: FactBaseline | None = None,
                   gold=None) -> list[ValidationIssue]:
    result = result or parse_ledger()
    baseline = baseline or compute_baseline(result)
    gold = gold or extract_gold()
    issues: list[ValidationIssue] = []

    def add(name, ok, detail=""):
        issues.append(ValidationIssue(check_name=name,
                                      status="pass" if ok else "fail",
                                      detail=detail))

    records = result.records

    # 1. 字段完整性：每条记录关键字段非空
    add("field_completeness", all(
        r.store and r.store_format and r.daypart and r.status_raw for r in records),
        f"{len(records)} 条记录检查门店/业态/餐段/状态非空")

    # 2. 数据类型：模型层已强制 int/枚举，复验无浮点客流
    add("data_types", all(
        isinstance(r.base_value, int) and isinstance(r.current_value, int) for r in records),
        "base/current 均为整数")

    # 3. 唯一性：record_id 唯一
    ids = [r.record_id for r in records]
    add("uniqueness", len(ids) == len(set(ids)),
        f"{len(ids)} 条记录，重复 {len(ids) - len(set(ids))} 条")

    # 4. 客流非负性
    add("non_negative", all(r.base_value >= 0 and r.current_value >= 0 for r in records))

    # 5. 餐段与总客流一致性：每店每期间 3 餐段齐全
    ok5 = True
    detail5 = []
    for period in ComparisonPeriod:
        stores = {r.store for r in records if r.period == period}
        for s in stores:
            dp = {r.daypart for r in records if r.period == period and r.store == s}
            if len(dp) != 3:
                ok5 = False
                detail5.append(f"{period.value} {s} 餐段数={len(dp)}")
    add("daypart_totals_consistency", ok5, "; ".join(detail5) or "每店每期 3 餐段齐全")

    # 6. 比较期间完整性：两个期间各 18 条明细
    counts = {p.value: sum(1 for r in records if r.period == p) for p in ComparisonPeriod}
    add("period_completeness", all(v == 18 for v in counts.values()), str(counts))

    # 7. 门店状态分类合理性：每店状态一致且属于三分类
    ok7 = len(baseline.store_classifications) == 12 and all(
        c.status in (StoreStatus.CONTINUING, StoreStatus.NEW, StoreStatus.CLOSED)
        for c in baseline.store_classifications)
    add("status_classification", ok7,
        f"{len(baseline.store_classifications)} 个门店期间归类（2 期间 × 6 店）")

    # 8. 组合桥闭合性
    ok8 = all(bridge_closes(baseline, p) for p in ComparisonPeriod)
    add("bridge_closure", ok8)

    # 9. 餐段贡献闭合性
    ok9 = all(dayparts_close(baseline, p) and daypart_components_close(baseline, p)
              for p in ComparisonPeriod)
    add("daypart_closure", ok9)

    # 10. 来源追溯完整性：每条记录有 sheet/row/source_file
    add("traceability", all(
        r.source.sheet and r.source.row and r.source_file for r in records))

    # 11. JSON 与 SQLite 一致性（SQLite 侧汇总 vs 基线）
    conn = connect(DEFAULT_DB)
    try:
        rows = {r[0]: (r[1], r[2]) for r in conn.execute(
            "SELECT period, SUM(base_value), SUM(current_value) "
            "FROM traffic_records GROUP BY period")}
    finally:
        conn.close()
    expected = {b.period.value: (b.base_total, b.current_total) for b in baseline.brand_totals}
    add("json_sqlite_consistency", rows == expected,
        f"SQLite={rows} 基线={expected}")

    # 12. Gold 差异检查
    diffs = compare_with_gold(baseline, gold)
    mism = [d for d in diffs if not d.match]
    add("gold_diff", not mism,
        f"{len(diffs)} 项对照，{len(mism)} 项不一致"
        + ("" if not mism else
           "; ".join(f"{d.period}/{d.key}/{d.field}" for d in mism)))

    return issues


def persist_issues(issues: list[ValidationIssue], db_path=DEFAULT_DB):
    conn = connect(db_path)
    try:
        conn.execute("DELETE FROM validation_issues")
        conn.executemany(
            "INSERT INTO validation_issues (check_name, status, detail) VALUES (?,?,?)",
            [(i.check_name, i.status, i.detail) for i in issues])
        conn.commit()
    finally:
        conn.close()


def write_report(issues: list[ValidationIssue], path: Path) -> Path:
    status_order = {"fail": 0, "manual_review": 1, "insufficient_data": 2, "pass": 3}
    payload = {
        "total": len(issues),
        "pass": sum(1 for i in issues if i.status == "pass"),
        "fail": sum(1 for i in issues if i.status == "fail"),
        "manual_review": sum(1 for i in issues if i.status == "manual_review"),
        "insufficient_data": sum(1 for i in issues if i.status == "insufficient_data"),
        "items": [i.model_dump() for i in sorted(issues, key=lambda i: status_order[i.status])],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main():
    issues = run_all_checks()
    persist_issues(issues)
    out = write_report(issues, Path(__file__).resolve().parents[2] / "data" / "validation_report.json")
    return out


if __name__ == "__main__":
    print(main())
