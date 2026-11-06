"""Gold 对照（节点 2.5 D）。

从 gold/expected_answer.xlsx 提取 门店组合桥 与 餐段归因 两张表的数值，
与 Independent Baseline 逐项对照。仅作事后比对，不影响基线计算结果。
"""
from __future__ import annotations

import json
from pathlib import Path

import openpyxl
from pydantic import BaseModel

from .calculators import FactBaseline
from .models import ComparisonPeriod, Daypart, StoreStatus

GOLD_PATH = Path(__file__).resolve().parents[2] / "restaurant-portfolio-traffic-change-audit" \
    / "gold" / "expected_answer.xlsx"

PERIOD_MAP = {"2023→2024": ComparisonPeriod.P2023_2024, "2024→2025": ComparisonPeriod.P2024_2025}
STATUS_COL = {"持续经营": StoreStatus.CONTINUING, "新开": StoreStatus.NEW, "关闭": StoreStatus.CLOSED}


class GoldBridgeRow(BaseModel):
    period: ComparisonPeriod
    component: StoreStatus
    members: list[str]
    absolute_impact: int
    denominator: int
    signed_contribution: float


class GoldDaypartRow(BaseModel):
    period: ComparisonPeriod
    daypart: Daypart
    continuing_impact: int
    new_impact: int
    closed_impact: int
    absolute_change: int
    denominator: int
    signed_contribution: float


class GoldExtract(BaseModel):
    bridges: list[GoldBridgeRow]
    dayparts: list[GoldDaypartRow]


class DiffItem(BaseModel):
    category: str            # bridge / daypart
    period: str
    key: str                 # 成分或餐段名
    field: str
    baseline_value: object
    gold_value: object
    match: bool


def extract_gold(path: Path = GOLD_PATH) -> GoldExtract:
    wb = openpyxl.load_workbook(path, data_only=True)
    bridges, dayparts = [], []
    ws = wb["门店组合桥"]
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[0] is None:
            continue
        bridges.append(GoldBridgeRow(
            period=ComparisonPeriod(f"{int(row[0])}→{int(row[1])}"),
            component=STATUS_COL[str(row[2]).strip()],
            members=[m.strip() for m in str(row[3]).split("、")],
            absolute_impact=int(row[4]),
            denominator=int(row[5]),
            signed_contribution=float(row[6]),
        ))
    ws = wb["餐段归因"]
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[0] is None:
            continue
        dayparts.append(GoldDaypartRow(
            period=ComparisonPeriod(f"{int(row[0])}→{int(row[1])}"),
            daypart=Daypart(str(row[2]).strip()),
            continuing_impact=int(row[3]),
            new_impact=int(row[4]),
            closed_impact=int(row[5]),
            absolute_change=int(row[6]),
            denominator=int(row[7]),
            signed_contribution=float(row[8]),
        ))
    return GoldExtract(bridges=bridges, dayparts=dayparts)


def compare_with_gold(baseline: FactBaseline, gold: GoldExtract) -> list[DiffItem]:
    diffs: list[DiffItem] = []
    for gb in gold.bridges:
        bb = next(b for b in baseline.bridge
                  if b.period == gb.period and b.component == gb.component)
        checks = [
            ("absolute_impact", bb.absolute_impact, gb.absolute_impact),
            ("denominator", bb.denominator, gb.denominator),
            ("signed_contribution", round(bb.signed_contribution, 12), round(gb.signed_contribution, 12)),
            ("members", sorted(bb.member_stores), sorted(gb.members)),
        ]
        for field, bv, gv in checks:
            diffs.append(DiffItem(category="bridge", period=gb.period.value,
                                  key=gb.component.value, field=field,
                                  baseline_value=bv, gold_value=gv, match=bv == gv))
    for gd in gold.dayparts:
        bd = next(d for d in baseline.daypart_contributions
                  if d.period == gd.period and d.daypart == gd.daypart)
        checks = [
            ("continuing_impact", bd.continuing_impact, gd.continuing_impact),
            ("new_impact", bd.new_impact, gd.new_impact),
            ("closed_impact", bd.closed_impact, gd.closed_impact),
            ("absolute_change", bd.absolute_change, gd.absolute_change),
            ("denominator", bd.denominator, gd.denominator),
            ("signed_contribution", round(bd.signed_contribution, 12), round(gd.signed_contribution, 12)),
        ]
        for field, bv, gv in checks:
            diffs.append(DiffItem(category="daypart", period=gd.period.value,
                                  key=gd.daypart.value, field=field,
                                  baseline_value=bv, gold_value=gv, match=bv == gv))
    return diffs


def write_diff_report(diffs: list[DiffItem], path: Path) -> Path:
    mismatches = [d for d in diffs if not d.match]
    payload = {
        "total_checks": len(diffs),
        "mismatches": len(mismatches),
        "mismatch_items": [d.model_dump() for d in mismatches],
        "all_items": [d.model_dump() for d in diffs],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
