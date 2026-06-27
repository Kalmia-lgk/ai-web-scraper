"""
================================================================================
  AI 全自动网页抓取与可视化分析看板
  作者：你的技术导师
  功能：网页抓取 → AI 结构化提取 JSON → Pandas 表格 → 自动图表 → AI 分析报告
  运行方式：在终端执行 `streamlit run app.py`
================================================================================
"""

import os
import json
import streamlit as st
import pandas as pd
from openai import OpenAI

from services.scraper import fetch_and_clean_html, check_robots_txt
from services.ai_extractor import extract_structured_data, smart_scan_page
from services.analyzer import identify_numeric_columns, generate_ai_analysis_report

# ============================================================================
# 第一部分：页面初始化配置
# ============================================================================

st.set_page_config(
    page_title="AI 全自动网页抓取与分析看板",
    page_icon="🕷️",
    layout="wide",
)

st.title("🕷️ AI 全自动网页抓取与可视化分析看板")
st.caption("输入任意网页 URL，用大白话告诉 AI 你想提取什么数据，剩下的交给我。")

# ============================================================================
# 第二部分：侧边栏 — API 配置
# ============================================================================

with st.sidebar:
    st.header("⚙️ 大模型 API 配置")

    api_base_url = st.text_input(
        label="API Base URL（接口地址）",
        value="https://api.deepseek.com",
        help="兼容 OpenAI 格式的 API 地址。例如：\n"
             "• DeepSeek: https://api.deepseek.com\n"
             "• SiliconFlow: https://api.siliconflow.cn/v1\n"
             "• 本地 Ollama: http://localhost:11434/v1",
    )

    api_key = st.text_input(
        label="API Key（密钥）",
        value=os.environ.get("DEEPSEEK_API_KEY", ""),
        type="password",
        help="留空则自动使用环境变量 DEEPSEEK_API_KEY",
    )

    model_name = st.text_input(
        label="模型名称（Model Name）",
        value="deepseek-chat",
        help="例如：deepseek-chat / deepseek-reasoner / gpt-4o 等",
    )

    st.divider()

    st.caption("高级参数（一般不用改）")
    temperature = st.slider(
        label="Temperature（创造性）",
        min_value=0.0,
        max_value=2.0,
        value=0.1,
        step=0.1,
        help="越低越严谨（适合数据提取），越高越有创意（适合写报告）",
    )
    max_tokens = st.slider(
        label="Max Tokens（最大输出长度）",
        min_value=512,
        max_value=16384,
        value=4096,
        step=512,
        help="限制 AI 单次回复的最大 Token 数",
    )
    max_text_length_slider = st.slider(
        label="网页文本截取长度（字符数）",
        min_value=2000,
        max_value=50000,
        value=20000,
        step=2000,
        help="发送给 AI 的网页文本最大长度。网页越大截得越多。",
    )
    robots_check_enabled = st.checkbox(
        label="🤖 启用 robots.txt 合规检查（推荐开启）",
        value=True,
        help="开启后会自动检查目标网站的 robots.txt，如果禁止爬取会拒绝抓取。",
    )

    st.divider()

    debug_mode = st.toggle(
        label="🐛 调试模式（显示 AI 原始返回内容）",
        value=False,
    )

# ============================================================================
# 第三部分：初始化 Session State
# ============================================================================

if "extracted_data" not in st.session_state:
    st.session_state.extracted_data = None
if "web_text" not in st.session_state:
    st.session_state.web_text = ""
if "fetch_status" not in st.session_state:
    st.session_state.fetch_status = ""
if "df_processed" not in st.session_state:
    st.session_state.df_processed = None
if "numeric_cols" not in st.session_state:
    st.session_state.numeric_cols = []
if "ai_report" not in st.session_state:
    st.session_state.ai_report = None
if "report_status" not in st.session_state:
    st.session_state.report_status = ""
if "debug_truncated_text" not in st.session_state:
    st.session_state.debug_truncated_text = ""
if "debug_ai_raw_output" not in st.session_state:
    st.session_state.debug_ai_raw_output = ""
if "robots_status" not in st.session_state:
    st.session_state.robots_status = ""
if "scan_result" not in st.session_state:
    st.session_state.scan_result = None
if "retry_used" not in st.session_state:
    st.session_state.retry_used = False

# ============================================================================
# 第四部分：主界面布局 — 用户输入区
# ============================================================================

