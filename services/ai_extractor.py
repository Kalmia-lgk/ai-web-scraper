"""
AI 结构化数据提取服务

核心功能：
1. extract_structured_data — 将网页文本 + 用户需求发给大模型，强制返回 JSON 数组
2. smart_scan_page — 让 AI 先"看懂"页面，建议可提取的字段
3. _clean_ai_output_to_json — 强力清洗 AI 返回内容，确保是纯 JSON
"""

import json
import re
from openai import OpenAI


def extract_structured_data(
    web_text: str,
    user_requirement: str,
    client: OpenAI,
    model: str,
    temperature: float = 0.1,
    max_tokens: int = 4096,
    max_text_length: int = 20000,
) -> tuple[list[dict] | None, str]:
    """
    将清洗后的网页文本 + 用户需求发送给大模型，强制让它返回标准 JSON 数组。

    这是整个系统最核心的函数——提示词工程全在这里。

    参数:
        web_text:         清洗后的网页纯文本
        user_requirement: 用户用大白话写的数据提取需求
        client:           OpenAI 客户端对象
        model:            模型名称
        temperature:      创造性参数
        max_tokens:       最大输出 Token
        max_text_length:  网页文本最大截取长度（字符数）

    返回:
        tuple[数据列表或None, 状态信息]
    """
    # ========================================================================
    # 核心提示词设计 — 用极其严格的措辞确保 AI 只返回纯 JSON
    # ========================================================================
    system_prompt = (
        "你是一个专业的数据提取机器人。你的唯一职责是从网页文本中提取结构化数据。\n\n"
        "【核心工作流程】：\n"
        "1. 先快速浏览网页文本，判断页面主要内容属于什么类型：新闻列表？商品信息？职位招聘？\n"
        "   文章目录？数据报表？社交内容？还是其他？\n"
        "2. 如果用户的需求描述比较笼统（如「爬取数据」「帮我分析」「提取信息」），\n"
        "   你就发挥主动性，把页面中最明显、最核心的结构化数据找出来提取。\n"
        "3. 如果用户明确指定了字段（如「职位名称、薪资」），就精准提取这些字段。\n\n"
        "【关键原则——宁可多提取，不要返回空数组】：\n"
        "• 页面里有任何列表、表格、分类信息、标题集合 → 都必须提取出来\n"
        "• 即使页面看起来主要是文章正文，也要把「标题、段落摘要、关键数字」整理成结构化数据\n"
        "• 返回空数组 [] 只允许在一种情况：页面完全是空白或乱码，没有任何人类可读内容\n\n"
        "【你必须严格遵守的输出格式规则】：\n"
        "1. 你【只能】返回一个合法的 JSON 数组，数组的每个元素是一个 JSON 对象（字典）。\n"
        "2. 绝对不允许在 JSON 之外添加任何文字——没有问候语、没有解释、没有Markdown代码块标记。\n"
        "3. 你的回复的第一个字符必须是 '['，最后一个字符必须是 ']'。\n"
        "4. 每个对象的键（key）必须是简洁的中文列名（2-5个字），所有对象的键必须完全一致。\n"
        "5. 如果某条数据的某个字段缺失，用空字符串 \"\" 填充，不要省略该字段。\n\n"
        "【输出格式示例】：\n"
        '提取职位信息 → [{"职位名称": "Python工程师", "薪资": "15K-25K", "公司": "某某科技"}]\n'
        '提取文章列表 → [{"标题": "xxx", "发布时间": "2024-01-01", "摘要": "xxx"}]\n'
        '提取商品信息 → [{"商品名": "xxx", "价格": "99元", "销量": "1000+"}]\n\n'
        "再次强调：只返回 JSON 数组本身。你的回复必须以 [ 开头，以 ] 结尾。不要返回空数组，除非页面真的没有任何内容。"
    )

    # ---- 用户消息：网页内容 + 用户需求 ----
    if len(web_text) > max_text_length:
        truncated_text = web_text[:max_text_length]
        truncation_notice = (
            f"\n\n⚠️ 【提示】原始网页共 {len(web_text):,} 字符，"
            f"已截取前 {max_text_length:,} 字符发送给 AI 分析。"
        )
    else:
        truncated_text = web_text
        truncation_notice = ""

    user_prompt = (
        f"【用户的数据提取需求】：\n{user_requirement}\n\n"
        f"【网页纯文本内容】：\n{truncated_text}\n\n"
        f"请严格按照系统指令，从以上网页内容中提取用户所需的数据，"
        f"只返回 JSON 数组，不要任何其他内容。"
    )

    # ---- 调用大模型 API ----
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
        raw_output = response.choices[0].message.content
        if raw_output is None:
            return None, "❌ AI 返回了空内容，请重试或更换模型。"

    except Exception as e:
        return None, f"❌ API 调用失败：{e}"

    # ---- 清洗 AI 返回的内容，确保是纯净的 JSON ----
    clean_json_str = _clean_ai_output_to_json(raw_output)

    # ---- 尝试解析 JSON ----
    try:
        data = json.loads(clean_json_str)
    except json.JSONDecodeError as e:
        debug_info = (
            f"❌ AI 返回的内容不是合法 JSON。\n"
            f"JSON 解析错误：{e}\n\n"
            f"--- AI 原始返回（前 500 字符）---\n"
            f"{raw_output[:500]}"
        )
        return None, debug_info

    # ---- 校验数据格式 ----
    if not isinstance(data, list):
        return None, (
            f"❌ AI 返回的不是 JSON 数组，而是 {type(data).__name__}。\n"
            f"原始返回（前 300 字符）：{raw_output[:300]}"
        )

    if len(data) == 0:
        return [], "⚠️ AI 未在网页中找到符合要求的数据（返回了空数组）。请检查需求描述是否准确。"

    if not all(isinstance(item, dict) for item in data):
        return None, "❌ AI 返回的数组元素不全是字典（对象），格式异常。"

    # ---- 成功返回 ----
    record_count = len(data)
    column_names = list(data[0].keys())
    status = (
        f"✅ AI 成功提取 {record_count} 条数据！"
        f"列名：{'、'.join(column_names)}"
    )
    if truncation_notice:
        status += truncation_notice

    return data, status


