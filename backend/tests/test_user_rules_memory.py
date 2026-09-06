import pytest
import os
import json
from api_server import get_user_category, save_user_category, USER_RULES_FILE

class TestUserRulesMemory:
    """测试后端本地的用户自定义分类记忆库"""
    
    @pytest.fixture(autouse=True)
    def clean_rules_file(self):
        """每个测试前确保规则文件是干净的"""
        if os.path.exists(USER_RULES_FILE):
            os.remove(USER_RULES_FILE)
        yield
        if os.path.exists(USER_RULES_FILE):
            os.remove(USER_RULES_FILE)
            
    def test_save_and_get_user_category(self):
        """测试：保存一个自定义规则后，能否正确读出"""
        # 1. 假设用户在前端把某个独立咖啡馆手动改成了"dining"
        save_user_category("独立主理人手冲咖啡", "dining")
        
        # 2. 下次解析时，应该能直接拿到 dining
        assert get_user_category("独立主理人手冲咖啡") == "dining"
        
    def test_overwrite_existing_rule(self):
        """测试：用户如果改主意了，规则能否被覆盖"""
        save_user_category("神秘网购", "other")
        save_user_category("神秘网购", "shopping")
        
        assert get_user_category("神秘网购") == "shopping"
        
    def test_unseen_description_returns_none(self):
        """测试：没见过的商户名，应该返回 None，以便走后续的默认规则"""
        assert get_user_category("没见过的全新商户") is None
