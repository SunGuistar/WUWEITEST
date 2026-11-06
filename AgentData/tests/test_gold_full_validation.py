import pytest

from audit_tool import gold_full_validation as gfv

EXPECTED_COUNTS = {
    "变化归因说明": 72, "门店组合桥": 24, "餐段归因": 42,
    "门店状态": 60, "原值追溯": 152, "控制": 62,
}


@pytest.fixture(scope="module")
def details():
    """直接由代码现场计算，不依赖已归档的逐项记录文件。"""
    checks = gfv.build_all()
    return {
        "meta": {
            "total": len(checks),
            "by_sheet": {s: sum(1 for c in checks if c.sheet_name == s)
                         for s in EXPECTED_COUNTS},
            "by_status": {st: sum(1 for c in checks if c.verification_status == st)
                          for st in ("pass", "mismatch", "manual_review", "not_verifiable")},
        },
        "items": [c.model_dump() for c in checks],
    }


class TestInventory:
    def test_total(self, details):
        # 414 - 2（控制表范围边界行"闭合状态"纯文本标签，人工决定非数值类不校准，已排除）
        assert details["meta"]["total"] == 412 == sum(EXPECTED_COUNTS.values())

    def test_per_sheet_counts(self, details):
        assert details["meta"]["by_sheet"] == EXPECTED_COUNTS

    def test_unique_ids(self, details):
        ids = [i["check_id"] for i in details["items"]]
        assert len(ids) == len(set(ids)) == 412

    def test_metadata_excluded(self, details):
        names = [i["data_name"] for i in details["items"]]
        assert not any("采用" in n or "顺序" in n for n in names)

    def test_status_values_valid(self, details):
        allowed = {"pass", "mismatch", "manual_review", "not_verifiable"}
        assert all(i["verification_status"] in allowed for i in details["items"])


class TestResults:
    def test_all_pass(self, details):
        assert details["meta"]["by_status"] == {
            "pass": 412, "mismatch": 0,
            "manual_review": 0, "not_verifiable": 0,
        }


class TestRules:
    ctx = gfv.load_ctx()

    def test_sheet5_all_cell_values_match_ledger(self):
        checks = [c for c in gfv.build_sheet5(self.ctx)
                  if c.data_name.endswith(("基期值", "本期值", "原表同比"))]
        assert len(checks) == 114
        assert all(c.verification_status == "pass" for c in checks)

    def test_precision_rules(self):
        assert gfv.floats_equal(0.4791666666666667, 0.4791666666666666)
        assert not gfv.floats_equal(0.4791666666666667, 0.47917)
        assert abs(gfv.text_pct_tolerance("12.8342") - 5e-7) < 1e-15
