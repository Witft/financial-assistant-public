import pytest
from api_server import classify_transaction

class TestClassificationConfidence:
    """测试分类引擎返回的置信度契约"""

    def test_unknown_transaction_requires_review(self):
        """完全不认识的交易应该归入other，置信度极低，且必须要求人工审核"""
        category, confidence, requires_review = classify_transaction("火星来的神秘扣款", "未知类型", skip_memory=True)
        assert category == "other"
        assert confidence < 0.2
        assert requires_review is True

    def test_keyword_match_high_confidence(self):
        """精准命中关键词库的交易，置信度应该高，无需审核"""
        category, confidence, requires_review = classify_transaction("肯德基原味鸡", "商户消费", skip_memory=True)
        assert category == "dining"
        assert confidence > 0.8
        assert requires_review is False

    def test_type_fallback_medium_confidence(self):
        """只命中交易类型fallback的，置信度中等，视情况决定是否审核"""
        category, confidence, requires_review = classify_transaction("什么描述都没有", "外卖美食", skip_memory=True)
        assert category == "dining"
        assert 0.4 < confidence < 0.8
        # 中等置信度可以要求审核，也可以不要求，具体看你的严格程度，这里假设中等置信度也要审核
        assert requires_review is True

    def test_ambiguous_person_name_transfer_requires_review(self):
        """带转账语义但只有人名/昵称的记录，不应直接视为家庭支持，应进入人工审核"""
        category, confidence, requires_review = classify_transaction("微信转账-李华", "转账", skip_memory=True)
        assert category == "other"
        assert confidence < 0.3
        assert requires_review is True

    def test_explicit_family_relation_transfer_skips_review(self):
        """明确家庭关系的转账应稳定判为 family_support，无需人工审核"""
        category, confidence, requires_review = classify_transaction("微信转账-妈妈", "转账", skip_memory=True)
        assert category == "family_support"
        assert confidence >= 0.85
        assert requires_review is False

    # ──────────────────────────────────────────────────────────────
    # 第二 A/B 领域：平台名误导纠偏
    # ──────────────────────────────────────────────────────────────

    def test_platform_name_with_secondary_healthcare_indicator(self):
        """平台名 + 医疗/药品关键词 → 应覆盖平台默认分类"""
        for text, tx_type in [
            ("美团买药", "外卖美食"),
            ("饿了么-叮当快药", "外卖美食"),
            ("京东健康", "商户消费"),
        ]:
            category, confidence, requires_review = classify_transaction(text, tx_type, skip_memory=True)
            assert category == "healthcare", f"'{text}' 应为 healthcare，实际为 {category}"
            assert requires_review is False

    def test_platform_name_with_secondary_shopping_indicator(self):
        """平台名 + 超市/便利关键词 → 应覆盖平台默认分类"""
        category, confidence, requires_review = classify_transaction("美团超市便利", "外卖美食", skip_memory=True)
        assert category == "shopping", f"应为 shopping，实际为 {category}"
        assert requires_review is False

    def test_platform_name_without_secondary_stays_default(self):
        """平台名 + 无次要指标 → 保持平台默认分类（防回归）"""
        for text, tx_type, expected in [
            ("美团外卖-华莱士", "外卖美食", "dining"),
            ("京东到家-水果", "商户消费", "shopping"),
        ]:
            category, confidence, requires_review = classify_transaction(text, tx_type, skip_memory=True)
            assert category == expected, f"'{text}' 应为 {expected}，实际为 {category}"
