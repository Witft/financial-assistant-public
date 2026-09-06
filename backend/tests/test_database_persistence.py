#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PostgreSQL persistence tests for parsed transactions."""

import os
import sys

# 将父目录添加到 sys.path 以便导入 backend 模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import build_transaction_record, generate_transaction_id, is_database_enabled


def test_database_is_disabled_when_database_url_is_empty(monkeypatch):
    """未配置 DATABASE_URL 时，解析接口应保持无状态兼容模式。"""
    monkeypatch.delenv("DATABASE_URL", raising=False)

    assert is_database_enabled() is False


def test_generate_transaction_id_is_stable_for_same_transaction():
    """同一笔交易应生成稳定 ID，方便重复上传时 upsert 去重。"""
    tx = {
        "date": "2026-04-01 08:00:00",
        "description": "星巴克",
        "amount": -35.0,
        "category": "dining",
        "type": "expense",
        "source": "alipay",
    }

    assert generate_transaction_id(tx) == generate_transaction_id(dict(tx))
    assert generate_transaction_id(tx).startswith("tx_")


def test_generate_transaction_id_ignores_category_changes():
    """同一笔真实交易改分类后，ID 也应保持稳定，避免重复入库。"""
    tx = {
        "date": "2026-04-01 08:00:00",
        "description": "星巴克",
        "amount": -35.0,
        "category": "dining",
        "type": "expense",
        "source": "alipay",
    }
    revised = dict(tx, category="other")

    assert generate_transaction_id(tx) == generate_transaction_id(revised)


def test_build_transaction_record_preserves_agent_facing_fields():
    """写入 PostgreSQL 的记录必须保留 Agent 后续查询所需的结构化字段。"""
    tx = {
        "date": "2026-04-01 08:00:00",
        "description": "星巴克",
        "transaction_type": "餐饮美食",
        "amount": -35.0,
        "category": "dining",
        "type": "expense",
        "source": "alipay",
        "confidence": 0.9,
        "requires_human_review": False,
    }

    record = build_transaction_record(tx)

    assert record["id"].startswith("tx_")
    assert record["transaction_date"] == "2026-04-01"
    assert record["amount"] == -35.0
    assert record["category"] == "dining"
    assert record["description"] == "星巴克"
    assert record["source"] == "alipay"
    assert record["type"] == "expense"
    assert record["transaction_type"] == "餐饮美食"
    assert record["confidence"] == 0.9
    assert record["requires_human_review"] is False
    assert record["raw_data"]["description"] == "星巴克"


def test_build_transaction_record_allows_income_category_after_manual_review():
    """人工审核后的收入类标签应能以结构化 category 持久化。"""
    tx = {
        "date": "2026-04-03 10:00:00",
        "description": "工资",
        "amount": 10000.0,
        "category": "income",
        "type": "income",
        "source": "alipay",
        "requires_human_review": True,
    }

    record = build_transaction_record(tx)

    assert record["category"] == "income"
    assert record["type"] == "income"
    assert record["raw_data"]["category"] == "income"
