import os
import re
import urllib.parse
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup, NavigableString
import markdown
import requests

from components import (
    build_checklist_card,
    build_code_card,
    build_pipeline_card,
    build_qa_card,
    build_resource_card,
    build_spec_card,
    build_takeaway_card,
    build_timeline_card,
    build_warning_card,
)


def _to_str(val: Any) -> str:
    """辅助函数：安全转换字符串。"""
    if isinstance(val, list):
        return " ".join([str(x) for x in val])
    return str(val or "").strip()


def clean_html_whitespace(html_str: str) -> str:
    """消除 HTML 标签之间的冗余空隙，保留标签内部代码格式。"""
    html_str = re.sub(r">\s+<", "><", html_str)
    return html_str.strip()


def split_markdown_paragraphs(md_text: str) -> List[str]:
    """
    智能段落切分引擎：
    保证代码块 (```...```) 内部即使含有空行，也作为一个整体段落，绝不被切碎。
    """
    code_blocks = {}
    counter = 0

    def code_sub(match):
        nonlocal counter
        ph = f"__CODE_BLOCK_PLACEHOLDER_{counter}__"
        code_blocks[ph] = match.group(0)
        counter += 1
        return ph

    # 1. 保护代码块
    protected = re.sub(r"```[\s\S]*?```", code_sub, md_text)

    # 2. 按双换行安全切分
    raw_paras = [p.strip() for p in protected.split("\n\n") if p.strip()]

    # 3. 还原代码块
    final_paras = []
    for p in raw_paras:
        for ph, original_code in code_blocks.items():
            if ph in p:
                p = p.replace(ph, original_code)
        final_paras.append(p)

    return final_paras


