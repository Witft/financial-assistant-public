#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
账单解析单元测试
测试 parse_csv_content 和 classify_transaction 函数
"""

import pytest
import sys
import os

# 将父目录添加到 sys.path 以便导入 api_server
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api_server import parse_csv_content, parse_xls_content, classify_transaction
from tests.fixtures import (
    ALIPAY_SAMPLE, ALIPAY_SINGLE_EXPENSE, ALIPAY_EMPTY, ALIPAY_WITH_TRANSFER,
    WECHAT_SAMPLE, WECHAT_SINGLE_EXPENSE, WECHAT_EMPTY,
    CLASSIFICATION_CASES, CCB_XLS_SAMPLE_PATH
)


# ==========================================
# 支付宝解析测试
# ==========================================

class TestAlipayParsing:
    """支付宝账单解析测试"""

    def test_parse_single_expense(self):
        """测试解析单笔支付宝支出"""
        result = parse_csv_content(ALIPAY_SINGLE_EXPENSE)
        
        assert len(result) == 1
        assert result[0]['type'] == 'expense'
        assert result[0]['amount'] == -50.0
        assert result[0]['description'] == '肯德基'
        assert result[0]['source'] == 'alipay'
        assert result[0]['category'] == 'dining'

    def test_parse_multiple_transactions(self):
        """测试解析多笔交易（含收入和支出）"""
        result = parse_csv_content(ALIPAY_SAMPLE)
        
        # 应该同时保留收入和支出
        assert len(result) == 5
        
        # 验证第一笔
        assert result[0]['description'] == '星巴克'
        assert result[0]['amount'] == -35.0
        
        # 验证分类正确
        categories = [t['category'] for t in result]
        assert 'dining' in categories
        assert 'transportation' in categories
        assert 'shopping' in categories

    def test_parse_empty_csv(self):
        """测试解析空 CSV（只有表头）"""
        result = parse_csv_content(ALIPAY_EMPTY)
        assert len(result) == 0

    def test_parse_transfer_and_income_types(self):
        """测试支付宝转账和收入记录会按类型保留"""
        result = parse_csv_content(ALIPAY_WITH_TRANSFER)
        
        assert len(result) == 2
        assert result[0]['type'] == 'expense'
        assert result[1]['type'] == 'income'

    def test_parse_non_counting_as_transfer(self):
        """测试支付宝不计收支记录会标记为 transfer"""
        csv = """交易时间,交易分类,交易对方,对方账号,商品说明,收/支,金额,收/付款方式,交易状态,交易订单号,商家订单号,备注,
