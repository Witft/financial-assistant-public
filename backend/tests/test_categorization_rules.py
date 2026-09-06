import pytest
from api_server import classify_transaction

class TestCategorizationEngineV2:
    """测试本地规则分类引擎(Categorization Engine V2)的准确性"""

    @pytest.mark.parametrize("description, original_type, expected_category", [
        # 1. 数码订阅 (Digital Subscription)
        ("Bandwagon Host Compute Cloud - Invoice 23058156", "商户消费", "digital_subscription"),
        ("云服务器ECS(包月)", "商户消费", "digital_subscription"),
        ("CodePlanPlus-月度会员", "商户消费", "digital_subscription"),
        ("黄金会员-包月", "商户消费", "digital_subscription"),
        ("高档充电连续包月九", "商户消费", "digital_subscription"),
        ("apple.com/bill/MS2QJ253M8a0", "商户消费", "digital_subscription"),
        
        # 2. 日用百货 (Daily Necessities)
        ("维达湿巾纸纯水男女成人私处房事家用湿纸巾家庭实惠装80片大包装", "商户消费", "daily_necessities"),
        ("【优惠价】适用于云鲸J4扫地机器人清洁液地面清洁剂配件J1J2J3J5地板清洗剂", "商户消费", "daily_necessities"),
        ("美国原装进口艾禾美口气清新清洁亮白牙齿护理口腔含氟小苏打牙膏 等多件", "商户消费", "daily_necessities"),
        ("[明星同款]tempo得宝雪松之境4层加厚90抽任选家用实惠装抽纸", "商户消费", "daily_necessities"),
        
        # 3. 购物 (Shopping)
        ("【明星同款】蕉内非常503Relax男女同款圆领四季卫衣空气层新款", "商户消费", "shopping"),
        ("李宁运动裤男款春季新款裤子棉质长裤宽松直筒休闲裤男士针织卫裤", "商户消费", "shopping"),
        ("Vulkit新款超薄小巧钱包男士卡包名片夹RFID防盗刷银行卡证件包 等多件", "商户消费", "shopping"),
        
        # 4. 家庭支持 (Family Support)
        ("转账备注:微信转账", "微信转账", "family_support"),
        ("微信转账-妈妈", "转账", "family_support"),
        ("转账给爸爸", "转账", "family_support"),
        
        # 5. 餐饮 (Dining)
        ("麦当劳", "商户消费", "dining"),
        ("喜茶支付中心支付单", "商户消费", "dining"),
        ("米村拌饭(杭州亲橙里店)外卖订单", "商户消费", "dining"),
        ("正宗信阳烤炉鸡蛋灌饼外卖订单", "商户消费", "dining"),
        ("美团/大众点评点餐订单-041750260", "商户消费", "dining"),
        
        # 6. 交通 (Transportation)
        ("高德打车订单", "商户消费", "transportation"),
        ("杭州通互联互通卡 充值", "商户消费", "transportation"),
        
        # 7. 娱乐 (Entertainment)
        ("斗鱼直播-6鱼翅（三***角）", "商户消费", "digital_subscription"), # "直播" 在数码订阅里，会先匹配
        
        # 8. 兜底测试 (Other)
        ("不知道什么乱七八糟的杂项单子", "商户消费", "other"),
        ("/", "商户消费", "other"),
    ])
    def test_local_keyword_rules(self, description, original_type, expected_category):
        """测试账单描述能否精确命中我们的 V2 规则词库"""
        result_category, confidence, requires_human_review = classify_transaction(description, original_type)
        assert result_category == expected_category, f"Failed for '{description}': expected {expected_category}, got {result_category}"
        assert 0.0 <= confidence <= 1.0
        assert isinstance(requires_human_review, bool)