st.header("📥 第一步：输入抓取目标")

col1, col2 = st.columns([1, 1])

with col1:
    target_url = st.text_input(
        label="🔗 请输入要抓取的网页 URL",
        placeholder="例如：https://www.zhipin.com/web/geek/job?query=Python",
        value="",
        key="input_url_empty",
    )

with col2:
    extraction_requirement = st.text_area(
        label="💬 用大白话描述你想提取什么数据",
        placeholder=(
            "✏️ 越具体越好！比如：\n"
            "• 「提取所有职位名称、公司名、薪资待遇和工作地点」\n"
            "• 「提取所有商品的名称、价格和销量」\n"
            "• 「提取所有文章的标题、作者和发布时间」\n\n"
            "💡 如果不确定该写什么，先填 URL 然后点下面的「🔍 智能扫描」按钮！"
        ),
        height=140,
        key="input_requirement",
    )

# --- 智能扫描按钮 ---
scan_col1, scan_col2 = st.columns([1, 3])
with scan_col1:
    scan_button = st.button(
        label="🔍 智能扫描",
        help="让 AI 先分析网页内容，告诉你有哪些数据可以提取，然后自动生成提取指令",
        use_container_width=True,
        key="scan_btn",
    )
with scan_col2:
    if st.session_state.scan_result:
        st.success("✅ 扫描完成！请查看下方建议，复制建议指令到左侧输入框。")
    else:
        st.caption("👆 不确定提取什么？先填 URL，点这里让 AI 帮你分析！")

if st.session_state.scan_result:
    with st.expander("🔍 智能扫描结果 — AI 建议可提取的数据", expanded=True):
        st.markdown(st.session_state.scan_result)

# --- 开始抓取按钮 ---
start_button = st.button(
    label="🚀 开始抓取并 AI 提取",
    type="primary",
    use_container_width=True,
)

# --- 显示抓取状态 ---
if st.session_state.fetch_status:
    if "✅" in st.session_state.fetch_status:
        st.success(st.session_state.fetch_status)
    elif "⚠️" in st.session_state.fetch_status:
        st.warning(st.session_state.fetch_status)
    elif "❌" in st.session_state.fetch_status:
        st.error(st.session_state.fetch_status)

# ============================================================================
# 第五部分：按钮执行逻辑
# ============================================================================

# --- 智能扫描按钮逻辑 ---
if scan_button:
    if not target_url.strip():
        st.error("❗ 请先在左侧输入网页 URL，才能进行智能扫描。")
    elif not api_key.strip():
        st.error("❗ 请在侧边栏填写 API Key。")
    else:
        with st.spinner("🌐 正在抓取网页内容（用于扫描）..."):
            scan_client = OpenAI(api_key=api_key, base_url=api_base_url)
            scan_text, scan_fetch_status = fetch_and_clean_html(target_url)

        if not scan_text:
            st.error(scan_fetch_status)
        else:
            with st.spinner("🔍 AI 正在分析网页内容，判断可提取的数据类型..."):
                scan_result, scan_status = smart_scan_page(
                    web_text=scan_text,
                    client=scan_client,
                    model=model_name,
                )
                st.session_state.scan_result = scan_result
                st.session_state.web_text = scan_text

            if scan_result:
                st.success(scan_status)
            else:
                st.error(scan_status)
        st.rerun()