def _flatten_latex_to_unicode(latex: str) -> str:
    """终极公式扁平化引擎：利用 pylatexenc 语法树解析全量 LaTeX，并美化上下标与分式。"""
    text = latex.strip()
    if not text:
        return ""

    # 1. 优先清洗所有字体修饰符: \mathcal{H} -> H, \mathbf{W} -> W, \bm{x} -> x, \mathbb{R} -> R
    text = re.sub(r"\\(?:mathcal|mathbb|mathscr|mathfrak|mathbf|mathrm|text|mathit|boldsymbol|bm)\{([^{}]+)\}", r"\1", text)

    # 2. 支持嵌套括号的分式优雅转换: \frac{A}{B} -> A / (B)
    nested_frac_pattern = r"\\frac\{((?:[^{}]|\{[^{}]*\})+)\}\{((?:[^{}]|\{[^{}]*\})+)\}"
    def frac_sub(m):
        num = m.group(1).strip()
        den = m.group(2).strip()
        num = re.sub(r"[{}]", "", num)
        den = re.sub(r"[{}]", "", den)
        den_str = f"({den})" if any(op in den for op in ["+", "-", " ", "*"]) and not (den.startswith("(") and den.endswith(")")) else den
        return f"{num} / {den_str}"
    
    # 循环替换直到没有嵌套分式
    while re.search(nested_frac_pattern, text):
        text = re.sub(nested_frac_pattern, frac_sub, text)

    # 3. 调用 pylatexenc 工业级转换引擎（解析所有希腊字母、数学符号、箭头、积分求和等）
    try:
        from pylatexenc.latex2text import LatexNodes2Text
        text = LatexNodes2Text(math_mode='text').latex_to_text(text)
    except Exception:
        pass

    # 4. 上标与下标的 Unicode 字符级美化
    sup_map = {
        "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹",
        "+": "⁺", "-": "⁻", "=": "⁼", "(": "⁽", ")": "⁾",
        "a": "ᵃ", "b": "ᵇ", "c": "ᶜ", "d": "ᵈ", "e": "ᵉ", "f": "ᶠ", "g": "ᵍ", "h": "ʰ", "i": "ⁱ", "j": "ʲ",
        "k": "ᵏ", "l": "ˡ", "m": "ᵐ", "n": "ⁿ", "o": "ᵒ", "p": "ᵖ", "r": "ʳ", "s": "ˢ", "t": "ᵗ", "u": "ᵘ",
        "v": "ᵛ", "w": "ʷ", "x": "ˣ", "y": "ʸ", "z": "ᶻ", "T": "ᵀ"
    }
    sub_map = {
        "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄", "5": "₅", "6": "₆", "7": "₇", "8": "₈", "9": "₉",
        "+": "₊", "-": "₋", "=": "₌", "(": "₍", ")": "₎",
        "a": "ₐ", "e": "ₑ", "h": "ₕ", "i": "ᵢ", "j": "ⱼ", "k": "ₖ", "l": "ₗ", "m": "ₘ", "n": "ₙ", "o": "ₒ",
        "p": "ₚ", "r": "ᵣ", "s": "ₛ", "t": "ₜ", "u": "ᵤ", "v": "ᵥ", "x": "ₓ"
    }

    text = re.sub(r"\^\{([^{}]+)\}|\^([0-9a-zA-Z+-])", lambda m: "".join(sup_map.get(c, c) for c in (m.group(1) or m.group(2))), text)
    text = re.sub(r"_\{([^{}]+)\}|_([0-9a-zA-Z+-])", lambda m: "".join(sub_map.get(c, c) for c in (m.group(1) or m.group(2))), text)

    # 5. 清理多余大括号、反斜杠与空格
    text = re.sub(r"[{}]", "", text)
    text = re.sub(r"\\[a-zA-Z]+", "", text)  # 清理任何未被识别的残余反斜杠命令
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _process_latex_formula(latex_code: str, is_block: bool, primary_color: str, wechat_token: str = "") -> str:
    """公式处理：优先上传至微信 CDN 生成 mmbiz 官方图片，降级方案为 CodeCogs/精美文本。"""
    latex_code = latex_code.strip()
    if not latex_code:
        return ""

    if is_block:
        latex_query = rf"\dpi{{300}} \bg_white \large {latex_code}"
        encoded_latex = urllib.parse.quote(latex_query)
        api_url = f"https://latex.codecogs.com/png.image?{encoded_latex}"

        if wechat_token:
            try:
                img_res = requests.get(api_url, timeout=8)
                if img_res.status_code == 200 and img_res.content.startswith(b"\x89PNG\r\n\x1a\n"):
                    temp_formula_path = "temp_formula.png"
                    with open(temp_formula_path, "wb") as f:
                        f.write(img_res.content)

                    upload_url = f"https://api.weixin.qq.com/cgi-bin/media/uploadimg?access_token={wechat_token}"
                    with open(temp_formula_path, "rb") as f:
                        res_json = requests.post(upload_url, files={"media": f}, timeout=8).json()

                    if "url" in res_json:
                        return (
                            f'<section style="text-align:center;margin:18px 0;" data-wechat-card="true">'
                            f'<img src="{res_json["url"]}" style="display:inline-block;max-height:80px;max-width:100%;vertical-align:middle;" alt="{latex_code}">'
                            f'</section>'
                        )
            except Exception as e:
                print(f"[EXCEPT] 微信公式转图异常: {str(e)}")

        return (
            f'<section style="text-align:center;margin:18px 0;" data-wechat-card="true">'
            f'<img src="{api_url}" style="display:inline-block;max-height:80px;max-width:100%;vertical-align:middle;" alt="{latex_code}">'
            f'</section>'
        )
    else:
        # 调用扁平化函数转为 Unicode 纯文本，并保留优雅的衬线字体排版
        plain_formula = _flatten_latex_to_unicode(latex_code)
        return (
            f'<span style="font-family:Georgia,\'Times New Roman\',serif;font-style:italic;'
            f'color:{primary_color};margin:0 3px;letter-spacing:0.5px;">'
            f'{plain_formula}</span>'
        )


