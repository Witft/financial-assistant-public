"""
Financial Assistant MCP Server
HTTP 包装层：将 FastAPI 的 Agent 查询接口暴露为 MCP 工具。

使用方式（stdio）：
    python mcp_server.py

依赖环境变量：
    FINANCIAL_API_URL  — FastAPI 服务地址，如 http://127.0.0.1:8000
                         本地开发默认 http://127.0.0.1:8000
                         ECS 部署默认 http://127.0.0.1:8080
"""

import os
import json
import httpx
from typing import Annotated, Literal, Optional

from mcp.server.fastmcp import FastMCP
from pydantic import Field

# ═══════════════════════════════════════════════════════════
# 初始化配置
# ═══════════════════════════════════════════════════════════
# FINANCIAL_API_URL: FastAPI 后端地址
#   - 本地开发: http://127.0.0.1:8000
#   - ECS 部署: http://127.0.0.1:8080
API_BASE = os.environ.get("FINANCIAL_API_URL", "http://127.0.0.1:8000")
TIMEOUT = 30.0  # HTTP 请求超时（秒）

SummaryMonth = Annotated[
    str,
    Field(
        description="月份，格式 YYYY-MM，例如 2026-04",
        pattern="^[0-9]{4}-(0[1-9]|1[0-2])$",
    ),
]
QueryMonth = Annotated[
    str,
    Field(description="月份，格式 YYYY-MM", pattern="^[0-9]{4}-(0[1-9]|1[0-2])$"),
]
Category = Annotated[str, Field(description="分类过滤，如 dining, shopping, healthcare 等")]
Source = Annotated[Literal["alipay", "wechat", "ccb"], Field(description="来源过滤")]
TransactionType = Annotated[
    Literal["expense", "income", "transfer"], Field(description="类型过滤")
]
Limit = Annotated[
    int, Field(description="返回条数上限，默认 50，最大 500", ge=1, le=500)
]

# ═══════════════════════════════════════════════════════════
# MCP Server 实例化
# FastMCP 是 MCP 协议的 Python 实现，负责：
#   1. 向 AI Agent 暴露工具列表（通过 instructions）
#   2. 接收 AI 的工具调用请求，分发到对应的 Python 函数
#   3. 将函数返回值传回给 AI
# ═══════════════════════════════════════════════════════════
mcp = FastMCP(
    name="financial_assistant",
    instructions="个人财务助手 MCP 服务。\n"
    "工具：monthly_summary（月度汇总）、query_transactions（交易明细）、list_months（已上传月份）。\n"
    "所有返回均为 JSON 字符串。",
)


# ═══════════════════════════════════════════════════════════
# 内部辅助函数：HTTP 请求包装器
# 统一处理连接错误、超时、4xx/5xx 响应，转换为 RuntimeError
# 这样上层逻辑不需要逐个处理这些异常情况
# ═══════════════════════════════════════════════════════════


def _get(path: str, params: Optional[dict] = None) -> dict:
    """
    对 FastAPI 发起 GET 请求，统一错误处理。

    错误转换规则：
        ConnectError  → RuntimeError("无法连接到 FastAPI 服务")
        TimeoutException → RuntimeError("API 请求超时")
        4xx/5xx       → RuntimeError("API 错误 [状态码] detail")
    """
    url = f"{API_BASE}{path}"
    with httpx.Client(timeout=TIMEOUT) as client:
        try:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            # 4xx/5xx，尝试从 JSON body 提取 detail
            try:
                detail = exc.response.json().get("detail", str(exc))
            except Exception:
                detail = str(exc)
            raise RuntimeError(f"API 错误 [{exc.response.status_code}] {detail}")
        except httpx.ConnectError:
            raise RuntimeError(
                f"无法连接到 FastAPI 服务 ({API_BASE})，请确认服务已启动且 FINANCIAL_API_URL 配置正确"
            )
        except httpx.TimeoutException:
            raise RuntimeError(f"API 请求超时 ({url})，请检查数据库连接")