# --- 开始抓取按钮逻辑 ---
if start_button:
    # ---- 第 1 关：校验用户输入 ----
    if not target_url.strip():
        st.error("❗ 请输入要抓取的网页 URL，不能为空。")
    elif not extraction_requirement.strip():
        st.error("❗ 请用大白话描述你想提取什么数据，不能为空。")
    elif not api_key.strip():
        st.error("❗ 请在左侧边栏填写 API Key。")
    else:
        st.session_state.retry_used = False

        # ---- 第 2 关：创建 OpenAI 客户端 ----
        with st.spinner("🔧 正在初始化 AI 客户端..."):
            ai_client = OpenAI(api_key=api_key, base_url=api_base_url)

        # ---- 第 2.5 关：robots.txt 合规检查 ----
        robots_ok = True
        if robots_check_enabled:
            with st.spinner("🤖 正在检查 robots.txt 合规性..."):
                robots_ok, robots_msg = check_robots_txt(target_url)
                st.session_state.robots_status = robots_msg
                if not robots_ok:
                    st.error(robots_msg)
                    st.stop()
                else:
                    st.success(robots_msg)

        # ---- 第 3 关：抓取 + 清洗网页 ----
        with st.spinner("🌐 正在抓取网页内容..."):
            clean_text, fetch_status = fetch_and_clean_html(target_url)
            st.session_state.web_text = clean_text
            st.session_state.fetch_status = fetch_status

        if not clean_text:
            st.error(fetch_status)
            st.stop()

        st.success(fetch_status)

        with st.expander("📄 查看清洗后的网页文本（前 2000 字符预览）", expanded=False):
            preview = clean_text[:2000]
            st.text_area(
                label="清洗后文本预览",
                value=preview,
                height=300,
                disabled=True,
                key="text_preview",
            )

        # ---- 第 4 关：调用 AI 提取结构化数据 ----
        actual_max_text = max_text_length_slider
        with st.spinner("🤖 AI 正在分析网页内容并提取结构化数据..."):
            if debug_mode:
                st.session_state.debug_truncated_text = clean_text[:actual_max_text]

            data, extract_status = extract_structured_data(
                web_text=clean_text,
                user_requirement=extraction_requirement,
                client=ai_client,
                model=model_name,
                temperature=temperature,
                max_tokens=max_tokens,
                max_text_length=actual_max_text,
            )
            st.session_state.extracted_data = data
            st.session_state.fetch_status = extract_status

        if data is None:
            st.error(extract_status)
            if debug_mode:
                st.info(f"调试信息：发送给 AI 的网页文本长度为 {min(len(clean_text), actual_max_text):,} 字符")
            st.stop()

        st.success(extract_status)

        # ---- 第 4.5 关：空数组自动重试 ----
        if len(data) == 0 and not st.session_state.retry_used:
            st.warning("⚠️ 第一轮提取返回了空结果。正在用更宽泛的策略自动重试...")
            st.session_state.retry_used = True

            fallback_requirement = (
                "请你自己判断这个网页的主要内容类型，然后提取其中所有的结构化数据。"
                "例如：如果是新闻列表，提取标题和时间；如果是商品页，提取商品名和价格；"
                "如果是数据表格，提取表格中的所有行和列。"
                "总之：找到页面上任何可以整理成表格的信息，全部提取出来。"
            )

            with st.spinner("🔄 AI 正在用更宽泛的策略重新提取（第 2 轮）..."):
                data, extract_status = extract_structured_data(
                    web_text=clean_text,
                    user_requirement=fallback_requirement,
                    client=ai_client,
                    model=model_name,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    max_text_length=actual_max_text,
                )
                st.session_state.extracted_data = data
                st.session_state.fetch_status = f"🔄 已自动切换为泛化提取策略。{extract_status}"

            if data is None:
                st.error(extract_status)
                st.stop()

            if len(data) > 0:
                st.success(f"✅ 第二轮泛化提取成功！共提取 {len(data)} 条数据。")
            else:
                st.warning(
                    "⚠️ 两轮 AI 提取均未找到结构化数据。\n\n"
                    "可能的原因：\n"
                    "1. 网页主要内容是图片/动态加载的（React/Vue 渲染），纯文本中不包含目标数据\n"
                    "2. 网页文本被截断太多 → 尝试增大左侧的「网页文本截取长度」到 50000\n"
                    "3. 该网页确实没有可表格化的结构化数据（如纯文章正文）\n"
                    "4. 网站有反爬机制，返回了空页面或验证码页面"
                )
                if debug_mode and st.session_state.debug_truncated_text:
                    text_sent = st.session_state.debug_truncated_text
                    with st.expander("🐛 调试：查看发送给 AI 的文本（末尾 1500 字符）", expanded=False):
                        st.text_area(
                            label="发送给 AI 的文本末尾",
                            value=text_sent[-1500:] if len(text_sent) > 1500 else text_sent,
                            height=300,
                            disabled=True,
                        )

        # ---- 第 5 关：自动识别数值列 + 生成图表数据 ----
        if len(data) > 0:
            with st.spinner("📊 正在分析数据列类型，准备图表..."):
                df_raw = pd.DataFrame(data)
                numeric_cols, df_processed = identify_numeric_columns(df_raw)
                st.session_state.df_processed = df_processed
                st.session_state.numeric_cols = numeric_cols

        # ---- 第 6 关：AI 数据洞察分析报告 ----
        if len(data) > 0:
            with st.spinner("🧠 AI 正在撰写数据洞察分析报告..."):
                report, report_status = generate_ai_analysis_report(
                    data=data,
                    client=ai_client,
                    model=model_name,
                    temperature=0.7,
                )
                st.session_state.ai_report = report
                st.session_state.report_status = report_status

        st.rerun()

