"""独立计算事实基线（节点 2.5）。

全部数值从标准化台账数据独立计算，不使用 Gold 中的任何数字作为计算结果；
Gold 仅作为事后对照对象（见 gold_compare）。
"""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from .models import (
    BrandTotal,
    BridgeComponent,
    ComparisonPeriod,
    Daypart,
    DaypartContribution,
    StoreClassification,
    StoreStatus,
    TrafficRecord,
)
from .parsers import parse_ledger


class FactBaseline(BaseModel):
    brand_totals: list[BrandTotal]
    bridge: list[BridgeComponent]
    daypart_contributions: list[DaypartContribution]
    store_classifications: list[StoreClassification]

    def brand_total(self, period: ComparisonPeriod) -> BrandTotal:
        return next(b for b in self.brand_totals if b.period == period)


def classify_stores(records: list[TrafficRecord], period: ComparisonPeriod) -> list[StoreClassification]:
    recs = [r for r in records if r.period == period]
    out = []
    for store in sorted({r.store for r in recs}):
        srecs = [r for r in recs if r.store == store]
        statuses = {r.status for r in srecs}
        if len(statuses) != 1:
            raise ValueError(f"{period} {store}: 同一门店状态不一致 {statuses}")
        formats = {r.store_format for r in srecs}
        out.append(StoreClassification(
            period=period,
            store=store,
            store_format=formats.pop(),
            status=statuses.pop(),
            base_total=sum(r.base_value for r in srecs),
            current_total=sum(r.current_value for r in srecs),
            daypart_count=len(srecs),
        ))
    return out


def compute_bridge(cls: list[StoreClassification], period: ComparisonPeriod) -> list[BridgeComponent]:
    denom = sum(c.current_total for c in cls) - sum(c.base_total for c in cls)
    components = []
    for status in (StoreStatus.CONTINUING, StoreStatus.NEW, StoreStatus.CLOSED):
        members = [c for c in cls if c.status == status]
        if status == StoreStatus.CLOSED:
            impact = -sum(c.base_total for c in members)   # 关闭 = 失去基期客流
        else:
            impact = sum(c.current_total - c.base_total for c in members) if status == StoreStatus.CONTINUING \
                else sum(c.current_total for c in members)  # 新开 = 本期全部贡献
        components.append(BridgeComponent(
            period=period,
            component=status,
            member_stores=[m.store for m in members],
            absolute_impact=impact,
            denominator=denom,
            signed_contribution=impact / denom,
        ))
    return components


def compute_dayparts(records: list[TrafficRecord], period: ComparisonPeriod,
                     denom: int) -> list[DaypartContribution]:
    recs = [r for r in records if r.period == period]
    out = []
    for daypart in (Daypart.BREAKFAST, Daypart.LUNCH, Daypart.DINNER):
        drecs = [r for r in recs if r.daypart == daypart]
        cont = sum(r.current_value - r.base_value for r in drecs if r.status == StoreStatus.CONTINUING)
        new = sum(r.current_value for r in drecs if r.status == StoreStatus.NEW)
        closed = -sum(r.base_value for r in drecs if r.status == StoreStatus.CLOSED)
        out.append(DaypartContribution(
            period=period, daypart=daypart,
            continuing_impact=cont, new_impact=new, closed_impact=closed,
            denominator=denom,
        ))
    return out


def compute_baseline(result=None) -> FactBaseline:
    result = result or parse_ledger()
    records = result.records
    brand_totals, bridge, dayparts, classifications = [], [], [], []
    for period in ComparisonPeriod:
        cls = classify_stores(records, period)
        classifications.extend(cls)
        bt = BrandTotal(period=period,
                        base_total=sum(c.base_total for c in cls),
                        current_total=sum(c.current_total for c in cls))
        brand_totals.append(bt)
        bridge.extend(compute_bridge(cls, period))
        dayparts.extend(compute_dayparts(records, period, bt.net_change))
    return FactBaseline(brand_totals=brand_totals, bridge=bridge,
                        daypart_contributions=dayparts,
                        store_classifications=classifications)


# ---------- 闭合验证 ----------

def bridge_closes(baseline: FactBaseline, period: ComparisonPeriod) -> bool:
    comps = [b for b in baseline.bridge if b.period == period]
    return sum(b.absolute_impact for b in comps) == baseline.brand_total(period).net_change


def dayparts_close(baseline: FactBaseline, period: ComparisonPeriod) -> bool:
    ds = [d for d in baseline.daypart_contributions if d.period == period]
    return sum(d.absolute_change for d in ds) == baseline.brand_total(period).net_change


def daypart_components_close(baseline: FactBaseline, period: ComparisonPeriod) -> bool:
    ds = [d for d in baseline.daypart_contributions if d.period == period]
    return all(d.continuing_impact + d.new_impact + d.closed_impact == d.absolute_change
               for d in ds)


def contributions_sum_to_one(baseline: FactBaseline, period: ComparisonPeriod) -> bool:
    comps = [b for b in baseline.bridge if b.period == period]
    return abs(sum(b.signed_contribution for b in comps) - 1.0) < 1e-9


def write_baseline(baseline: FactBaseline, path: Path) -> Path:
    payload = json.loads(baseline.model_dump_json())
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