def assemble_wechat_html(
    markdown_text: str,
    semantic_config: Dict[str, Any],
    wechat_token: str = "",
) -> str:
    """
    一站式组装引擎（纯 DOM 架构版）：
    普通段落与卡片组件完全在 DOM 树节点层面组装，杜绝字符串混编与解析污染。
    """
    # 1. 提取视觉配置与高亮关键词
    visual_config = semantic_config.get("visual_config", {})
    primary = visual_config.get("primary_color", "#0288d1")
    secondary_bg = visual_config.get("secondary_bg", "#f4f8fa")
    highlight_keywords = [kw for kw in visual_config.get("highlight_keywords", []) if kw]

    # 2. 剥离正文开头的大标题
    clean_md = re.sub(r"^\s*#\s+[^\n]+\n*", "", markdown_text).strip()

    # 3. 公式占位保护（严禁引入多余换行，避免打乱段落索引）
    formula_map = {}
    formula_counter = 0

    def block_formula_callback(match):
        nonlocal formula_counter
        placeholder = f"%%BLOCK_FORMULA_HOLDER_{formula_counter}%%"
        formula_map[placeholder] = _process_latex_formula(match.group(1), True, primary, wechat_token)
        formula_counter += 1
        return placeholder

    def inline_formula_callback(match):
        nonlocal formula_counter
        placeholder = f"%%INLINE_FORMULA_HOLDER_{formula_counter}%%"
        formula_map[placeholder] = _process_latex_formula(match.group(1), False, primary, wechat_token)
        formula_counter += 1
        return placeholder

    protected_md = re.sub(r"\$\$(.*?)\$\$", block_formula_callback, clean_md, flags=re.DOTALL)
    protected_md = re.sub(r"\$(.*?)\$", inline_formula_callback, protected_md, flags=re.DOTALL)

    # 4. 智能切分段落（与大模型接收的段落严格 1:1 对齐）
    raw_paragraphs = split_markdown_paragraphs(protected_md)
    cards = semantic_config.get("cards", [])

    card_at_start_para = {}  # 起始段落编号 -> Card BeautifulSoup 节点
    claimed_paras = set()    # 被卡片合并覆盖的段落编号集合

    # 5. 生成卡片 DOM 节点
    for card_info in cards:
        c_type = card_info.get("type")
        target_paras = card_info.get("target_paragraphs", [])

        if isinstance(target_paras, int):
            target_paras = [target_paras]

        valid_paras = [p_idx for p_idx in target_paras if isinstance(p_idx, int) and 1 <= p_idx <= len(raw_paragraphs)]
        if not valid_paras:
            continue

        valid_paras.sort()
        start_idx = valid_paras[0]
        data = card_info.get("data", {})

        # 合并目标段落原始文本
        combined_original_text = "\n\n".join([raw_paragraphs[p - 1] for p in valid_paras])
        card_html = ""

        # 分发构建卡片
        if c_type == "takeaway":
            quote_text = data.get("quote_text") or combined_original_text
            clean_quote = re.sub(r"^>\s*", "", quote_text).strip()
            card_html = build_takeaway_card(clean_quote, primary, secondary_bg)

        elif c_type == "warning":
            title = data.get("title", "注意事项")
            content = data.get("content") or combined_original_text
            alert_type = data.get("alert_type", "warning")
            clean_content = re.sub(r"^>\s*", "", content).strip()
            card_html = build_warning_card(title, clean_content, alert_type)

        elif c_type == "code":
            code_match = re.search(r"```(?:\w+)?\s*\n?(.*?)\n?```", combined_original_text, re.DOTALL)
            code_text = code_match.group(1) if code_match else (data.get("code_text") or data.get("code") or combined_original_text)
            lang = data.get("language") or "Python"
            card_html = build_code_card(code_text, lang, primary)

        elif c_type == "qa":
            question = data.get("question", "疑难解答")
            answer = data.get("answer") or combined_original_text
            card_html = build_qa_card(question, answer, primary)

        elif c_type == "resource":
            title = data.get("title", "开源资源与链接")
            desc = data.get("desc") or data.get("description") or combined_original_text
            link_info = data.get("link_info") or data.get("link", "获取链接")
            card_html = build_resource_card(title, desc, link_info, primary, secondary_bg)

        elif c_type == "checklist":
            title = data.get("title", "核心总结清单")
            items = data.get("items", [])
            if not items:
                items = [re.sub(r"^[•●▪✦\-*\d.]+\s*", "", line).strip() for line in combined_original_text.split("\n") if line.strip()]
            card_html = build_checklist_card(title, items, primary, secondary_bg)

        elif c_type == "pipeline":
            steps = data.get("steps", [])
            if len(steps) >= 2:
                card_html = build_pipeline_card(steps, primary, secondary_bg)

        elif c_type == "spec":
            title = data.get("title", "模型参数与配置")
            specs = data.get("specs", {})
            if specs:
                card_html = build_spec_card(title, specs, primary)

        elif c_type == "timeline":
            title = data.get("title", "技术演进历程")
            events = data.get("events", [])
            if events:
                card_html = build_timeline_card(title, events, primary)

        # 封装卡片节点并打上隔离标记
        if card_html:
            card_bs = BeautifulSoup(card_html, "html.parser")
            top_node = card_bs.find(True)
            if top_node:
                top_node["data-wechat-card"] = "true"
                card_at_start_para[start_idx] = card_bs
                for p_idx in valid_paras:
                    claimed_paras.add(p_idx)

    # 6. 【核心重构】：在纯 DOM 树上装配节点（彻底摒弃 Markdown 混拼）
    root_soup = BeautifulSoup('<div id="wechat-article-root"></div>', "html.parser")
    root_container = root_soup.find("div")

    for idx, para_text in enumerate(raw_paragraphs, start=1):
        if idx in card_at_start_para:
            # 插入预先构建好的卡片 DOM 节点
            root_container.append(card_at_start_para[idx])
        elif idx in claimed_paras:
            # 该段落已被卡片吞并，跳过
            continue
        else:
            # 普通段落单独编译 Markdown，不受卡片 HTML 干扰
            para_html = markdown.markdown(para_text, extensions=["extra", "tables"])
            para_soup = BeautifulSoup(para_html, "html.parser")
            for elem in list(para_soup.contents):
                if elem.name:
                    root_container.append(elem)

    # 7. 还原公式占位符
    final_dom_html = str(root_container)
    for placeholder, rendered_formula in formula_map.items():
        final_dom_html = final_dom_html.replace(placeholder, rendered_formula)

    soup = BeautifulSoup(final_dom_html, "html.parser")

    def _is_inside_card(node):
        return node.find_parent(attrs={"data-wechat-card": "true"}) is not None or node.get("data-wechat-card") == "true"

    # 8. 全局 DOM 美化（跳过已标记卡片）
    # (A) H2 / H3 徽章标题美化
    for h in soup.find_all(["h2", "h3"]):
        if _is_inside_card(h):
            continue
        title_text = h.get_text(strip=True)
        h_section = soup.new_tag("section")
        h_section["style"] = (
            f"margin: 35px 0 18px; padding-bottom: 6px; border-bottom: 2px solid {primary}; "
            f"display: flex; align-items: center; font-size: 18px !important; font-weight: bold !important; "
            f"color: {primary} !important; line-height: 1.4;"
        )
        badge_html = (
            f'<span style="background:{primary}; color:#ffffff; padding:3px 8px; border-radius:4px; '
            f'margin-right:8px; font-size:12px; font-weight:bold; flex-shrink:0;">SECTION</span>'
            f'<span style="font-size:18px !important; font-weight:bold !important; color:{primary} !important;">{title_text}</span>'
        )
        h_section.append(BeautifulSoup(badge_html, "html.parser"))
        h.replace_with(h_section)

    # (B) 普通引用块 Blockquote 降级为重点框
    for quote in soup.find_all("blockquote"):
        if _is_inside_card(quote):
            continue
        quote_text = quote.get_text(strip=True)
        quote_html = (
            f'<div style="background:{secondary_bg}; border-left:4px solid {primary}; padding:14px 18px; '
            f'border-radius:0 8px 8px 0; margin:20px 0; color:#444444; font-size:14.5px; line-height:1.8;">💡 {quote_text}</div>'
        )
        quote.replace_with(BeautifulSoup(quote_html, "html.parser"))

    # (C) 列表 <ul>/<ol> 微信稳妥布局重构
    for ul_tag in soup.find_all(["ul", "ol"]):
        if _is_inside_card(ul_tag):
            continue
        is_ol = (ul_tag.name == "ol")
        list_container = soup.new_tag("section")
        list_container["style"] = "margin: 16px 0;"

        for idx, li in enumerate(ul_tag.find_all("li", recursive=False)):
            for p_inside in li.find_all("p"):
                p_inside.unwrap()
            li_content = re.sub(r"^[•●▪✦\-*\s]+", "", li.decode_contents().strip())
            if not li_content:
                continue

            bullet = f"{idx + 1}." if is_ol else "✦"
            item_html = (
                f'<section style="display: table; width: 100%; margin-bottom: 8px; line-height: 1.8;">'
                f'<section style="display: table-cell; width: 22px; vertical-align: top; color: {primary}; font-weight: bold; font-size: 15px;">{bullet}</section>'
                f'<section style="display: table-cell; vertical-align: top; color: #333333; font-size: 15px; text-align: justify;">{li_content}</section>'
                f'</section>'
            )
            list_container.append(BeautifulSoup(item_html, "html.parser"))

        ul_tag.replace_with(list_container)

    # (D) 关键词高亮
    if highlight_keywords:
        for p in soup.find_all("p"):
            if _is_inside_card(p):
                continue
            for text_node in list(p.find_all(text=True)):
                if isinstance(text_node, NavigableString):
                    node_str = str(text_node)
                    modified = False
                    for kw in highlight_keywords:
                        if kw in node_str and f"color:{primary}" not in node_str:
                            node_str = node_str.replace(
                                kw, f'<strong style="color:{primary}; font-weight:bold;">{kw}</strong>'
                            )
                            modified = True
                    if modified:
                        text_node.replace_with(BeautifulSoup(node_str, "html.parser"))

    # (E) 普通段落排版修饰
    for p in soup.find_all("p"):
        if _is_inside_card(p):
            continue
        if not p.get_text(strip=True) and not p.find_all(["img", "section", "svg", "iframe", "table"]):
            p.decompose()
            continue
        p["style"] = "margin: 0 0 16px 0; line-height: 1.8; font-size: 15px; color: #333333; text-align: justify;"

    # (F) 未匹配为卡片的普通代码块（兜底转暗黑卡片）
    for pre in soup.find_all("pre"):
        if _is_inside_card(pre):
            continue
        code_tag = pre.find("code")
        raw_code = code_tag.get_text() if code_tag else pre.get_text()
        lang = "PYTHON"
        if code_tag and code_tag.get("class"):
            for cls in code_tag["class"]:
                if cls.startswith("language-"):
                    lang = cls.replace("language-", "").upper()
                    break
        card_html = build_code_card(raw_code, lang, primary)
        pre.replace_with(BeautifulSoup(card_html, "html.parser"))

    # 提取顶层容器内的 HTML 内容并清理空白
    final_html = soup.find("div", id="wechat-article-root").decode_contents()
    return clean_html_whitespace(final_html)

