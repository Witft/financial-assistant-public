import pytest
from api_server import parse_csv_content

class TestTransactionStatusFilter:
    """测试解析引擎对废弃交易（交易关闭、失败、退款）的过滤逻辑"""

    def test_filter_alipay_closed_transactions(self):
        """测试支付宝账单过滤掉 '交易关闭' 的废单"""
        csv_data = (
            "交易时间,交易分类,交易对方,商品说明,收/支,金额,交易状态\n"
            "2026-03-01 10:00:00,数码产品,小米商城,小米手机14,支出,4299.00,交易关闭\n"
            "2026-03-01 11:00:00,餐饮美食,麦当劳,巨无霸套餐,支出,35.00,交易成功\n"
            "2026-03-01 12:00:00,服饰装扮,优衣库,T恤,支出,99.00,退款成功\n"
        )
        transactions = parse_csv_content(csv_data)
        
        # 应该只保留那一笔麦当劳，因为小米是交易关闭，优衣库是退款成功
        assert len(transactions) == 1
        assert transactions[0]["description"] == "巨无霸套餐"
        assert transactions[0]["amount"] == -35.00

    def test_filter_wechat_failed_transactions(self):
        """测试微信账单过滤掉 '失败' 或 '关闭' 的废单"""
        csv_data = (
            "交易时间,交易类型,交易对方,商品,收/支,金额(元),当前状态\n"
            "2026-03-02 10:00:00,商户消费,星巴克,拿铁,支出,30.00,支付成功\n"
            "2026-03-02 11:00:00,商户消费,苹果官网,MacBook,支出,12999.00,支付失败\n"
            "2026-03-02 12:00:00,商户消费,高铁扫码,乘车,支出,5.00,已全额退款\n"
        )
        transactions = parse_csv_content(csv_data)
        
        # 应该只保留星巴克
        assert len(transactions) == 1
        assert transactions[0]["description"] == "拿铁"
        assert transactions[0]["amount"] == -30.00
