"""
测试 Financial MCP Server

运行方式（在 backend 目录下）：
    pytest tests/test_mcp_server.py -v

测试策略：Mock httpx，验证 MCP server 的请求构造和参数校验逻辑。
"""

import asyncio
from copy import deepcopy
import json
from unittest.mock import patch, MagicMock

import pytest
from mcp.server.fastmcp.exceptions import ToolError

# 被测模块
import mcp_server

# Frozen from the input_schema AST literals in the read-only original at
# bccdf654710854e96a1156fa5009bedf3910d6f7. MCP clients consume these
# dictionaries as a contract, so equality (not a subset) is intentional.
ORIGINAL_INPUT_SCHEMAS = {
    "monthly_summary": {
        "type": "object",
        "properties": {
            "month": {
                "type": "string",
                "description": "月份，格式 YYYY-MM，例如 2026-04",
                "pattern": "^[0-9]{4}-(0[1-9]|1[0-2])$",
            }
        },
        "required": ["month"],
    },
    "query_transactions": {
        "type": "object",
        "properties": {
            "month": {
                "type": "string",
                "description": "月份，格式 YYYY-MM",
                "pattern": "^[0-9]{4}-(0[1-9]|1[0-2])$",
            },
            "category": {
                "type": "string",
                "description": "分类过滤，如 dining, shopping, healthcare 等",
            },
            "source": {
                "type": "string",
                "description": "来源过滤",
                "enum": ["alipay", "wechat", "ccb"],
            },
            "transaction_type": {
                "type": "string",
                "description": "类型过滤",
                "enum": ["expense", "income", "transfer"],
            },
            "limit": {
                "type": "integer",
                "description": "返回条数上限，默认 50，最大 500",
                "default": 50,
                "minimum": 1,
                "maximum": 500,
            },
        },
        "required": ["month"],
    },
    "list_months": {"type": "object", "properties": {}},
}


# The user-approved compatibility delta is exhaustive.  The frozen legacy
# dictionaries above remain the baseline, and these are the only additions
# FastMCP/Pydantic is permitted to advertise.
APPROVED_SCHEMA_ADDITIONS = {
    "monthly_summary": {
        "title": "monthly_summaryArguments",
        "properties": {"month": {"title": "Month"}},
    },
    "query_transactions": {
        "title": "query_transactionsArguments",
        "properties": {
            "month": {"title": "Month"},
            "category": {"title": "Category", "default": None},
            "source": {"title": "Source", "default": None},
            "transaction_type": {"title": "Transaction Type", "default": None},
            "limit": {"title": "Limit"},
        },
    },
    "list_months": {"title": "list_monthsArguments"},
}


def approved_schema_contract():
    """Apply precisely the approved additions to the frozen legacy schema."""
    expected = deepcopy(ORIGINAL_INPUT_SCHEMAS)
    for tool_name, additions in APPROVED_SCHEMA_ADDITIONS.items():
        if "title" in additions:
            expected[tool_name]["title"] = additions["title"]
        for property_name, property_additions in additions.get("properties", {}).items():
            expected[tool_name]["properties"][property_name].update(property_additions)
    return expected


class TestMCPToolRegistration:
    """Supported FastMCP registration has one narrow approved schema delta."""

    def test_advertised_input_schemas_equal_frozen_contract_plus_only_approved_additions(self):
        tools = {tool.name: tool for tool in asyncio.run(mcp_server.mcp.list_tools())}

        assert set(tools) == set(ORIGINAL_INPUT_SCHEMAS)
        # Equality is intentional: it rejects changed or removed legacy fields,
        # unexpected titles/defaults, and all other unapproved additions.
        assert {name: tools[name].inputSchema for name in ORIGINAL_INPUT_SCHEMAS} == approved_schema_contract()


class TestFastMCPDispatch:
    """Exercise FastMCP validation/dispatch without allowing real HTTP I/O."""

    def test_optional_fields_omitted_dispatches_with_mocked_http_adapter(self):
        with patch.object(
            mcp_server,
            "_get",
            return_value={"success": True, "count": 0, "transactions": []},
        ) as mock_get:
            result = asyncio.run(
                mcp_server.mcp.call_tool("query_transactions", {"month": "2026-04"})
            )

        assert result
        mock_get.assert_called_once_with(
            "/api/agent/transactions", params={"month": "2026-04", "limit": 50}
        )

    def test_explicit_null_optional_fields_are_rejected_before_http_dispatch(self):
        with patch.object(mcp_server, "_get") as mock_get:
            with pytest.raises(ToolError, match="validation errors"):
                asyncio.run(
                    mcp_server.mcp.call_tool(
                        "query_transactions",
                        {
                            "month": "2026-04",
                            "category": None,
                            "source": None,
                            "transaction_type": None,
                        },
                    )
                )

        mock_get.assert_not_called()


