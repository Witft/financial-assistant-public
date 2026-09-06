#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API 集成测试
测试 FastAPI 的 /api/parse 接口
"""

import pytest
import io
import sys
import os
from unittest.mock import Mock

# 将父目录添加到 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from api_server import app
from tests.fixtures import ALIPAY_SAMPLE, WECHAT_SAMPLE, CCB_XLS_SAMPLE_PATH

client = TestClient(app)


class TestParseAPI:
    """测试 /api/parse 接口"""

    def test_parse_alipay_csv(self):
        """测试上传支付宝 CSV"""
        response = client.post(
            "/api/parse",
            files={"file": ("alipay.csv", io.BytesIO(ALIPAY_SAMPLE.encode('utf-8')), "text/csv")}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] == True
        assert len(data['transactions']) >= 1

    def test_parse_wechat_csv(self):
        """测试上传微信 CSV"""
        response = client.post(
            "/api/parse",
            files={"file": ("wechat.csv", io.BytesIO(WECHAT_SAMPLE.encode('utf-8')), "text/csv")}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] == True
        assert len(data['transactions']) >= 1

    def test_parse_ccb_xls(self):
        """测试上传建行 .xls 账单"""
        response = client.post(
            "/api/parse",
            files={"file": ("ccb.xls", io.BytesIO(CCB_XLS_SAMPLE_PATH.read_bytes()), "application/vnd.ms-excel")}
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert len(data['transactions']) == 12
        first = data['transactions'][0]
        assert first['source'] == 'ccb'
        assert first['date'] == '2026-04-04'
        assert first['description'] == '支付宝-支付宝-理财-蚂蚁（杭州）基金销售有限公司'
        assert first['amount'] == -160.0
        assert first['type'] == 'transfer'  # 附言含"理财"，实为转到余额宝

        transfer_like = {tx['description']: tx for tx in data['transactions']}
        assert transfer_like['资金发放']['source'] == 'ccb'
        assert any(tx['type'] == 'transfer' for tx in data['transactions'])

    def test_parse_invalid_file_type(self):
        """测试上传非 CSV/XLSX 文件"""
        response = client.post(
            "/api/parse",
            files={"file": ("report.txt", io.BytesIO(b"hello world"), "text/plain")}
        )
        assert response.status_code == 400
        assert "只支持 CSV、XLS 或 XLSX 文件" in response.json()['detail']

    def test_parse_empty_csv(self):
        """测试上传空 CSV"""
        csv = "交易时间,商品说明,收/支,金额,交易状态,交易分类"
        response = client.post(
            "/api/parse",
            files={"file": ("empty.csv", io.BytesIO(csv.encode('gbk')), "text/csv")}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] == True
        assert len(data['transactions']) == 0

    def test_response_format(self):
        """测试返回格式是否符合 ParseResponse 模型"""
        response = client.post(
            "/api/parse",
            files={"file": ("alipay.csv", io.BytesIO(ALIPAY_SAMPLE.encode('utf-8')), "text/csv")}
        )
        
        data = response.json()
        assert 'success' in data
        assert 'transactions' in data
        assert 'message' in data
        
        # 验证交易对象格式
        if len(data['transactions']) > 0:
            tx = data['transactions'][0]
            assert 'id' in tx
            assert 'date' in tx
            assert 'amount' in tx
            assert 'category' in tx
            assert 'description' in tx
            assert 'source' in tx
            assert 'type' in tx

    def test_parse_persists_transactions_when_database_is_enabled(self, monkeypatch):
        """配置 DATABASE_URL 后，/api/parse 应把解析结果写入持久化层。"""
        save_mock = Mock(return_value=5)
        monkeypatch.setattr('api_server.database.is_database_enabled', lambda: True)
        monkeypatch.setattr('api_server.database.save_transactions', save_mock)

        response = client.post(
            "/api/parse",
            files={"file": ("alipay.csv", io.BytesIO(ALIPAY_SAMPLE.encode('utf-8')), "text/csv")}
        )

        assert response.status_code == 200
        save_mock.assert_called_once()
        persisted_transactions = save_mock.call_args.args[0]
        assert len(persisted_transactions) == len(response.json()['transactions'])
        assert persisted_transactions[0]['description'] == '星巴克'
        assert response.json()['message'] == '成功解析 5 笔交易，并已写入数据库 5 笔'

    def test_parse_reports_when_database_is_disabled(self, monkeypatch):
        """未配置 DATABASE_URL 时，/api/parse 应明确提示仅解析未持久化。"""
        monkeypatch.setattr('api_server.database.is_database_enabled', lambda: False)

        response = client.post(
            "/api/parse",
            files={"file": ("alipay.csv", io.BytesIO(ALIPAY_SAMPLE.encode('utf-8')), "text/csv")}
        )

        assert response.status_code == 200
        assert response.json()['message'] == '成功解析 5 笔交易；未配置 DATABASE_URL，当前未写入数据库'

    def test_parse_returns_succeeded_import_job_status(self, monkeypatch):
        """无待审核交易时，/api/parse 应返回 SUCCEEDED 的 import job 状态。"""
        create_job_mock = Mock(return_value="job_succeeded_1")
        create_run_mock = Mock(return_value='run_succeeded_1')
        finalize_run_mock = Mock()
        finalize_job_mock = Mock()
        clean_transactions = [
            {
                'date': '2026-04-01',
                'amount': -35.0,
                'category': 'dining',
                'description': '星巴克',
                'source': 'alipay',
                'type': 'expense',
                'requires_human_review': False,
            },
            {
                'date': '2026-04-01',
                'amount': -25.0,
                'category': 'transportation',
                'description': '滴滴出行',
                'source': 'alipay',
                'type': 'expense',
                'requires_human_review': False,
            },
        ]

        monkeypatch.setattr('api_server.database.is_database_enabled', lambda: True)
        monkeypatch.setattr('api_server.database.save_transactions', Mock(return_value=2))
        monkeypatch.setattr('api_server.parse_csv_content', lambda _csv_text: clean_transactions)
        monkeypatch.setattr('api_server.database.create_import_job', create_job_mock, raising=False)
        monkeypatch.setattr('api_server.database.create_import_job_run', create_run_mock, raising=False)
        monkeypatch.setattr('api_server.database.finalize_import_job_run', finalize_run_mock, raising=False)
        monkeypatch.setattr('api_server.database.finalize_import_job', finalize_job_mock, raising=False)

        response = client.post(
            "/api/parse",
            files={"file": ("alipay.csv", io.BytesIO(ALIPAY_SAMPLE.encode('utf-8')), "text/csv")}
        )

        assert response.status_code == 200
        data = response.json()
        assert data['job_id'] == 'job_succeeded_1'
        assert data['run_id'] == 'run_succeeded_1'
        assert data['job_status'] == 'SUCCEEDED'
        assert data['review_required_count'] == 0
        assert data['persisted_count'] == 2
        create_job_mock.assert_called_once()
        create_run_mock.assert_called_once_with(
            'job_succeeded_1',
            step='parse_bill',
            input_summary={
                'filename': 'alipay.csv',
                'file_kind': 'csv',
                'source': 'unknown',
            },
            model_version=None,
            retry_count=0,
        )
        finalize_run_mock.assert_called_once_with(
            'run_succeeded_1',
            step='persist_transactions',
            final_status='SUCCEEDED',
            output_summary={
                'total_transactions': 2,
                'persisted_count': 2,
                'review_required_count': 0,
                'failure_policy': 'no_retry_needed',
            },
            error_message=None,
        )
        finalize_job_mock.assert_called_once_with(
            'job_succeeded_1',
            status='SUCCEEDED',
            total_transactions=2,
            review_required_count=0,
            persisted_count=2,
            error_message=None,
        )
        
    def test_parse_returns_job_run_parse_bill_when_database_is_disabled(self, monkeypatch):
        create_job_mock = Mock(return_value="job_succeeded_1")
        create_run_mock = Mock(return_value='run_succeeded_1')
        finalize_run_mock = Mock()
        finalize_job_mock = Mock()
        clean_transactions = [
            {
                'date': '2026-04-01',
                'amount': -35.0,
                'category': 'dining',
                'description': '星巴克',
                'source': 'alipay',
                'type': 'expense',
                'requires_human_review': False,
            },
            {
                'date': '2026-04-01',
                'amount': -25.0,
                'category': 'transportation',
                'description': '滴滴出行',
                'source': 'alipay',
                'type': 'expense',
                'requires_human_review': False,
            },
        ]
        
        monkeypatch.setattr('api_server.database.is_database_enabled', lambda: False)
        monkeypatch.setattr('api_server.parse_csv_content', lambda _csv_text: clean_transactions)
        monkeypatch.setattr('api_server.database.create_import_job', create_job_mock, raising=False)
        monkeypatch.setattr('api_server.database.create_import_job_run', create_run_mock, raising=False)
        monkeypatch.setattr('api_server.database.finalize_import_job_run', finalize_run_mock, raising=False)
        monkeypatch.setattr('api_server.database.finalize_import_job', finalize_job_mock, raising=False)
        
        response = client.post(
            "/api/parse",
            files={"file": ("alipay.csv", io.BytesIO(ALIPAY_SAMPLE.encode('utf-8')), "text/csv")}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['job_id'] == 'job_succeeded_1'
        assert data['run_id'] == 'run_succeeded_1'
        assert data['job_status'] == 'SUCCEEDED'
        assert data['review_required_count'] == 0
        create_run_mock.assert_called_once_with(
            'job_succeeded_1',
            step='parse_bill',
            input_summary={
                'filename': 'alipay.csv',
                'file_kind': 'csv',
                'source': 'unknown',
            },
            model_version=None,
            retry_count=0,
        )
        finalize_run_mock.assert_called_once_with(
            'run_succeeded_1',
            step='parse_bill',
            final_status='SUCCEEDED',
            output_summary={
                'total_transactions': 2,
                'persisted_count': 0,
                'review_required_count': 0,
                'failure_policy': 'no_retry_needed',
            },
            error_message=None,
        )

    def test_parse_returns_persist_transactions_import_job_run(self, monkeypatch):
        """/api/parse 中解析文件后保存到数据库时出错，execution record 应为 persist_transactions，并标记为 failed。"""
        create_job_mock = Mock(return_value="job_review_1")
        create_run_mock = Mock(return_value='run_review_1')
        finalize_run_mock = Mock()
        finalize_job_mock = Mock()
        clean_transactions = [
            {
                'date': '2026-04-01',
                'amount': -35.0,
                'category': 'dining',
                'description': '星巴克',
                'source': 'alipay',
                'type': 'expense',
                'requires_human_review': False,
            },
            {
                'date': '2026-04-01',
                'amount': -25.0,
                'category': 'transportation',
                'description': '滴滴出行',
                'source': 'alipay',
                'type': 'expense',
                'requires_human_review': False,
            },
        ]

        monkeypatch.setattr('api_server.database.is_database_enabled', lambda: True)
        monkeypatch.setattr('api_server.parse_csv_content', lambda _csv_text: clean_transactions)
        monkeypatch.setattr('api_server.database.create_import_job', create_job_mock, raising=False)
        monkeypatch.setattr('api_server.database.create_import_job_run', create_run_mock, raising=False)
        monkeypatch.setattr('api_server.database.update_import_job_status', lambda *args, **kwargs: None, raising=False)
        monkeypatch.setattr('api_server.database.save_transactions', lambda *args, **kwargs: (_ for _ in ()).throw(Exception("save failed")))
        monkeypatch.setattr('api_server.database.finalize_import_job_run', finalize_run_mock, raising=False)
        monkeypatch.setattr('api_server.database.finalize_import_job', finalize_job_mock, raising=False)

        response = client.post(
            "/api/parse",
            files={"file": ("review.csv", io.BytesIO(ALIPAY_SAMPLE.encode('utf-8')), "text/csv")}
        )

        assert response.status_code == 500
        data = response.json()
        assert data['detail'] == '解析失败: save failed'
        create_run_mock.assert_called_once_with(
            'job_review_1',
            step='parse_bill',
            input_summary={
                'filename': 'review.csv',
                'file_kind': 'csv',
                'source': 'unknown',
            },
            model_version=None,
            retry_count=0,
        )
        finalize_run_mock.assert_called_once_with(
            'run_review_1',
            step='persist_transactions',
            final_status='FAILED',
            output_summary={
                'total_transactions': 0,
                'persisted_count': 0,
                'review_required_count': 0,
                'failure_policy': 'mark_failed_and_stop',
            },
            error_message='save failed',
        )
        finalize_job_mock.assert_called_once_with(
            'job_review_1',
            status='FAILED',
            total_transactions=0,
            review_required_count=0,
            persisted_count=0,
            error_message='save failed',
        )

    def test_parse_returns_review_required_import_job_status(self, monkeypatch):
        """存在待审核交易时，/api/parse 应返回 REVIEW_REQUIRED 的 import job 状态。"""
        create_job_mock = Mock(return_value="job_review_1")
        create_run_mock = Mock(return_value='run_review_1')
        finalize_run_mock = Mock()
        finalize_job_mock = Mock()
        review_transactions = [{
            'date': '2026-04-09',
            'amount': -20.0,
            'category': 'other',
            'description': '未知商户',
            'source': 'alipay',
            'type': 'expense',
            'requires_human_review': True,
        }]

        monkeypatch.setattr('api_server.database.is_database_enabled', lambda: False)
        monkeypatch.setattr('api_server.parse_csv_content', lambda _csv_text: review_transactions)
        monkeypatch.setattr('api_server.database.create_import_job', create_job_mock, raising=False)
        monkeypatch.setattr('api_server.database.create_import_job_run', create_run_mock, raising=False)
        monkeypatch.setattr('api_server.database.finalize_import_job_run', finalize_run_mock, raising=False)
        monkeypatch.setattr('api_server.database.finalize_import_job', finalize_job_mock, raising=False)

        response = client.post(
            "/api/parse",
            files={"file": ("review.csv", io.BytesIO(ALIPAY_SAMPLE.encode('utf-8')), "text/csv")}
        )

        assert response.status_code == 200
        data = response.json()
        assert data['job_id'] == 'job_review_1'
        assert data['run_id'] == 'run_review_1'
        assert data['job_status'] == 'REVIEW_REQUIRED'
        assert data['review_required_count'] == 1
        assert data['persisted_count'] == 0
        assert data['transactions'][0]['import_job_id'] == 'job_review_1'
        finalize_run_mock.assert_called_once_with(
            'run_review_1',
            step='awaiting_human_review',
            final_status='REVIEW_REQUIRED',
            output_summary={
                'total_transactions': 1,
                'persisted_count': 0,
                'review_required_count': 1,
                'failure_policy': 'handoff_to_human_review',
            },
            error_message=None,
        )
        finalize_job_mock.assert_called_once_with(
            'job_review_1',
            status='REVIEW_REQUIRED',
            total_transactions=1,
            review_required_count=1,
            persisted_count=0,
            error_message=None,
        )

    def test_parse_marks_import_job_failed_on_exception(self, monkeypatch):
        """解析异常时，/api/parse 应把 import job 标记为 FAILED。"""
        create_job_mock = Mock(return_value='job_failed_1')
        create_run_mock = Mock(return_value='run_failed_1')
        finalize_run_mock = Mock()
        finalize_job_mock = Mock()

        monkeypatch.setattr('api_server.database.create_import_job', create_job_mock, raising=False)
        monkeypatch.setattr('api_server.database.create_import_job_run', create_run_mock, raising=False)
        monkeypatch.setattr('api_server.database.finalize_import_job_run', finalize_run_mock, raising=False)
        monkeypatch.setattr('api_server.database.finalize_import_job', finalize_job_mock, raising=False)
        monkeypatch.setattr('api_server.parse_csv_content', Mock(side_effect=ValueError('boom')))

        response = client.post(
            "/api/parse",
            files={"file": ("broken.csv", io.BytesIO(ALIPAY_SAMPLE.encode('utf-8')), "text/csv")}
        )

        assert response.status_code == 500
        assert '解析失败: boom' in response.json()['detail']
        finalize_run_mock.assert_called_once_with(
            'run_failed_1',
            step='parse_bill',
            final_status='FAILED',
            output_summary={
                'total_transactions': 0,
                'persisted_count': 0,
                'review_required_count': 0,
                'failure_policy': 'mark_failed_and_stop',
            },
            error_message='boom',
        )
        finalize_job_mock.assert_called_once_with(
            'job_failed_1',
            status='FAILED',
            total_transactions=0,
            review_required_count=0,
            persisted_count=0,
            error_message='boom',
        )

    def test_agent_monthly_summary_reads_from_database(self, monkeypatch):
        """Agent-facing 月度汇总接口应从 PostgreSQL 查询结构化财务快照。"""
        monkeypatch.setattr('api_server.database.is_database_enabled', lambda: True)
        monkeypatch.setattr('api_server.database.get_monthly_summary', lambda month: {
            "month": month,
            "summary": {
                "income": 10000.0,
                "expense": 105.0,
                "transfer": 0.0,
                "balance": 9895.0,
                "transaction_count": 3,
            },
            "category_expenses": [
                {"category": "dining", "amount": 80.0, "transaction_count": 2},
                {"category": "transportation", "amount": 25.0, "transaction_count": 1},
            ],
        })

        response = client.get("/api/agent/monthly-summary?month=2026-04")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["month"] == "2026-04"
        assert data["summary"]["expense"] == 105.0
        assert data["category_expenses"][0]["category"] == "dining"

    def test_agent_transactions_filters_and_returns_database_rows(self, monkeypatch):
        """Agent-facing 明细接口应支持按月、分类、来源、类型查询交易。"""
        captured = {}

        def fake_get_transactions(**kwargs):
            captured.update(kwargs)
            return [
                {
                    "id": "tx_dining_1",
                    "date": "2026-04-01",
                    "amount": -35.0,
                    "category": "dining",
                    "description": "星巴克",
                    "source": "alipay",
                    "type": "expense",
                    "transaction_type": "餐饮美食",
                    "confidence": 0.9,
                    "requires_human_review": False,
                }
            ]

        monkeypatch.setattr('api_server.database.is_database_enabled', lambda: True)
        monkeypatch.setattr('api_server.database.get_transactions', fake_get_transactions)

        response = client.get(
            "/api/agent/transactions?month=2026-04&category=dining&source=alipay&type=expense&limit=20"
        )

        assert response.status_code == 200
        assert captured == {
            "month": "2026-04",
            "category": "dining",
            "source": "alipay",
            "transaction_type": "expense",
            "limit": 20,
        }
        data = response.json()
        assert data["success"] is True
        assert data["count"] == 1
        assert data["transactions"][0]["description"] == "星巴克"
        assert data["transactions"][0]["amount"] == -35.0

    def test_correct_transaction_category_persists_rule_and_updates_database_row(self, monkeypatch):
        """人工审核纠偏时，应同时记住分类规则并写回对应 PostgreSQL 交易。"""
        saved_rule = {}
        updated_row = {}
        completed_job = {}

        monkeypatch.setattr('api_server.save_user_category', lambda description, category: saved_rule.update({
            'description': description,
            'category': category,
        }))
        monkeypatch.setattr('api_server.database.is_database_enabled', lambda: True)
        monkeypatch.setattr('api_server.database.update_transaction_category', lambda transaction_id, category: updated_row.update({
            'transaction_id': transaction_id,
            'category': category,
        }))
        monkeypatch.setattr('api_server.database.complete_import_job_if_review_finished', lambda job_id: completed_job.update({
            'job_id': job_id,
        }), raising=False)

        response = client.post(
            "/api/transactions/correct",
            json={
                "transaction_id": "tx_income_1",
                "description": "工资",
                "category": "收入",
                "job_id": "job_review_1",
            },
        )

        assert response.status_code == 200
        assert saved_rule == {
            'description': '工资',
            'category': 'income',
        }
        assert updated_row == {
            'transaction_id': 'tx_income_1',
            'category': 'income',
        }
        assert completed_job == {
            'job_id': 'job_review_1',
        }
        data = response.json()
        assert data["success"] is True
        assert data["normalized_category"] == "income"
        assert data["updated_transaction"] is True


class TestImportJobAPI:
    """测试 import job 查询接口。"""

    def test_get_latest_import_job_returns_job(self, monkeypatch):
        monkeypatch.setattr('api_server.database.is_database_enabled', lambda: True)
        monkeypatch.setattr('api_server.database.get_latest_import_job', lambda: {
            'id': 'job_latest_1',
            'status': 'REVIEW_REQUIRED',
            'source': 'alipay',
            'filename': 'alipay-april.csv',
            'total_transactions': 15,
            'review_required_count': 2,
            'persisted_count': 15,
            'error_message': None,
            'created_at': '2026-05-17T06:00:00Z',
            'started_at': '2026-05-17T06:00:01Z',
            'finished_at': '2026-05-17T06:00:03Z',
            'updated_at': '2026-05-17T06:00:03Z',
            'latest_run': {
                'id': 'run_latest_1',
                'job_id': 'job_latest_1',
                'step': 'awaiting_human_review',
                'final_status': 'REVIEW_REQUIRED',
                'input_summary': {'filename': 'alipay-april.csv'},
                'model_version': None,
                'output_summary': {'review_required_count': 2, 'failure_policy': 'handoff_to_human_review'},
                'error_message': None,
                'retry_count': 0,
                'started_at': '2026-05-17T06:00:01Z',
                'finished_at': '2026-05-17T06:00:03Z',
                'updated_at': '2026-05-17T06:00:03Z',
            },
        }, raising=False)

        response = client.get('/api/import-jobs/latest')

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['job']['id'] == 'job_latest_1'
        assert data['job']['status'] == 'REVIEW_REQUIRED'
        assert data['job']['review_required_count'] == 2
        assert data['job']['latest_run']['id'] == 'run_latest_1'
        assert data['job']['latest_run']['output_summary']['failure_policy'] == 'handoff_to_human_review'

    def test_get_latest_import_job_returns_null_when_empty(self, monkeypatch):
        monkeypatch.setattr('api_server.database.is_database_enabled', lambda: True)
        monkeypatch.setattr('api_server.database.get_latest_import_job', lambda: None, raising=False)

        response = client.get('/api/import-jobs/latest')

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['job'] is None

    def test_get_import_job_detail_returns_job(self, monkeypatch):
        monkeypatch.setattr('api_server.database.is_database_enabled', lambda: True)
        monkeypatch.setattr('api_server.database.get_import_job', lambda job_id: {
            'id': job_id,
            'status': 'SUCCEEDED',
            'source': 'wechat',
            'filename': 'wechat-may.xlsx',
            'total_transactions': 8,
            'review_required_count': 0,
            'persisted_count': 8,
            'error_message': None,
            'created_at': '2026-05-18T10:00:00Z',
            'started_at': '2026-05-18T10:00:01Z',
            'finished_at': '2026-05-18T10:00:02Z',
            'updated_at': '2026-05-18T10:00:02Z',
            'latest_run': {
                'id': 'run_succeeded_1',
                'job_id': job_id,
                'step': 'persist_transactions',
                'final_status': 'SUCCEEDED',
                'input_summary': {'filename': 'wechat-may.xlsx'},
                'model_version': None,
                'output_summary': {'persisted_count': 8, 'failure_policy': 'no_retry_needed'},
                'error_message': None,
                'retry_count': 0,
                'started_at': '2026-05-18T10:00:01Z',
                'finished_at': '2026-05-18T10:00:02Z',
                'updated_at': '2026-05-18T10:00:02Z',
            },
        }, raising=False)

        response = client.get('/api/import-jobs/job_succeeded_1')

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['job']['id'] == 'job_succeeded_1'
        assert data['job']['status'] == 'SUCCEEDED'
        assert data['job']['persisted_count'] == 8
        assert data['job']['latest_run']['step'] == 'persist_transactions'

    def test_get_import_job_detail_returns_404_when_missing(self, monkeypatch):
        monkeypatch.setattr('api_server.database.is_database_enabled', lambda: True)
        monkeypatch.setattr('api_server.database.get_import_job', lambda _job_id: None, raising=False)

        response = client.get('/api/import-jobs/job_missing_1')

        assert response.status_code == 404
        assert response.json()['detail'] == '未找到导入任务: job_missing_1'