def _post(path: str, data: dict) -> dict:
    """对 FastAPI 发起 POST 请求，请求体为 JSON。"""
    url = f"{API_BASE}{path}"
    with httpx.Client(timeout=TIMEOUT) as client:
        try:
            resp = client.post(url, json=data)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            try:
                detail = exc.response.json().get("detail", str(exc))
            except Exception:
                detail = str(exc)
            raise RuntimeError(f"API 错误 [{exc.response.status_code}] {detail}")
        except httpx.ConnectError:
            raise RuntimeError(
                f"无法连接到 FastAPI 服务 ({API_BASE})，请确认服务已启动"
            )
        except httpx.TimeoutException:
            raise RuntimeError(f"API 请求超时 ({url})")


# ═══════════════════════════════════════════════════════════
# MCP 工具定义
# 每个 @mcp.tool() 装饰的函数都会暴露给 AI Agent 调用
# 返回值必须是字符串（JSON 格式），因为 MCP 协议规定工具返回文本
# ═══════════════════════════════════════════════════════════

@mcp.tool(
    title="查询月度汇总",
    description="查询指定月份的财务收支汇总，返回该月总收入、总支出、净余额、交易笔数，以及各分类支出明细。",
)
def monthly_summary(month: SummaryMonth) -> str:
    # Preserve the legacy direct-call contract: it accepted any YYYY-MM-shaped
    # value and delegated semantic month validation to the API.
    if not month or len(month) != 7 or month[4] != "-":
        raise ValueError("month 参数格式错误，请使用 YYYY-MM 格式，例如 2026-04")

    data = _get("/api/agent/monthly-summary", params={"month": month})

    if not data.get("success"):
        raise RuntimeError(f"查询失败：{data.get('detail', '未知错误')}")

    # 将 API 返回的字典序列化为带缩进的 JSON 字符串
    # ensure_ascii=False: 保留中文不转义
    # indent=2: 格式化输出，方便调试和 AI 解析
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool(
    title="查询交易明细",
    description="按条件筛选查询交易明细，支持按分类、来源、类型过滤，返回交易列表。",
)
def query_transactions(
    month: QueryMonth,
    category: Category = None,
    source: Source = None,
    transaction_type: TransactionType = None,
    limit: Limit = 50,
) -> str:
    if not month or len(month) != 7 or month[4] != "-":
        raise ValueError("month 参数格式错误，请使用 YYYY-MM 格式，例如 2026-04")

    if limit < 1 or limit > 500:
        raise ValueError("limit 必须在 1-500 之间")

    # 按需构造查询参数，避免传递 None 值
    params = {"month": month, "limit": limit}
    if category:
        params["category"] = category
    if source:
        if source not in ("alipay", "wechat", "ccb"):
            raise ValueError("source 必须是 alipay / wechat / ccb 之一")
        params["source"] = source
    if transaction_type:
        if transaction_type not in ("expense", "income", "transfer"):
            raise ValueError("transaction_type 必须是 expense / income / transfer 之一")
        params["type"] = transaction_type

    data = _get("/api/agent/transactions", params=params)

    if not data.get("success"):
        raise RuntimeError(f"查询失败：{data.get('detail', '未知错误')}")

    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool(
    title="查询已上传月份列表",
    description="查询数据库中已有交易记录的月份列表，返回 YYYY-MM 格式的月份数组，升序排列。",
)
def list_months() -> str:
    data = _get("/api/agent/months")
    return json.dumps(data, ensure_ascii=False, indent=2)


# ═══════════════════════════════════════════════════════════
# 启动入口
# 以 stdio 模式运行 MCP Server：
#   - MCP 协议通过标准输入/输出传递消息（不是 HTTP）
#   - Claude Code 或其他 MCP Client 通过 stdio 与此进程通信
#   - 适合本地开发或进程内集成（如 claude-code MCP server 配置）
# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    mcp.run()