class TestMonthlySummary:
    """工具 monthly_summary 的参数校验和请求构造测试"""

    def test_valid_month(self):
        """合法月份格式应构造正确请求"""
        with patch.object(mcp_server, "_get") as mock_get:
            mock_get.return_value = {
                "success": True,
                "month": "2026-04",
                "summary": {"income": 1000.0, "expense": 800.0, "balance": 200.0, "transaction_count": 15},
                "category_expenses": [],
            }
            result = mcp_server.monthly_summary("2026-04")
            mock_get.assert_called_once_with("/api/agent/monthly-summary", params={"month": "2026-04"})
            data = json.loads(result)
            assert data["success"] is True
            assert data["summary"]["income"] == 1000.0

    def test_direct_call_preserves_original_month_permissiveness(self):
        """The legacy direct-call wrapper forwarded YYYY-13 unchanged to the API."""
        with patch.object(mcp_server, "_get", return_value={"success": True}) as mock_get:
            result = mcp_server.monthly_summary("2026-13")

        mock_get.assert_called_once_with("/api/agent/monthly-summary", params={"month": "2026-13"})
        assert json.loads(result) == {"success": True}

    def test_invalid_month_format(self):
        """非法月份格式应抛出 ValueError"""
        with pytest.raises(ValueError, match="YYYY-MM"):
            mcp_server.monthly_summary("2026/04")
        with pytest.raises(ValueError, match="YYYY-MM"):
            mcp_server.monthly_summary("2026-4")
        with pytest.raises(ValueError, match="YYYY-MM"):
            mcp_server.monthly_summary("")

    def test_api_returns_failure(self):
        """API 返回 success=False 时应抛出 RuntimeError"""
        with patch.object(mcp_server, "_get") as mock_get:
            mock_get.return_value = {"success": False, "detail": "数据库未配置"}
            with pytest.raises(RuntimeError, match="查询失败"):
                mcp_server.monthly_summary("2026-04")


class TestQueryTransactions:
    """工具 query_transactions 的参数校验和请求构造测试"""

    def test_only_required_param(self):
        """仅传必填参数 month"""
        with patch.object(mcp_server, "_get") as mock_get:
            mock_get.return_value = {"success": True, "count": 3, "transactions": []}
            mcp_server.query_transactions("2026-04")
            mock_get.assert_called_once_with(
                "/api/agent/transactions",
                params={"month": "2026-04", "limit": 50},
            )

    def test_all_optional_params(self):
        """传入所有可选参数"""
        with patch.object(mcp_server, "_get") as mock_get:
            mock_get.return_value = {"success": True, "count": 1, "transactions": []}
            mcp_server.query_transactions(
                month="2026-04",
                category="dining",
                source="alipay",
                transaction_type="expense",
                limit=20,
            )
            mock_get.assert_called_once_with(
                "/api/agent/transactions",
                params={
                    "month": "2026-04",
                    "category": "dining",
                    "source": "alipay",
                    "type": "expense",
                    "limit": 20,
                },
            )

    def test_invalid_source(self):
        """source 参数非法值"""
        with pytest.raises(ValueError, match="alipay / wechat / ccb"):
            mcp_server.query_transactions("2026-04", source="invalid")

    def test_invalid_type(self):
        """transaction_type 参数非法值"""
        with pytest.raises(ValueError, match="expense / income / transfer"):
            mcp_server.query_transactions("2026-04", transaction_type="unknown")

    def test_invalid_limit(self):
        """limit 超出范围"""
        with pytest.raises(ValueError, match="1-500"):
            mcp_server.query_transactions("2026-04", limit=0)
        with pytest.raises(ValueError, match="1-500"):
            mcp_server.query_transactions("2026-04", limit=501)


class TestListMonths:
    """工具 list_months 测试"""

    def test_returns_month_list(self):
        with patch.object(mcp_server, "_get") as mock_get:
            mock_get.return_value = {"success": True, "months": ["2026-01", "2026-03", "2026-04"]}
            result = mcp_server.list_months()
            mock_get.assert_called_once_with("/api/agent/months")
            data = json.loads(result)
            assert data["months"] == ["2026-01", "2026-03", "2026-04"]


class TestErrorHandling:
    """错误处理测试"""

    def test_connect_error(self):
        """无法连接到 FastAPI"""
        with patch.object(mcp_server, "_get") as mock_get:
            mock_get.side_effect = RuntimeError("无法连接到 FastAPI 服务")
            with pytest.raises(RuntimeError, match="无法连接到 FastAPI"):
                mcp_server.monthly_summary("2026-04")

    def test_timeout_error(self):
        """请求超时"""
        with patch.object(mcp_server, "_get") as mock_get:
            mock_get.side_effect = RuntimeError("API 请求超时")
            with pytest.raises(RuntimeError, match="超时"):
                mcp_server.monthly_summary("2026-04")
