#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
财务助手 API 调用封装 - 调用 FastAPI 后端的完整分析流程
上传 CSV → 解析 → AI 诊断，一站式完成
"""

import sys
import os
import json
import argparse
import httpx
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# ==========================================
# FastAPI 后端配置
# ==========================================
API_BASE_URL = os.getenv("FINANCIAL_API_URL") or "http://localhost:8000"


def parse_bill_file(file_path: str) -> dict:
    """
    调用 /api/parse 上传并解析账单 CSV 文件
    
    Returns:
        包含 transactions 列表的字典
    """
    if not os.path.exists(file_path):
        return {"success": False, "error": f"文件不存在: {file_path}"}
    
    # TODO: 只支持csv是不是太局限了
    if not file_path.endswith('.csv'):
        return {"success": False, "error": "只支持 CSV 文件"}
    
    try:
        with httpx.Client(timeout=30.0) as client:
            with open(file_path, 'rb') as f:
                files = {'file': (os.path.basename(file_path), f, 'text/csv')}
                response = client.post(f"{API_BASE_URL}/api/parse", files=files)
                response.raise_for_status()
                result = response.json()
                
                if result.get("success"):
                    return {
                        "success": True,
                        "transactions": result.get("transactions", []),
                        "message": result.get("message", "")
                    }
                else:
                    return {"success": False, "error": result.get("message", "解析失败")}
                    
    except httpx.ConnectError:
        return {"success": False, "error": f"无法连接到 API 服务 ({API_BASE_URL})"}
    except Exception as e:
        return {"success": False, "error": f"API 调用失败: {str(e)}"}


def analyze_finances(transactions: list) -> str:
    """
    调用 /api/analyze 获取 AI 财务诊断
    
    Args:
        transactions: 解析后的交易列表
        
    Returns:
        AI 生成的诊断报告（Markdown 格式）
    """
    # 从 transactions 计算汇总数据
    total_income = 0.0
    total_expense = 0.0
    category_totals = {}
    all_transactions = []
    
    for t in transactions:
        amount = float(t.get('amount', 0))
        category = t.get('category', 'other')
        
        if t.get('type') == 'income':
            total_income += abs(amount)
        elif t.get('type') == 'expense':
            total_expense += abs(amount)
            if category not in category_totals:
                category_totals[category] = 0.0
            category_totals[category] += abs(amount)
        
        all_transactions.append({
            "date": t.get('date', ''),
            "category": category,
            "amount": f"{abs(amount):.2f}",
            "desc": t.get('description', ''),
            "type": t.get('type', '')
        })
    
    balance = total_income - total_expense
    
    # 按金额排序，取前5大分类
    sorted_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)[:5]
    top_categories = []
    for cat, amount in sorted_categories:
        pct = (amount / total_expense * 100) if total_expense > 0 else 0
        top_categories.append({
            "name": cat,
            "amount": f"{amount:.2f}",
            "pct": f"{pct:.0f}%"
        })
    
    # 按金额排序，取前5大支出
    expense_transactions = [t for t in all_transactions if t.get('type') == 'expense']
    top_expenses = sorted(expense_transactions, key=lambda x: float(x['amount']), reverse=True)[:5]
    
    # 构建 API 请求体
    payload = {
        "financial_data": {
            "month": "本月",
            "summary": {
                "income": f"{total_income:.2f}",
                "expense": f"{total_expense:.2f}",
                "balance": f"{balance:.2f}"
            },
            "top_categories": top_categories,
            "top_expenses": top_expenses
        }
    }
    
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{API_BASE_URL}/api/analyze",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            result = response.json()
            
            if result.get("success"):
                return result.get("result", "分析结果为空")
            else:
                return f"API 返回失败: {result}"
                
    except httpx.ConnectError:
        return f"错误: 无法连接到 API 服务 ({API_BASE_URL})"
    except httpx.TimeoutException:
        return "错误: API 请求超时"
    except Exception as e:
        return f"API 调用失败: {str(e)}"


def parse_args() -> argparse.Namespace:
    """解析命令行参数，默认保持原来的一条龙分析流程。"""
    parser = argparse.ArgumentParser(
        description="调用 FastAPI 后端解析账单，或继续生成 AI 财务诊断报告"
    )
    parser.add_argument(
        "--mode",
        choices=("parse", "analyze"),
        default="analyze",
        help="parse 只输出交易 JSON；analyze 解析后继续生成诊断报告（默认）"
    )
    parser.add_argument("file_path", help="账单 CSV 文件路径")
    return parser.parse_args()


def main():
    """主函数：按模式完成解析或解析 + 诊断"""
    args = parse_args()
    file_path = args.file_path

    # Step 1: 解析账单
    print(f"📁 文件: {file_path}")
    print(f"🔗 API: {API_BASE_URL}")
    print()
    print("📊 解析账单中...")

    parse_result = parse_bill_file(file_path)
    
    if not parse_result.get("success"):
        print(f"❌ 解析失败: {parse_result.get('error')}")
        sys.exit(1)
    
    transactions = parse_result.get("transactions", [])

    if args.mode == "parse":
        print(json.dumps(transactions, indent=2, ensure_ascii=False))
        sys.exit(0)

    print(f"✅ 成功解析 {len(transactions)} 笔交易")
    print()
    
    # Step 2: AI 诊断
    print("🤖 AI 诊断中...")
    diagnosis = analyze_finances(transactions)
    print()
    print("=" * 50)
    if isinstance(diagnosis, dict):
        print(json.dumps(diagnosis, indent=2, ensure_ascii=False))
    else:
        print(diagnosis)
    print("=" * 50)


if __name__ == "__main__":
    main()