# ============================================================================
# 第六部分：结果展示区
# ============================================================================

if st.session_state.extracted_data is not None and len(st.session_state.extracted_data) > 0:
    st.divider()
    st.header("📊 第二步：数据表格与可视化分析")

    # ========================================================================
    # 6-A：数据表格展示
    # ========================================================================
    data = st.session_state.extracted_data
    df = pd.DataFrame(data)

    st.subheader("📋 结构化数据表格")

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.metric(label="📋 数据条数", value=len(data))
    with col_b:
        st.metric(label="📌 字段数量", value=len(data[0].keys()))
    with col_c:
        num_count = len(st.session_state.numeric_cols)
        st.metric(label="🔢 数值列数", value=num_count if num_count > 0 else "无")

    st.dataframe(df, use_container_width=True, hide_index=False)

    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    st.download_button(
        label="💾 下载 JSON 数据",
        data=json_str,
        file_name="ai_extracted_data.json",
        mime="application/json",
    )

    # ========================================================================
    # 6-B：数据可视化图表
    # ========================================================================
    st.divider()
    st.subheader("📈 自动数据可视化")

    numeric_cols = st.session_state.numeric_cols
    df_processed = st.session_state.df_processed

    if numeric_cols and df_processed is not None:
        chart_type = st.radio(
            label="选择图表类型",
            options=["📊 柱状图 (Bar Chart)", "📉 折线图 (Line Chart)"],
            horizontal=True,
            key="chart_type",
        )

        if len(numeric_cols) > 0:
            selected_cols = st.multiselect(
                label="选择要在图表中展示的数值列（可多选）",
                options=numeric_cols,
                default=numeric_cols[: min(4, len(numeric_cols))],
                help="只显示包含数字的列，纯文本列不会出现在这里",
                key="chart_cols",
            )
        else:
            selected_cols = numeric_cols

        if selected_cols:
            chart_df = df_processed[selected_cols].copy()

            first_col = df.columns[0]
            if first_col not in selected_cols:
                chart_df.index = df[first_col].astype(str)

            if chart_type == "📊 柱状图 (Bar Chart)":
                st.bar_chart(chart_df, use_container_width=True, height=400)
            else:
                st.line_chart(chart_df, use_container_width=True, height=400)

            st.caption(
                f"💡 图表基于 {len(selected_cols)} 个数值列绘制。"
                f"如果数据包含薪资范围（如 '15K-25K'），系统会自动取第一个数字（15）作为数值。"
            )
    else:
        st.info(
            "ℹ️ 当前提取的数据中没有识别到数值列，无法自动生成图表。\n\n"
            "这是正常的——如果你的数据全是文字信息（如文章标题、作者名等），图表没有意义。\n"
            "如果数据里确实包含数字（如价格、薪资），请检查 AI 的提取结果是否将这些数字正确提取出来了。"
        )

    # ========================================================================
    # 6-C：AI 数据洞察分析报告
    # ========================================================================
    st.divider()
    st.subheader("🧠 AI 数据洞察分析报告")

    if st.session_state.ai_report:
        st.markdown(st.session_state.ai_report)
        if st.session_state.report_status:
            st.caption(st.session_state.report_status)
    elif st.session_state.report_status and "❌" in st.session_state.report_status:
        st.error(st.session_state.report_status)
    else:
        st.info("⏳ 分析报告尚未生成，请先点击「开始抓取并 AI 提取」按钮。")

elif st.session_state.extracted_data is not None and len(st.session_state.extracted_data) == 0:
    st.divider()
    st.warning("⚠️ AI 完成了分析，但未提取到符合条件的数据。请尝试调整需求描述，或确认网页内容包含你要的信息。")

# ============================================================================
# 第七部分：页脚
# ============================================================================

st.divider()
st.caption(
    "💡 提示：左侧边栏可随时修改 API 配置。\n"
    "📌 系统会自动识别数值列并生成图表，并调用 AI 撰写数据洞察报告。"
)
