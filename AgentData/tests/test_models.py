import pytest
from pydantic import ValidationError

from audit_tool.models import (
    ComparisonPeriod,
    Daypart,
    SourceReference,
    StoreStatus,
    TrafficRecord,
    BridgeComponent,
    STATUS_RAW_TO_STD,
)

REF = SourceReference(sheet="客流对比_2024", row=4)


def make_record(**kw):
    base = dict(
        record_id="2023→2024|青禾店|早餐",
        period=ComparisonPeriod.P2023_2024,
        store="青禾店",
        store_format="社区店",
        daypart=Daypart.BREAKFAST,
        status_raw="持续经营",
        status=StoreStatus.CONTINUING,
        base_value=12,
        current_value=13,
        in_scope_base=True,
        in_scope_current=True,
        yoy_raw=(13 - 12) / 12,
        source=REF,
        source_file="ledger",
    )
    base.update(kw)
    return TrafficRecord(**base)


class TestContinuing:
    def test_valid(self):
        r = make_record()
        assert r.status == StoreStatus.CONTINUING

    def test_yoy_mismatch_rejected(self):
        with pytest.raises(ValidationError):
            make_record(yoy_raw=0.5)

    def test_negative_value_rejected(self):
        with pytest.raises(ValidationError):
            make_record(base_value=-1)

    def test_new_store_yoy_must_be_none(self):
        with pytest.raises(ValidationError):
            make_record(
                status_raw="新开", status=StoreStatus.NEW,
                base_value=0, in_scope_base=False, yoy_raw=0.1,
            )


class TestNewStore:
    def test_valid(self):
        r = make_record(
            status_raw="新开", status=StoreStatus.NEW,
            base_value=0, in_scope_base=False, yoy_raw=None,
        )
        assert not r.in_scope_base and r.in_scope_current

    def test_nonzero_base_rejected(self):
        with pytest.raises(ValidationError):
            make_record(
                status_raw="新开", status=StoreStatus.NEW,
                base_value=5, in_scope_base=False, yoy_raw=None,
            )

    def test_in_scope_base_rejected(self):
        with pytest.raises(ValidationError):
            make_record(
                status_raw="新开", status=StoreStatus.NEW,
                base_value=0, in_scope_base=True, yoy_raw=None,
            )


class TestClosedStore:
    def test_valid(self):
        r = make_record(
            status_raw="关闭", status=StoreStatus.CLOSED,
            base_value=22, current_value=0,
            in_scope_base=True, in_scope_current=False, yoy_raw=None,
        )
        assert r.in_scope_base and not r.in_scope_current

    def test_nonzero_current_rejected(self):
        with pytest.raises(ValidationError):
            make_record(
                status_raw="关闭", status=StoreStatus.CLOSED,
                base_value=22, current_value=3,
                in_scope_base=True, in_scope_current=False, yoy_raw=None,
            )


class TestBridgeComponent:
    def test_contribution_consistency(self):
        b = BridgeComponent(
            period=ComparisonPeriod.P2023_2024,
            component=StoreStatus.NEW,
            member_stores=["湖滨店"],
            absolute_impact=89,
            denominator=48,
            signed_contribution=89 / 48,
        )
        assert abs(b.signed_contribution - 1.854166666666667) < 1e-9

    def test_inconsistent_contribution_rejected(self):
        with pytest.raises(ValidationError):
            BridgeComponent(
                period=ComparisonPeriod.P2023_2024,
                component=StoreStatus.NEW,
                member_stores=["湖滨店"],
                absolute_impact=89,
                denominator=48,
                signed_contribution=0.5,
            )

    def test_zero_denominator_rejected(self):
        with pytest.raises(ValidationError):
            BridgeComponent(
                period=ComparisonPeriod.P2023_2024,
                component=StoreStatus.NEW,
                member_stores=["湖滨店"],
                absolute_impact=89,
                denominator=0,
                signed_contribution=0.0,
            )


class TestStatusMapping:
    def test_all_raw_statuses_mapped(self):
        assert set(STATUS_RAW_TO_STD) == {"持续经营", "新开", "关闭"}