def smart_scan_page(
    web_text: str,
    client: OpenAI,
    model: str,
    max_scan_chars: int = 8000,
) -> tuple[str | None, str]:
    """
    让 AI 快速扫描网页内容，告诉用户「这个页面有哪些数据可以提取」。

    参数:
        web_text:       清洗后的网页纯文本
        client:         OpenAI 客户端
        model:          模型名称
        max_scan_chars: 用于扫描的最大字符数

    返回:
        tuple[扫描结果（Markdown）或None, 状态信息]
    """
    scan_text = web_text[:max_scan_chars]

    system_prompt = (
        "你是一个网页内容分析专家。用户会给你一段网页的纯文本内容，"
        "请你快速判断这个页面主要包含什么类型的信息，并告诉用户可以提取哪些结构化数据。\n\n"
        "请用以下格式回复（严格遵循）：\n"
        "第一行：页面类型（如：职位列表页 / 新闻列表页 / 商品展示页 / 文章正文 / 数据表格 / 论坛帖子 / 其他）\n"
        "第二行起：用列表列出「可以提取的数据字段」，每行一个，格式为「- 字段名：说明」\n"
        "最后：给一句大白话的「建议提取指令」，用户可以直接复制到输入框里使用\n\n"
        "要求：简洁、实用、可操作。总回复控制在 150 字以内。"
    )

    user_prompt = (
        f"请分析以下网页内容，告诉用户有哪些数据可以提取：\n\n"
        f"```\n{scan_text}\n```"
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=512,
            stream=False,
        )
        result = response.choices[0].message.content
        if result is None:
            return None, "❌ 智能扫描失败：AI 返回了空内容。"
        return result, "✅ 智能扫描完成"
    except Exception as e:
        return None, f"❌ 智能扫描失败：{e}"


def _clean_ai_output_to_json(raw: str) -> str:
    """
    清洗 AI 的原始返回字符串，去掉各种常见噪音：
    - Markdown 代码块标记（```json ... ``` 或 ``` ... ```）
    - 前后的客套话（如"好的，以下是提取结果："）
    - 多余空白

    策略：找到第一个 '[' 和最后一个 ']'，只取中间部分。
    """
    # 第 1 步：去掉 Markdown 代码块标记
    md_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
    if md_match:
        raw = md_match.group(1)

    # 第 2 步：找到第一个 '[' 和最后一个 ']'，只取中间部分
    first_bracket = raw.find("[")
    last_bracket = raw.rfind("]")

    if first_bracket == -1 or last_bracket == -1:
        return raw

    clean = raw[first_bracket: last_bracket + 1]
    clean = clean.strip()

    return clean
