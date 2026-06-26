"""
网页抓取与清洗服务

提供两个核心功能：
1. fetch_and_clean_html — 抓取网页并用 BeautifulSoup 清洗出纯文本
2. check_robots_txt — 检查目标网站的 robots.txt 是否允许爬取
"""

import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

# 浏览器 UA，防止被反爬拦截
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

# 抓取时需要从 DOM 中删除的无用标签
USELESS_TAGS = ["script", "style", "noscript", "iframe", "nav", "footer", "header"]


def fetch_and_clean_html(url: str, timeout: int = 15) -> tuple[str, str]:
    """
    使用 requests 抓取网页源码，然后用 BeautifulSoup 清洗出纯文本。

    参数:
        url:     目标网页的完整 URL
        timeout: 请求超时时间（秒）

    返回:
        tuple[纯文本内容, 状态信息]
        - 成功时：("清洗后的网页文本...", "✅ 抓取成功，共提取 N 个字符")
        - 失败时：("", "❌ 错误信息...")
    """
    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    # ---------- 第 1 步：发送 HTTP 请求 ----------
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        raw_html = response.text
    except requests.exceptions.Timeout:
        return "", f"❌ 请求超时：网页超过 {timeout} 秒没有响应，请检查 URL 是否正确。"
    except requests.exceptions.ConnectionError:
        return "", "❌ 连接失败：无法连接到该网址，请检查网络或 URL 格式。"
    except requests.exceptions.HTTPError as e:
        return "", f"❌ HTTP 错误：{e}"
    except Exception as e:
        return "", f"❌ 未知错误：{e}"

    # ---------- 第 2 步：用 BeautifulSoup 清洗 HTML ----------
    soup = BeautifulSoup(raw_html, "html.parser")

    # 删除无用标签，减少发送给 AI 的 Token 数量
    for tag_name in USELESS_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    clean_text = soup.get_text(separator="\n", strip=True)

    # ---------- 第 3 步：压缩空白行，精简文本 ----------
    clean_text = re.sub(r"\n{3,}", "\n\n", clean_text)
    clean_text = "\n".join(line.strip() for line in clean_text.splitlines())
    clean_text = "\n".join(line for line in clean_text.splitlines() if line.strip())

    char_count = len(clean_text)
    status = f"✅ 抓取成功！共提取 {char_count:,} 个有效字符"

    return clean_text, status


def check_robots_txt(url: str) -> tuple[bool, str]:
    """
    检查目标网站的 robots.txt，确认是否允许爬虫访问目标路径。

    参数:
        url: 目标网页的完整 URL

    返回:
        tuple[是否允许, 提示信息]
        - (True, "...")   → 允许访问
        - (False, "...")  → 被禁止，不应爬取
    """
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    target_path = parsed.path or "/"

    try:
        resp = requests.get(robots_url, timeout=10)
        if resp.status_code == 404:
            return True, "⚠️ 该网站未设置 robots.txt，默认可爬取。请自觉控制抓取频率。"
        resp.raise_for_status()
        robots_content = resp.text
    except requests.exceptions.Timeout:
        return True, "⚠️ robots.txt 请求超时，无法验证合规性。请自行确认该网站允许爬取。"
    except Exception:
        return True, "⚠️ 无法获取 robots.txt，跳过合规检查。请自行确认爬取合法性。"

    # ---- 解析 robots.txt ----
    current_agents = []
    rules = []
    current_allows = []
    current_disallows = []

    for line in robots_content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        ua_match = re.match(r"^User-agent:\s*(.+)$", line, re.IGNORECASE)
        if ua_match:
            if current_agents:
                rules.append((current_agents, current_allows, current_disallows))
            current_agents = [ua_match.group(1).strip()]
            current_allows = []
            current_disallows = []
            continue

        allow_match = re.match(r"^Allow:\s*(.+)$", line, re.IGNORECASE)
        if allow_match and current_agents:
            current_allows.append(allow_match.group(1).strip())
            continue

        disallow_match = re.match(r"^Disallow:\s*(.+)$", line, re.IGNORECASE)
        if disallow_match and current_agents:
            current_disallows.append(disallow_match.group(1).strip())
            continue

    if current_agents:
        rules.append((current_agents, current_allows, current_disallows))

    # ---- 匹配规则 ----
    def _agent_matches(rule_agents):
        for agent in rule_agents:
            if agent == "*" or agent.lower() in USER_AGENT.lower():
                return True
        return False

    def _path_matches(rule_path, target):
        if rule_path == "/":
            return target == "/" or target == ""
        pattern = re.escape(rule_path).replace(r"\*", ".*")
        return bool(re.match(pattern, target))

    is_allowed = True
    matched_rule = None

    for rule_agents, allows, disallows in rules:
        if not _agent_matches(rule_agents):
            continue

        for dis_path in disallows:
            if not dis_path:
                continue
            if _path_matches(dis_path, target_path):
                is_allowed = False
                matched_rule = f"Disallow: {dis_path}"
                break
        if not is_allowed:
            break

        for allow_path in allows:
            if _path_matches(allow_path, target_path):
                is_allowed = True
                matched_rule = f"Allow: {allow_path}"
                break
        if is_allowed:
            break

    if is_allowed:
        return True, (
            f"✅ robots.txt 合规检查通过！该路径允许爬取。\n"
            f"匹配规则: {matched_rule or '无明确规则（默认允许）'}"
        )
    else:
        return False, (
            f"🚫 robots.txt 禁止爬取该路径！\n"
            f"禁止规则: {matched_rule}\n"
            f"robots.txt 地址: {robots_url}\n\n"
            f"请你尊重网站所有者的意愿，不要强行爬取被 robots.txt 明确禁止的路径。"
        )
