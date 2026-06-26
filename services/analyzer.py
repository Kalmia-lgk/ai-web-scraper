"""
数据分析与洞察服务

提供两个核心功能：
1. identify_numeric_columns — 自动识别 DataFrame 中的数值列
2. generate_ai_analysis_report — 调用 AI 撰写数据洞察分析报告
"""

import json
import re
import pandas as pd
from openai import OpenAI


def identify_numeric_columns(df: pd.DataFrame) -> tuple[list[str], pd.DataFrame]:
    """
    自动识别表格中哪些列是「数值型」的，并尝试将字符串类型的数字转为真正的数值。

    处理策略（按优先级）：
    1. 已经是 int/float 类型的列 → 直接保留
    2. 字符串列中包含 "15K-25K"、"￥15,000"、"30%" 等格式 → 清洗后转数值
    3. 纯文本列 → 跳过

    参数:
        df: Pandas DataFrame

    返回:
        tuple[数值列名列表, 处理后的DataFrame]
    """
    numeric_cols = []
    df_processed = df.copy()

    for col in df_processed.columns:
        # ---- 情况 1：列本身就是数值类型 ----
        if pd.api.types.is_numeric_dtype(df_processed[col]):
            numeric_cols.append(col)
            continue

        # ---- 情况 2：字符串类型，尝试从中提取数字 ----
        def _extract_number(text):
            """尝试从字符串中提取数值。支持 '15K-25K'→15, '￥15,000'→15000, '30%'→30"""
            if not isinstance(text, str):
                return None
            cleaned = text.replace(",", "").replace("，", "").replace("￥", "").replace("$", "").replace("%", "")
            match = re.search(r"[\d]+\.?[\d]*", cleaned)
            if match:
                try:
                    return float(match.group())
                except ValueError:
                    return None
            return None

        extracted = df_processed[col].apply(_extract_number)
        success_rate = extracted.notna().mean()

        if success_rate > 0.5:
            df_processed[col + "_数值"] = extracted
            numeric_cols.append(col + "_数值")

    return numeric_cols, df_processed


def generate_ai_analysis_report(
    data: list[dict],
    client: OpenAI,
    model: str,
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> tuple[str | None, str]:
    """
    将已提取的结构化数据再次发送给大模型，让它扮演「数据分析师」角色，
    用大白话为用户写一段数据洞察分析报告。

    参数:
        data:        AI 提取出的结构化数据列表
        client:      OpenAI 客户端对象
        model:       模型名称
        temperature: 创造性参数（写报告可以稍高）
        max_tokens:  最大输出 Token

    返回:
        tuple[报告文本或None, 状态信息]
    """
    data_json = json.dumps(data, ensure_ascii=False, indent=2)

    system_prompt = (
        "你是一位资深的数据分析师，擅长从结构化数据中发现有价值的洞察。\n"
        "用户会给你一份 JSON 格式的数据表格，请你：\n"
        "1. 快速浏览数据的整体情况（有多少条记录、涵盖哪些字段）\n"
        "2. 如果数据中包含数字（薪资、价格、销量等），进行简单的对比分析（最高/最低/平均值/分布规律）\n"
        "3. 用通俗易懂的大白话，给用户 2~3 条实用的数据洞察或建议\n"
        "4. 整段报告控制在 200 字左右，语言精炼，不说废话\n"
        "5. 用 Markdown 格式输出，适当使用小标题和列表增强可读性\n"
        "6. 不要复述原始数据，要给出「分析结论」而不是「数据摘要」"
    )

    user_prompt = (
        f"请分析以下结构化数据，写一段约 200 字的数据洞察报告：\n\n"
        f"```json\n{data_json}\n```\n\n"
        f"请直接输出分析报告，不要加「好的」「以下是报告」之类的客套话。"
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
        )
        report = response.choices[0].message.content
        if report is None:
            return None, "❌ AI 分析报告生成失败：模型返回了空内容。"

        return report, f"✅ 分析报告生成成功（{len(report)} 字符）"

    except Exception as e:
        return None, f"❌ AI 分析报告生成失败：{e}"