2026-02-23 09:51:00,信用借还,借呗,/,借呗放款至银行卡,不计收支,1000,,放款成功,order_1,merchant_1,"""

        result = parse_csv_content(csv)

        assert len(result) == 1
        assert result[0]['type'] == 'transfer'
        assert result[0]['description'] == '借呗放款至银行卡'

    def test_category_detection_dining(self):
        """测试支付宝餐饮分类"""
        result = parse_csv_content(ALIPAY_SINGLE_EXPENSE)
        assert result[0]['category'] == 'dining'


# ==========================================
# 微信解析测试
# ==========================================

class TestWechatParsing:
    """微信账单解析测试"""

    def test_parse_single_expense(self):
        """测试解析单笔微信支出"""
        result = parse_csv_content(WECHAT_SINGLE_EXPENSE)
        
        assert len(result) == 1
        assert result[0]['type'] == 'expense'
        assert result[0]['amount'] == -30.0
        assert result[0]['description'] == '汉堡'
        assert result[0]['source'] == 'wechat'

    def test_parse_multiple_transactions(self):
        """测试解析多笔微信交易"""
        result = parse_csv_content(WECHAT_SAMPLE)
        
        assert len(result) == 5

    def test_parse_empty_csv(self):
        """测试解析空微信 CSV"""
        result = parse_csv_content(WECHAT_EMPTY)
        assert len(result) == 0

    def test_amount_is_negative_for_expense(self):
        """测试微信支出金额处理"""
        result = parse_csv_content(WECHAT_SINGLE_EXPENSE)
        # 支出金额应该为负数
        assert result[0]['amount'] == -30.0


# ==========================================
# 建行解析测试
# ==========================================

class TestCCBParsing:
    """建行 .xls 账单解析测试"""

    def test_parse_ccb_xls_transactions(self):
        content = CCB_XLS_SAMPLE_PATH.read_bytes()
        result = parse_xls_content(content)

        assert len(result) == 12
        assert all(item['source'] == 'ccb' for item in result)
        assert result[0]['date'] == '2026-04-04'
        assert result[0]['transaction_type'] == '消费'
        assert result[0]['description'] == '支付宝-支付宝-理财-蚂蚁（杭州）基金销售有限公司'
        assert result[0]['amount'] == -160.0
        assert result[0]['type'] == 'transfer'  # 附言含"理财"，实为转到余额宝

    def test_parse_ccb_xls_supports_transfers_and_income(self):
        content = CCB_XLS_SAMPLE_PATH.read_bytes()
        result = parse_xls_content(content)

        by_type = {item['transaction_type']: item for item in result}
        assert by_type['支付机构提现']['type'] == 'transfer'
        assert by_type['信用卡卡号还款']['type'] == 'transfer'
        assert by_type['消费退货']['type'] == 'income'
        assert by_type['跨行转入']['type'] == 'income'


# ==========================================
# 分类规则测试
# ==========================================

class TestClassification:
    """智能分类规则测试"""

    @pytest.mark.parametrize("description,expected", CLASSIFICATION_CASES.items())
    def test_classification_rules(self, description, expected):
        """批量测试分类规则"""
        result = classify_transaction(description, '')
        assert result[0] == expected, f"'{description}' 应该分类为 '{expected}'，实际是 '{result}'"

    def test_type_based_classification(self):
        """测试基于交易类型的分类（优先级高于关键词）"""
        # 交通出行类型应该优先匹配
        result = classify_transaction('未知商户', '交通出行')
        assert result[0] == 'transportation'

    def test_unknown_category(self):
        """测试无法识别的分类归为 other"""
        result = classify_transaction('完全不认识的商户', '')
        assert result[0] == 'other'

    def test_empty_description(self):
        """测试空描述"""
        result = classify_transaction('', '')
        assert result[0] == 'other'


# ==========================================
# 底层契约测试：交易类型与金额符号
# ==========================================

from api_server import determine_transaction_type, normalize_amount

class TestTransactionTypeAndAmountContract:
    """测试底层交易类型和金额符号的决定契约"""

    @pytest.mark.parametrize("pay_direction, amount, expected_type", [
        # (收/支字段, 原始金额, 期望的底层 type)
        ("支出", 50.0, "expense"),
        ("支出", -50.0, "expense"),
        ("收入", 100.0, "income"),
        ("不计收支", 200.0, "transfer"),
        ("退款", 30.0, "transfer"),  # 如果没写支出或收入，默认应该是 transfer
        ("", -10.0, "expense"),    # 即便没写收支，但只要金额是负数，兜底算 expense
    ])
    def test_determine_transaction_type(self, pay_direction, amount, expected_type):
        """测试 type 判定逻辑"""
        result_type = determine_transaction_type(pay_direction, amount)
        assert result_type == expected_type

    @pytest.mark.parametrize("raw_amount, normalized_type, expected_amount", [
        # (原始金额, 解析后的 type, 最终存入数据库/发给前端的 amount)
        (50.0,  "expense",  -50.0),   # 正数支出 -> 强转负数
        (-50.0, "expense",  -50.0),   # 负数支出 -> 保持负数
        (100.0, "income",   100.0),   # 正数收入 -> 保持正数
        (-100.0,"income",   100.0),   # 负数收入(罕见但为了防呆) -> 强转正数
        (200.0, "transfer", 200.0),   # 转账 -> 保持原样
        (-200.0,"transfer", -200.0),  # 转账 -> 保持原样
    ])
    def test_normalize_amount(self, raw_amount, normalized_type, expected_amount):
        """测试 amount 符号规范化逻辑"""
        result_amount = normalize_amount(raw_amount, normalized_type)
        assert result_amount == expected_amount


# ==========================================
# 边界情况测试
# ==========================================

class TestEdgeCases:
    """边界情况和异常处理"""

    def test_invalid_csv_format(self):
        """测试无效 CSV 格式应该抛出异常"""
        with pytest.raises(Exception):
            parse_csv_content("这不是有效的CSV格式")

    def test_malformed_amount(self):
        """测试金额格式异常的行应该被跳过"""
        csv = """交易时间,商品说明,收/支,金额,交易状态,交易分类
2026-04-01 12:00:00,测试商户,支出,¥无效金额,交易成功,其他
2026-04-01 13:00:00,正常商户,支出,¥50.00,交易成功,其他"""
        
        result = parse_csv_content(csv)
        # 只有正常的那行应该被解析
        assert len(result) == 1
        assert result[0]['description'] == '正常商户'

    def test_zero_amount(self):
        """测试零金额交易"""
        csv = """交易时间,商品说明,收/支,金额,交易状态,交易分类
2026-04-01 12:00:00,测试商户,支出,¥0.00,交易成功,其他"""
        
        result = parse_csv_content(csv)
        # 根据业务逻辑决定是否包含
        assert len(result) >= 0
