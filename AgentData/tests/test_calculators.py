import pytest

from audit_tool import calculators, gold_compare
from audit_tool.models import ComparisonPeriod, Daypart, StoreStatus


@pytest.fixture(scope="module")
def baseline():
    return calculators.compute_baseline()


class TestBrandTotals:
    def test_period1(self, baseline):
        b = baseline.brand_total(ComparisonPeriod.P2023_2024)
        assert (b.base_total, b.current_total, b.net_change) == (374, 422, 48)
        assert abs(b.growth_rate - 48 / 374) < 1e-12

    def test_period2(self, baseline):
        b = baseline.brand_total(ComparisonPeriod.P2024_2025)
        assert (b.base_total, b.current_total, b.net_change) == (422, 481, 59)
        assert abs(b.growth_rate - 59 / 422) < 1e-12


class TestBridge:
    def test_period1_components(self, baseline):
        comps = {b.component: b for b in baseline.bridge
                 if b.period == ComparisonPeriod.P2023_2024}
        assert comps[StoreStatus.CONTINUING].absolute_impact == 23
        assert comps[StoreStatus.NEW].absolute_impact == 89
        assert comps[StoreStatus.CLOSED].absolute_impact == -64
        assert comps[StoreStatus.NEW].member_stores == ["湖滨店"]
        assert comps[StoreStatus.CLOSED].member_stores == ["客运港店"]
        assert all(b.denominator == 48 for b in comps.values())

    def test_period2_components(self, baseline):
        comps = {b.component: b for b in baseline.bridge
                 if b.period == ComparisonPeriod.P2024_2025}
        assert comps[StoreStatus.CONTINUING].absolute_impact == 31
        assert comps[StoreStatus.NEW].absolute_impact == 79
        assert comps[StoreStatus.CLOSED].absolute_impact == -51

    def test_closes_both_periods(self, baseline):
        for p in ComparisonPeriod:
            assert calculators.bridge_closes(baseline, p)

    def test_contributions_sum_to_one(self, baseline):
        for p in ComparisonPeriod:
            assert calculators.contributions_sum_to_one(baseline, p)


class TestDayparts:
    def test_period1(self, baseline):
        ds = {d.daypart: d for d in baseline.daypart_contributions
              if d.period == ComparisonPeriod.P2023_2024}
        assert ds[Daypart.BREAKFAST].absolute_change == -11
        assert ds[Daypart.LUNCH].absolute_change == 21
        assert ds[Daypart.DINNER].absolute_change == 38
        assert (ds[Daypart.BREAKFAST].continuing_impact,
                ds[Daypart.BREAKFAST].new_impact,
                ds[Daypart.BREAKFAST].closed_impact) == (4, 7, -22)

    def test_period2(self, baseline):
        ds = {d.daypart: d for d in baseline.daypart_contributions
              if d.period == ComparisonPeriod.P2024_2025}
        assert ds[Daypart.BREAKFAST].absolute_change == 1
        assert ds[Daypart.LUNCH].absolute_change == 17
        assert ds[Daypart.DINNER].absolute_change == 41

    def test_close_both_periods(self, baseline):
        for p in ComparisonPeriod:
            assert calculators.dayparts_close(baseline, p)
            assert calculators.daypart_components_close(baseline, p)


# ---------- 构造数据的边界用例 ----------

def rec(store, daypart, status, base, current, fmt="社区店", period="2023→2024"):
    from audit_tool.models import SourceReference, TrafficRecord
    in_scope = {"continuing": (True, True), "new": (False, True), "closed": (True, False)}[status.value]
    return TrafficRecord(
        record_id=f"{period}|{store}|{daypart.value}", period=ComparisonPeriod(period),
        store=store, store_format=fmt, daypart=daypart, status_raw=status.value,
        status=status, base_value=base, current_value=current,
        in_scope_base=in_scope[0], in_scope_current=in_scope[1],
        yoy_raw=None, source=SourceReference(sheet="s", row=1), source_file="f",
    )


class TestSynthetic:
    def test_zero_traffic_and_new_store(self):
        rs = [
            rec("A", Daypart.BREAKFAST, StoreStatus.CONTINUING, 0, 0),
            rec("A", Daypart.LUNCH, StoreStatus.CONTINUING, 0, 0),
            rec("A", Daypart.DINNER, StoreStatus.CONTINUING, 0, 0),
            rec("B", Daypart.BREAKFAST, StoreStatus.NEW, 0, 5),
            rec("B", Daypart.LUNCH, StoreStatus.NEW, 0, 5),
            rec("B", Daypart.DINNER, StoreStatus.NEW, 0, 5),
        ]
        cls = calculators.classify_stores(rs, ComparisonPeriod.P2023_2024)
        bridge = calculators.compute_bridge(cls, ComparisonPeriod.P2023_2024)
        assert sum(b.absolute_impact for b in bridge) == 15

    def test_closed_store_only(self):
        rs = [rec("C", d, StoreStatus.CLOSED, 10, 0) for d in Daypart]
        cls = calculators.classify_stores(rs, ComparisonPeriod.P2023_2024)
        bridge = calculators.compute_bridge(cls, ComparisonPeriod.P2023_2024)
        assert sum(b.absolute_impact for b in bridge) == -30

    def test_bridge_not_closing_detected(self, baseline):
        b = baseline.model_copy(deep=True)
        b.bridge[0] = b.bridge[0].model_copy(update={"absolute_impact": 999})
        assert not calculators.bridge_closes(b, b.bridge[0].period)

    def test_daypart_gap_detected(self, baseline):
        b = baseline.model_copy(deep=True)
        d0 = b.daypart_contributions[0]
        b.daypart_contributions[0] = d0.model_copy(update={"continuing_impact": d0.continuing_impact + 1})
        assert not calculators.dayparts_close(b, d0.period)


class TestGoldCompare:
    def test_gold_extract(self):
        gold = gold_compare.extract_gold()
        assert len(gold.bridges) == 6
        assert len(gold.dayparts) == 6

    def test_baseline_matches_gold(self, baseline):
        diffs = gold_compare.compare_with_gold(baseline, gold_compare.extract_gold())
        mismatches = [d for d in diffs if not d.match]
        assert mismatches == [], [f"{d.period}/{d.key}/{d.field}: {d.baseline_value} vs {d.gold_value}"
                                   for d in mismatches]
