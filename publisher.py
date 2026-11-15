import functools
import json
import os
import re
import time
import urllib.parse

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from PIL import Image
from playwright.sync_api import sync_playwright
import requests
from requests.adapters import HTTPAdapter, Retry
from typing import Any, Dict, Optional
from langchain_core.tools import tool


from state import TeamState
from utils import decode_base64_to_image, encode_image_to_base64, extract_article_title
from wechat_assembler import assemble_wechat_html


# 加载环境变量
load_dotenv()

# 配置全局请求重试策略
session = requests.Session()
session.mount("https://", HTTPAdapter(max_retries=Retry(total=3, backoff_factor=1)))
requests.get, requests.post = session.get, session.post


@functools.lru_cache(maxsize=1)
def get_wechat_access_token() -> str:
    """获取微信公众号临时 Access Token。"""
    app_id = os.getenv("WECHAT_APP_ID")
    app_secret = os.getenv("WECHAT_APP_SECRET")

    if not app_id or not app_secret:
        return ""

    url = (
        "https://api.weixin.qq.com/cgi-bin/token"
        f"?grant_type=client_credential&appid={app_id}&secret={app_secret}"
    )

    try:
        response = requests.get(url, timeout=10)
        res_json = response.json()

        if "access_token" in res_json:
            print("[INFO] 微信 Access Token 获取成功。")
            return res_json["access_token"]

        print(f"[ERROR] 微信 Token 获取失败，响应数据: {res_json}")
        return ""
    except Exception as e:
        print(f"[EXCEPT] 获取微信 Token 网络异常: {str(e)}")
        return ""


def generate_and_upload_cover_node(state: TeamState) -> dict:
    """节点：分析文章内容，生成 AI 封面图并上传至微信素材库。"""
    raw_article = state.get("draft_article", "")

    prompt_llm = ChatOpenAI(
        model=os.getenv("MODEL_LLM"),
        api_key=os.getenv("API_KEY"),
        base_url=os.getenv("BASE_URL"),
        temperature=0.1,
        timeout=120,
    )

    sys_prompt = """你是一位懂艺术、懂科技、审美极高的高级视觉设计总监。
你的任务是：根据传入的文章【标题】与【核心摘要】，为这篇公众号推文量身定制最契合的 AI 封面生成提示词（Prompt）。

请遵循以下【艺术创作三要素】：

1. 视觉隐喻 (Visual Metaphor)：
   将文章中抽象的技术/观点，转化为富有想象力的具象视觉主体。切忌直白描绘，要带有艺术感与科幻感。

2. 风格自主选择 (Dynamic Style)：
   根据文章的调性，自主挑选最匹配的一种风格（如 3D 玻璃与光影渲染、科幻蓝图、社论级概念插画、赛博朋克、抽象流体等）。

3. 硬性规避限制 (Safety Rules)：
   - 必须包含：no text, no words, no letters, no labels（画面严禁出现任何文字乱码）。
   - 主体突出，画面干净不杂乱，适合 16:9 横屏展现。
   - 提示词控制在 120 个英文单词以内。

请直接输出英文提示词，严禁包含任何中文说明或 Markdown 标签。"""

    messages = [
        SystemMessage(content=sys_prompt),
        HumanMessage(content=f"Generate a visual prompt for this paper:\n\n{raw_article}"),
    ]

    print("[INFO] 正在分析内容并生成封面 Prompt...")
    cover_prompt = prompt_llm.invoke(messages).content.strip()
    print(f"[INFO] 生成的封面 Prompt: {cover_prompt}")

    cover_local_path = "temp_cover.jpg"
    try:
        url = f"{os.getenv("BASE_URL")}/chat/completions"
        headers = {
            "Authorization": f"Bearer {os.getenv('API_KEY')}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": os.getenv("MODEL_PLM"),
            "messages": [
                {"role": "user", "content": f"Please generate a high quality image: {cover_prompt}"}
            ],
        }
        response = requests.post(url, json=payload, headers=headers, timeout=60)

        if response.status_code != 200:
            raise RuntimeError(f"API 异常状态码 {response.status_code}: {response.text}")

        res_json = response.json()
        message = res_json.get("choices", [{}])[0].get("message", {})
        content = message.get("content", "")
        http_match = re.search(r"https?://[^\s\)\"\']+", content)
        base64_match = re.search(r"data:image/[^;]+;base64,([A-Za-z0-9+/=]+)", content)

        if http_match:
            print("[INFO] 检测到 HTTP 图片链接，正在下载...")
            img_bytes = requests.get(http_match.group(0), timeout=30).content
            with open(cover_local_path, "wb") as f:
                f.write(img_bytes)
        elif base64_match:
            print("[INFO] 检测到 Base64 图片，正在解码保存...")
            decode_base64_to_image(base64_match.group(1), cover_local_path)
        else:
            raise RuntimeError(f"未能提取到图片，响应预览: {str(res_json)[:200]}...")

        print(f"[INFO] 封面图成功保存至本地: {cover_local_path}")

    except Exception as e:
        err_msg = str(e)[:300] + "...(已截断)" if len(str(e)) > 300 else str(e)
        print(f"[EXCEPT] 封面图生成失败: {err_msg}，将采用 Mock 图代替。")
        cover_local_path = "mock_cover.jpg"
        if not os.path.exists(cover_local_path):
            with open(cover_local_path, "wb") as f:
                f.write(b"")

    token = get_wechat_access_token()
    thumb_media_id = "mock_thumb_media_id_123"

    if token and os.path.exists(cover_local_path):
        try:
            print("[INFO] 正在上传封面图至微信素材库...")
            upload_url = f"https://api.weixin.qq.com/cgi-bin/material/add_material?access_token={token}&type=thumb"
            with open(cover_local_path, "rb") as f:
                res = requests.post(upload_url, files={"media": f}, timeout=15).json()

            if "thumb_media_id" in res:
                thumb_media_id = res["thumb_media_id"]
            elif "media_id" in res:
                thumb_media_id = res["media_id"]
            print(f"[INFO] 微信封面图上传成功, Media ID: {thumb_media_id}")
        except Exception as e:
            print(f"[EXCEPT] 微信封面图上传发生异常: {str(e)}")

    return {
        "cover_image_path": cover_local_path,
        "wechat_thumb_media_id": thumb_media_id,
    }


# def clean_and_reformat_html(html_content: str, wechat_token: str = "", primary_color: str = "#0288d1") -> str:
#     """清洗 HTML：处理 LaTeX 公式、列表转换以及文本排版优化（支持动态主色调）。"""

#     # 1. 处理块级公式 $$...$$
#     def replace_block_formula(match):
#         latex_code = match.group(1).strip()
#         fallback_html = (
#             f'<p style="text-align:center;margin:18px 0;font-family:Georgia,serif;'
#             f'font-size:16px;font-weight:bold;color:{primary_color};">{latex_code}</p>'
#         )

#         latex_query = rf"\dpi{{300}} \bg_white \large {latex_code}"
#         encoded_latex = urllib.parse.quote(latex_query)
#         api_url = f"https://latex.codecogs.com/png.image?{encoded_latex}"

#         if wechat_token:
#             try:
#                 img_res = requests.get(api_url, timeout=8)
#                 if img_res.status_code == 200 and img_res.content.startswith(b"\x89PNG\r\n\x1a\n"):
#                     temp_formula_path = "temp_formula.png"
#                     with open(temp_formula_path, "wb") as f:
#                         f.write(img_res.content)

#                     upload_url = f"https://api.weixin.qq.com/cgi-bin/media/uploadimg?access_token={wechat_token}"
#                     with open(temp_formula_path, "rb") as f:
#                         res_json = requests.post(upload_url, files={"media": f}, timeout=8).json()

#                     if "url" in res_json:
#                         return (
#                             f'<img src="{res_json["url"]}" style="display:block;margin:18px auto;'
#                             f'max-height:80px;max-width:100%;" alt="{latex_code}">'
#                         )
#             except Exception as e:
#                 print(f"[EXCEPT] 块级公式生成异常: {str(e)}")

#         return fallback_html

#     html_content = re.sub(r"\$\$(.*?)\$\$", replace_block_formula, html_content, flags=re.DOTALL)

#     # 2. 处理行内公式 $...$
#     html_content = re.sub(
#         r"\$(.*?)\$",
#         rf'<span style="font-family:Georgia,serif;font-style:italic;color:{primary_color};margin:0 3px;">\1</span>',
#         html_content,
#         flags=re.DOTALL,
#     )

#     # 3. 优化列表结构
#     soup = BeautifulSoup(html_content, "html.parser")

#     for li in soup.find_all("li"):
#         if not li.get_text(strip=True):
#             li.decompose()

#     for ul_tag in soup.find_all(["ul", "ol"]):
#         li_tags = ul_tag.find_all("li", recursive=False)
#         list_container = soup.new_tag("section")
#         list_container["style"] = "margin: 15px 0;"

#         for idx, li in enumerate(li_tags):
#             li_content = li.decode_contents().strip()
#             if not li_content:
#                 continue

#             li_content = re.sub(r"^[•●▪✦\-*\s]+", "", li_content).strip()
#             if not li_content:
#                 continue

#             li_soup = BeautifulSoup(li_content, "html.parser")
#             for p_tag in li_soup.find_all("p"):
#                 p_tag.unwrap()
#             clean_li_content = str(li_soup)

#             li_div = soup.new_tag("section")
#             li_div["style"] = "display: flex; align-items: flex-start; margin-bottom: 8px;"

#             bullet_span = soup.new_tag("span")
#             bullet_span["style"] = (
#                 f"color: {primary_color}; margin-right: 8px; font-weight: bold; flex-shrink: 0; font-size: 15px;"
#             )
#             bullet_span.string = f"{idx + 1}." if ul_tag.name == "ol" else "✦"

#             content_div = soup.new_tag("section")
#             content_div["style"] = "color: #333; line-height: 1.8; font-size: 15px; text-align: justify;"
#             content_div.append(BeautifulSoup(clean_li_content, "html.parser"))

#             li_div.append(bullet_span)
#             li_div.append(content_div)
#             list_container.append(li_div)

#         ul_tag.replace_with(list_container)

#     # 4. 清理空段落与残余符号
#     for p in soup.find_all("p"):
#         if p.find_all(["img", "section", "svg", "iframe", "div", "table"]):
#             continue
#         p_text = p.get_text(strip=True)
#         if p_text in ["•", "●", "✦", "▪", "-", "*", ""]:
#             p.decompose()

#     html = str(soup)

#     # 5. Markdown 标记修复与样式转换
#     html = re.sub(r"\*\*(.*?)\*\*", rf'<strong style="color:{primary_color};font-weight:bold;">\1</strong>', html)
#     html = re.sub(r"\*(.*?)\*", r'<em style="color:#555;font-style:italic;">\1</em>', html)
#     html = re.sub(
#         r"`(.*?)`",
#         r'<code style="background-color:#f5f5f5;color:#e01b24;padding:2px 5px;border-radius:4px;'
#         r'font-family:monospace;font-size:14px;margin:0 2px;">\1</code>',
#         html,
#     )
#     html = re.sub(r"(<h[1-6][^>]*>)\s*#+\s*", r"\1", html)
#     html = re.sub(r"(<p[^>]*>)\s*#+\s*", r"\1", html)
#     html = re.sub(r"^\s*[#•●✦\-\*]\s*$", "", html, flags=re.MULTILINE)

#     return html


def initial_draft_layout_node(state: TeamState) -> dict:
    """节点：正文分段切块，结合 LLM 智能提取关键词、匹配视觉卡片与配色方案，一站式完成排版。"""
    raw_article = state.get("draft_article", "")

    director_llm = ChatOpenAI(
        model=os.getenv("MODEL_LLM"),
        api_key=os.getenv("API_KEY"),
        base_url=os.getenv("BASE_URL"),
        temperature=0.3,
        timeout=60,
    )

    # 1. 前置剥离正文开头的大标题（微信自动由 draft_title 承载）
    clean_article = re.sub(r"^\s*#\s+[^\n]+\n*", "", raw_article).strip()

    # 2. 智能分段（代码块内部即使有空行也作为一个整体段落）
    from wechat_assembler import split_markdown_paragraphs
    raw_paragraphs = split_markdown_paragraphs(clean_article)

    numbered_article_prompt = ""
    for idx, p in enumerate(raw_paragraphs):
        numbered_article_prompt += f"[段落 {idx + 1}]:\n{p}\n\n"
        
    sys_prompt = f"""你是一位顶尖的微信公众号排版与视觉设计专家。请根据提供的文章段落，完成公众号排版方案的自动化决策。

【核心任务清单】
1. 主色调与视觉决定：你必须分析文章核心主题与情绪基调（如：重磅发布选橙红、开源代码选松石青、前沿理论选深邃紫），从视觉色卡库中匹配最符合文章特性的主色调 primary_color 与配套浅色背景 secondary_bg。
2. 关键词高亮提取：提取 3 到 6 个文章的核心技术或业务关键词，用于后续的强调美化。
3. 组件卡片精准匹配：深度扫描正文，提取 1 到 4 个最适合视觉强化的段落，匹配原子组件库并转化为结构化数据，但注意！不能过度省略原文内容！若原文内容复杂无法套入卡片中就放弃加入卡片！


【视觉色卡库 (visual_config 选色参考)】
1. 🔥 重磅发布/性能突破/SOTA（性能提升、新架构、突破性成果）：
   primary_color: "#e64a19" | secondary_bg: "#fdf4f2"

2. 🌿 开源项目/工程实践/轻量教程（代码开源、工具落地、实战）：
   primary_color: "#009688" | secondary_bg: "#e6f2f1"

3. 💜 深度算法/数学公式（推导严密、理论证明、学术）：
   primary_color: "#673ab7" | secondary_bg: "#f7f4fc"

4. ⚡ 避坑指南/预警踩坑/局限性分析（包含缺陷、硬件限制、踩坑）：
   primary_color: "#d9534f" | secondary_bg: "#fff8f8"

5. 📘 通用科技/AI分析（仅在无突出亮点时使用）：
   primary_color: "#0288d1" | secondary_bg: "#f4f8fa"

6. 🖤 黑客极客/底层架构（底层重构、C++/CUDA优化）：
   primary_color: "#2c3e50" | secondary_bg: "#f2f4f5"

【可匹配的原子组件库规范 (cards)】
请从文中选择合适段落转化为 0 到 4 个卡片(注意：匹配卡片的目的是“锦上添花”提升阅读体验。如果文章中某些段落不具备强烈的结构化特征，严禁强行硬套卡片！)，提取 type、覆盖的段落编号列表 target_paragraphs 及对应 data：

1. takeaway（核心金句）：极具启发性的核心总结、金句或结论。
   data: {{"quote_text": "核心金句内容..."}}
2. warning（避坑预警）：技术局限性、复现坑点、硬件门槛或安全风险警示。
   data: {{"title": "避坑提示", "content": "注意事项内容...", "alert_type": "warning"}}
3. code（代码块）：核心算法代码片段、Python 实现或伪代码。
   data: {{"language": "Python"}}
4. qa（疑难解答）：针对关键疑难问题的自问自答或常见疑问解释。
   data: {{"question": "为什么选择此方案？", "answer": "回答内容..."}}
5. resource（开源资源）：开源仓库、论文 PDF、数据集下载链接或获取提示。
   data: {{"title": "开源代码与数据集", "desc": "包含完整权重", "link_info": "GitHub 开源"}}
6. checklist（总结清单）：结尾或章节末尾多条并行列举的核心 Takeaway 总结。
   data: {{"title": "本文核心要点总结", "items": ["要点1", "要点2"]}}
7. pipeline（算法流程）：描述具有先后顺序的系统步骤或处理阶段（至少3步）。注意分辨是否具有先后顺序！并不是按顺序标号的段落就一定是先后顺序！
   data: {{"steps": ["第一步：数据预处理", "第二步：特征提取", "第三步：模型推理"]}}
8. spec（配置清单）：集中列出的模型结构参数、超参数或实验配置。
   data: {{"title": "模型训练超参数配置", "specs": {{"Batch Size": "64", "Learning Rate": "3e-4"}}}}

【严格执行规则】
1. 段落匹配：卡片中的 target_paragraphs 必须包含该卡片替换掉的所有段落编号（数组格式，如 [1] 或 [1, 2]）。
2. 色卡约束：切勿硬套默认蓝色，必须根据文章主题匹配色卡库中最适合的 primary_color 和 secondary_bg。
3. 输出规则：严格只输出标准 JSON 格式，不要包含任何说明解释文字。
4. 公式避让原则：严禁将单独的数学公式划归为 code（代码卡片）或任何其他卡片类型。所有数学公式必须保留在正文普通段落中，交由专用公式引擎处理。
5. 特别注意！对于复杂段落，优先保证原文正确性，宁可不插入卡片也不能因为插入卡片导致原文意思表述不清不全！不可自己提炼原文内容导致原文细节有遗漏！！！

【输入数据预览】
文章段落预览:
{numbered_article_prompt}

【输出 JSON 格式 Standard Schema】
{{
    "visual_config": {{
        "primary_color": "#HEX主色调",
        "secondary_bg": "#HEX背景色",
        "highlight_keywords": ["核心关键词1", "核心关键词2"]
    }},
    "cards": [
        {{
            "type": "takeaway",
            "target_paragraphs": [1],
            "data": {{ "quote_text": "核心金句内容" }}
        }}
    ]
}}"""

    print("[INFO] 视觉 Agent 正在基于文章语义分析视觉配色与匹配格式卡片...")
    semantic_config = {}

    try:
        response = director_llm.invoke([
            SystemMessage(content=sys_prompt),
            HumanMessage(content=f"请为以上文章指定配色与匹配卡片。段落总数共 {len(raw_paragraphs)} 段。"),
        ])
        res_text = response.content.strip()

        if "```json" in res_text:
            res_text = res_text.split("```json")[1].split("```")[0].strip()
        elif "```" in res_text:
            res_text = res_text.split("```")[0].split("```")[0].strip()

        semantic_config = json.loads(res_text)
        cards_matched = semantic_config.get("cards", [])

        visual_cfg = semantic_config.get("visual_config", {})
        p_color = visual_cfg.get("primary_color")
        bg_color = visual_cfg.get("secondary_bg")
        print(f"🔥 [DEBUG] 大模型决策选定的主色调: {p_color} | 辅助背景色: {bg_color}")

        print(f"[INFO] 成功匹配到 {len(cards_matched)} 个语义卡片:")
        for idx, c in enumerate(cards_matched, 1):
            c_type = c.get("type", "unknown")
            t_paras = c.get("target_paragraphs", [])
            print(f"       ├─ 卡片 [{idx}]: 类型=[{c_type:<10}] | 覆盖段落编号: {t_paras}")

    except Exception as e:
        print(f"[EXCEPT] 排版决策 JSON 解析失败: {str(e)}，改用默认科技蓝配色方案。")
        semantic_config = {
            "visual_config": {"primary_color": "#0288d1", "secondary_bg": "#f4f8fa", "highlight_keywords": []},
            "cards": [],
        }

    # 一站式组装（公式、卡片替换、样式注入内部闭环完成）
    wechat_token = get_wechat_access_token()
    html_code = assemble_wechat_html(raw_article, semantic_config, wechat_token=wechat_token)

    return {
        "wechat_html": html_code,
        "draft_article": raw_article,
        "retry_count": 0,
        "is_approved": False,
    }


def wechat_upload_node(state: TeamState) -> dict:
    """节点：自动提取草稿 HTML 中的图片标签，上传本地/网络图片至微信 CDN，并根据长宽比动态美化为公众号卡片。"""
    current_html = state.get("wechat_html", "")
    wechat_access_token = get_wechat_access_token()

    if not current_html:
        print("[WARN] HTML 内容为空，跳过图片上传。")
        return {"wechat_html": current_html}

    soup = BeautifulSoup(current_html, "html.parser")
    img_tags = soup.find_all("img")

    if not img_tags:
        print("[INFO] 当前文章中未检测到图片标签，跳过微信 CDN 上传。")
        return {"wechat_html": current_html}

    print(f"[INFO] 在文章中检测到 {len(img_tags)} 张图片，开始逐一处理并上传至微信 CDN...")

    for idx, img in enumerate(img_tags, 1):
        original_src = img.get("src", "").strip()
        alt_text = img.get("alt", "").strip() or img.get("title", "").strip()

        if not original_src:
            continue

        # 过滤已经属于微信 CDN 的图片（如公式图片或已上传过的图片）
        if "mmbiz.qpic.cn" in original_src or "qpic.cn" in original_src:
            print(f"[INFO] 图片 [{idx}] 已是微信 CDN 链接，跳过上传。")
            continue

        local_img_path = original_src
        is_temp_download = False

        # 如果是 HTTP 外链图片，先下载到本地临时文件再上传给微信
        if original_src.startswith("http://") or original_src.startswith("https://"):
            try:
                print(f"[INFO] 正在下载外链图片 [{idx}]: {original_src[:50]}...")
                dl_res = requests.get(original_src, timeout=15)
                if dl_res.status_code == 200:
                    temp_ext = "png" if "png" in original_src.lower() else "jpg"
                    local_img_path = f"temp_web_img_{idx}.{temp_ext}"
                    with open(local_img_path, "wb") as f:
                        f.write(dl_res.content)
                    is_temp_download = True
            except Exception as e:
                print(f"[EXCEPT] 下载外链图片失败: {str(e)}")

        wechat_img_url = ""

        # 上传至微信 CDN 获取官方 mmbiz 链接
        if wechat_access_token and os.path.exists(local_img_path) and os.path.getsize(local_img_path) > 0:
            try:
                print(f"[INFO] 正在将图片 [{idx}] ({local_img_path}) 上传至微信 CDN...")
                upload_url = f"https://api.weixin.qq.com/cgi-bin/media/uploadimg?access_token={wechat_access_token}"
                with open(local_img_path, "rb") as f:
                    res_json = requests.post(upload_url, files={"media": f}, timeout=15).json()

                if "url" in res_json:
                    wechat_img_url = res_json["url"]
                    print(f"[INFO] 图片 [{idx}] 上传微信 CDN 成功！")
                else:
                    print(f"[ERROR] 图片 [{idx}] 上传微信失败，返回: {res_json}")
            except Exception as e:
                print(f"[EXCEPT] 上传图片至微信 CDN 网络异常: {str(e)}")

        # 基于图片长宽比动态计算展示尺寸
        style_max_width = "100%"
        style_max_height = "500px"

        if os.path.exists(local_img_path):
            try:
                with Image.open(local_img_path) as im:
                    w, h = im.size
                    if h > 0:
                        ratio = w / h
                        if ratio > 1.3:
                            # 1. 横向大图/架构图/流程图：100% 全宽，不限制高度上限，确保字看得清
                            style_max_width = "100%"
                            style_max_height = "none"
                        elif ratio < 0.8:
                            # 2. 竖向长图/手机截图：限制宽度 55% 避免太长
                            style_max_width = "55%"
                            style_max_height = "480px"
                        else:
                            # 3. 方形图/单体模块图：限制宽度 100% 居中展示
                            style_max_width = "100%"
                            style_max_height = "none"
            except Exception as e:
                print(f"[WARN] 读取图片尺寸失败: {str(e)}")

        max_height_css = (
            f"max-height: {style_max_height} !important; " if style_max_height != "none" else ""
        )

        # 临时下载的文件清理
        if is_temp_download and os.path.exists(local_img_path):
            try:
                os.remove(local_img_path)
            except Exception:
                pass

        # 兜底 URL
        if not wechat_img_url:
            wechat_img_url = original_src if original_src.startswith("http") else f"https://mmbiz.qpic.cn/mock_img_{idx}.png"

        # 组装微信公众号美化插图卡片（动态传入 style_max_width 和 max_height_css）
        caption_html = (
            f'<p style="font-size: 13px; color: #888; margin-top: 8px; text-align: center; line-height: 1.4; font-family: sans-serif;">{alt_text}</p>'
            if alt_text
            else ""
        )

        card_html_str = (
            f'<section style="margin: 22px 0; text-align: center;">'
            f'<img src="{wechat_img_url}" style="display: block; margin: 0 auto; max-width: {style_max_width} !important; {max_height_css} width: auto !important; height: auto !important; object-fit: contain !important; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.08);" />'
            f'{caption_html}'
            f'</section>'
        )

        new_card_soup = BeautifulSoup(card_html_str, "html.parser").find("section")

        # 替换 DOM 节点：若 <img> 在独立的 <p> 标签中，则替换整个 <p>，否则替换 <img> 本身
        parent_p = img.find_parent("p")
        if parent_p and len(parent_p.find_all(True)) == 1:  # <p> 中仅有这一个 <img>
            parent_p.replace_with(new_card_soup)
        else:
            img.replace_with(new_card_soup)

    return {"wechat_html": str(soup)}


def create_initial_draft_node(state: TeamState) -> dict:
    """节点：在微信公众号草稿箱中创建新草稿。"""
    html_content = state["wechat_html"]
    wechat_token = get_wechat_access_token()
    thumb_media_id = state.get("wechat_thumb_media_id")

    raw_article = state.get("draft_article", "")
    article_title = state.get("article_title") or extract_article_title(raw_article)
    author_name = os.getenv("WECHAT_AUTHOR_NAME", "默认公众号名称")

    media_id = None
    if wechat_token:
        try:
            draft_url = f"https://api.weixin.qq.com/cgi-bin/draft/add?access_token={wechat_token}"
            payload = {
                "articles": [
                    {
                        "title": article_title,
                        "author": author_name,
                        "digest": article_title,
                        "content": html_content,
                        "thumb_media_id": thumb_media_id,
                        "need_open_comment": 0,
                        "only_fans_can_comment": 0,
                    }
                ]
            }
            res = requests.post(
                draft_url,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json; charset=utf-8"},
                timeout=15,
            ).json()

            if "media_id" in res:
                media_id = res["media_id"]
                print(f"[INFO] 微信草稿创建成功 | 标题: 《{article_title}》 | 作者: {author_name} | Media ID: {media_id}")
            else:
                print(f"[ERROR] 草稿创建失败，返回响应: {res}")
        except Exception as e:
            print(f"[EXCEPT] 创建草稿请求发生网络异常: {str(e)}")

    return {
        "wechat_media_id": media_id,
        "article_title": article_title,
    }


def universal_web_agent(context, vlm_model, goal: str, draft_title: str = "自动排版测试推文") -> bool:
    """视觉 Web Agent：由大模型自主观察屏幕、思考并决策进入草稿编辑器。"""
    max_steps = 10
    print(f"[AGENT] 视觉 Web Agent 启动，目标: {goal}")

    for step in range(max_steps):
        time.sleep(2)

        page = context.pages[-1]
        page.bring_to_front()

        # 检测是否已进入富文本编辑器
        if "appmsg_edit" in page.url or "action=edit" in page.url:
            print("[AGENT] 成功检测到页面已进入富文本编辑器 (appmsg_edit)。")
            return True

        screenshot_path = f"temp/agent_step_{step + 1}.png"
        page.screenshot(path=screenshot_path)
        base64_img = encode_image_to_base64(screenshot_path)

        system_prompt = f"""你是一个具备通用网页操作能力的自主视觉 Web Agent。
你能够看懂网页界面 (UI)，并根据目标自主决策下一步操作。

【公众号草稿箱重要操作规则】：
1. 如果当前页面在首页，优先寻找'草稿箱'进入草稿列表，如果没有，点击'内容管理'这个折叠菜单，然后再寻找'草稿箱'；或者滚动屏幕找到'全部草稿'进入草稿列表。
2. 在草稿列表中找到目标文章《{draft_title}》时，绝对不能直接点击文章标题文本（避免触发只读预览）。
3. 找到目标文章时，必须选择 `hover_and_edit` 动作，悬停在卡片上并点击出现的【编辑】按钮/铅笔图标。

【动作空间 (Action Space)】：
1. click: 点击普通文本或菜单按钮。
2. hover_and_edit: 悬停在目标推文卡片上并点击【编辑】按钮 (需提供 target_text 为文章标题)。
3. scroll: 滚动页面 (direction: "up" 或 "down")。
4. finish: 已达成目标，结束任务。

请观察截图并严格输出 JSON 格式：
{{
    "thought": "对当前界面的思考...",
    "action": "click" | "hover_and_edit" | "scroll" | "finish",
    "target_text": "要操作的具体标题或按钮文本",
    "direction": "down",
    "is_goal_reached": true | false
}}"""

        user_message = HumanMessage(content=[
            {"type": "text", "text": f"最终目标: {goal}\n当前推文标题: {draft_title}\n做出下一步决策："},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}},
        ])

        try:
            response = vlm_model.invoke([SystemMessage(content=system_prompt), user_message])
            res_text = response.content.strip()

            if "```json" in res_text:
                res_text = res_text.split("```json")[1].split("```")[0].strip()
            elif "```" in res_text:
                res_text = res_text.split("```")[1].split("```")[0].strip()

            res_data = json.loads(res_text)
            action = res_data.get("action")
            target_text = res_data.get("target_text", "")
            is_goal_reached = res_data.get("is_goal_reached", False)

            print(f"[AGENT Step {step + 1}] 思考过程: {res_data.get('thought')}")

            if is_goal_reached or action == "finish":
                print("[AGENT] 判定已成功达成目标。")
                return True

            if action == "hover_and_edit" or (action == "click" and draft_title in target_text):
                print(f"[AGENT] 执行【编辑】点击操作: '{draft_title}'")
                try:
                    page.evaluate("""(targetTitle) => {
                        const cleanTarget = targetTitle.replace(/\\s+/g, '');
                        const allElems = Array.from(document.querySelectorAll('.weui-desktop-publish__cover__title, .weui-desktop-card__bd span, .weui-desktop-card__bd a'));
                        const titleElem = allElems.find(el => el.textContent.replace(/\\s+/g, '').includes(cleanTarget));
                        if (!titleElem) return;

                        const card = titleElem.closest('.weui-desktop-card, .publish_card_container, .weui-desktop-masonry-list__item');
                        if (!card) return;

                        const tooltipWrps = Array.from(card.querySelectorAll('.weui-desktop-tooltip__wrp'));
                        const editWrp = tooltipWrps.find(wrp => wrp.textContent.includes('编辑'));
                        if (!editWrp) return;

                        const editBtn = editWrp.querySelector('a.weui-desktop-icon-btn, a');
                        if (editBtn) editBtn.click();
                    }""", draft_title)

                    time.sleep(3)
                    if len(context.pages) > 1:
                        latest_page = context.pages[-1]
                        latest_page.bring_to_front()
                        latest_page.wait_for_load_state("domcontentloaded")
                        if "appmsg_edit" in latest_page.url or "action=edit" in latest_page.url:
                            print("[AGENT] 成功通过新 Tab 进入微信富文本编辑器。")
                            return True
                except Exception as ex:
                    print(f"[EXCEPT] 点击编辑按钮异常: {str(ex)}")

            elif action == "click" and target_text:
                print(f"[AGENT] 点击目标元素: '{target_text}'")
                try:
                    page.get_by_text(target_text).first.click(force=True, timeout=3000)
                except Exception:
                    try:
                        page.locator(f"text={target_text}").first.click(force=True, timeout=3000)
                    except Exception as e:
                        print(f"[WARN] 文本点击未成功 ('{target_text}'): {str(e)}")

                time.sleep(2.5)

            elif action == "scroll":
                print("[AGENT] 向下滚动页面...")
                page.mouse.wheel(0, 500)

        except Exception as e:
            print(f"[EXCEPT] Agent 决策与执行发生异常: {str(e)}")

    return False


def enter_editable_draft_editor(context, page, draft_title: str):
    """在草稿箱中定位编辑按钮，并精准捕获新弹出的编辑器标签页。"""
    print(f"[INFO] 正在草稿箱寻找目标卡片 《{draft_title}》...")
    time.sleep(2)

    try:
        with context.expect_page(timeout=15000) as new_page_info:
            result = page.evaluate("""(targetTitle) => {
                const cleanTarget = targetTitle.replace(/\\s+/g, '');
                const allElems = Array.from(document.querySelectorAll('.weui-desktop-publish__cover__title, .weui-desktop-card__bd span, .weui-desktop-card__bd a'));
                const titleElem = allElems.find(el => el.textContent.replace(/\\s+/g, '').includes(cleanTarget));

                if (!titleElem) return { success: false, reason: '未找到标题节点' };

                const card = titleElem.closest('.weui-desktop-card, .publish_card_container, .weui-desktop-masonry-list__item');
                if (!card) return { success: false, reason: '未找到卡片容器' };

                const tooltipWrps = Array.from(card.querySelectorAll('.weui-desktop-tooltip__wrp'));
                const editWrp = tooltipWrps.find(wrp => wrp.textContent.includes('编辑'));
                if (!editWrp) return { success: false, reason: '未找到编辑按钮容器' };

                const editBtn = editWrp.querySelector('a.weui-desktop-icon-btn, a');
                if (!editBtn) return { success: false, reason: '未找到编辑按钮 <a>' };

                editBtn.click();
                return { success: true };
            }""", draft_title)

            print(f"[INFO] 草稿卡片点击结果: {result}")

        editor_page = new_page_info.value
        editor_page.wait_for_load_state("domcontentloaded")
        print(f"[INFO] 精确捕获到编辑器页面 | URL: {editor_page.url}")
        return editor_page

    except Exception as e:
        print(f"[EXCEPT] 进入编辑器过程发生异常或超时: {str(e)}")
        for p in context.pages:
            if "appmsg_edit" in p.url or "action=edit" in p.url:
                return p

    return None


def auto_publish_node(state: TeamState) -> dict:
    """基于 Playwright 精确导航进入编辑器，并通过多重 Selector 轮询完成推文发表。"""
    raw_article = state.get("draft_article", "")
    draft_title = state.get("article_title") or extract_article_title(raw_article)
    state_path = "wechat_state.json"

    if not os.path.exists(state_path):
        print("[ERROR] 未找到 wechat_state.json 登录凭证文件。")
        return {"is_approved": False, "review_reason": "未找到登录凭证文件"}

    print(f"[INFO] 启动自动发表节点 | 目标草稿: 《{draft_title}》")
    success = False

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=False,
                args=["--remote-debugging-port=9222", "--disable-blink-features=AutomationControlled", "--no-sandbox"],
            )
            context = browser.new_context(
                storage_state=state_path,
                viewport={"width": 1600, "height": 1000},
            )
            page = context.new_page()

            page.goto("https://mp.weixin.qq.com/", wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)

            # 1. 精确 DOM 定位进入编辑器
            editor_page = enter_editable_draft_editor(context, page, draft_title)

            # 2. DOM 定位失败时触发视觉 Web Agent 兜底
            if not editor_page:
                print("[WARN] DOM 定位未能进入编辑器，启动 universal_web_agent 视觉导航...")
                vlm = ChatOpenAI(
                    model=os.getenv("MODEL_VLM"),
                    api_key=os.getenv("API_KEY"),
                    base_url=os.getenv("BASE_URL"),
                    temperature=0.1,
                )
                agent_success = universal_web_agent(
                    context=context,
                    vlm_model=vlm,
                    goal=f"进入草稿《{draft_title}》的编辑页面",
                    draft_title=draft_title,
                )
                if agent_success:
                    editor_page = context.pages[-1]

            if not editor_page or ("appmsg_edit" not in editor_page.url and "action=edit" not in editor_page.url):
                print("[ERROR] 无法唤起或进入微信富文本编辑器。")
                browser.close()
                return {"is_approved": False, "review_reason": "无法进入编辑器"}

            print("[INFO] 成功进入微信富文本编辑器，准备执行发表动作...")
            editor_page.bring_to_front()
            time.sleep(2)

            # 点击编辑器底栏【发表】按钮
            print("[INFO] 正在定位底栏【发表】按钮...")
            bottom_publish_btn = editor_page.locator(
                "button:has-text('发表'), a:has-text('发表'), .js_publish_btn, button.weui-desktop-btn_primary:has-text('发表')"
            ).last

            if bottom_publish_btn.is_visible(timeout=5000):
                bottom_publish_btn.click(force=True)
                print("[INFO] 已成功点击底栏【发表】按钮，等待确认弹窗...")
            else:
                print("[WARN] 未找到底栏发表按钮，尝试滚动与降级点击...")
                editor_page.mouse.wheel(0, 1000)
                time.sleep(1)
                editor_page.locator("button:has-text('发表')").last.click(force=True)

            time.sleep(3)

            # 轮询处理多层弹窗确认
            candidate_selectors = [
                ".weui-desktop-dialog button.weui-desktop-btn_primary",
                ".weui-desktop-dialog__ft button.weui-desktop-btn_primary",
                "button.weui-desktop-btn_primary:has-text('确认发表')",
                "button.weui-desktop-btn_primary:has-text('继续发表')",
                "button.weui-desktop-btn_primary:has-text('发表')",
                "button.weui-desktop-btn_primary:has-text('群发')",
                "button.weui-desktop-btn_primary:has-text('确定')",
                ".weui-desktop-btn_primary",
            ]

            max_modal_clicks = 3
            for step in range(max_modal_clicks):
                clicked_in_this_step = False

                qrcode_modal = editor_page.locator(".weui-desktop-dialog").filter(has_text="扫码").first
                try:
                    if qrcode_modal.is_visible(timeout=1000):
                        print("[NOTICE] 触发微信安全扫码验证！请在 30 秒内使用管理员微信扫码确认...")
                        time.sleep(15)
                except Exception:
                    pass

                for sel in candidate_selectors:
                    btn = editor_page.locator(sel).first
                    try:
                        if btn.is_visible(timeout=1500):
                            btn_text = btn.inner_text().strip()
                            print(f"[INFO] 找到弹窗确认按钮 [文本: '{btn_text}'] (Selector: {sel})，准备点击...")
                            btn.click(force=True)
                            clicked_in_this_step = True
                            time.sleep(2.5)
                            break
                    except Exception:
                        continue

                if clicked_in_this_step:
                    success = True
                    time.sleep(1.5)
                    has_more_confirm_btns = False
                    for sel in candidate_selectors:
                        try:
                            if editor_page.locator(sel).first.is_visible(timeout=500):
                                has_more_confirm_btns = True
                                break
                        except Exception:
                            pass

                    if not has_more_confirm_btns:
                        print(f"[INFO] 文章 《{draft_title}》 已成功点击发表按钮！")
                        break
                else:
                    print(f"[WARN] 弹窗处理第 {step + 1} 轮未检测到可点击的确认按钮。")
                    if step > 0:
                        success = True
                    break

            time.sleep(3)
            browser.close()

    except Exception as e:
        print(f"[EXCEPT] 自动发表节点执行发生异常: {str(e)}")

    return {
        "wechat_html": state.get("wechat_html", ""),
        "is_approved": success,
        "review_reason": "文章已成功发表" if success else "发表失败",
    }


# =====================================================================
# LangGraph 工作流编排
# =====================================================================

wechat_builder = StateGraph(TeamState)

# 注册节点
wechat_builder.add_node("generate_cover", generate_and_upload_cover_node)
wechat_builder.add_node("initial_draft_layout", initial_draft_layout_node)
wechat_builder.add_node("wechat_upload", wechat_upload_node)
wechat_builder.add_node("create_initial_draft", create_initial_draft_node)
wechat_builder.add_node("auto_publish", auto_publish_node)

# 编排节点执行流程
wechat_builder.add_edge(START, "generate_cover")
wechat_builder.add_edge("generate_cover", "initial_draft_layout")
wechat_builder.add_edge("initial_draft_layout", "wechat_upload")
wechat_builder.add_edge("wechat_upload", "create_initial_draft")
wechat_builder.add_edge("create_initial_draft", "auto_publish")
wechat_builder.add_edge("auto_publish", END)

wechat_subgraph = wechat_builder.compile()


def run_wechat_publisher(
    draft_article: Optional[str] = None,
    article_title: Optional[str] = None
) -> Dict[str, Any]:
    """微信公众号排版与发布 Skill 核心入口函数。"""

    target_file = "draft.md"

    # 情况 A：外部/Agent 传了文章进来 ➡️ 第一时间写入 draft.md 落盘存盘
    if draft_article and draft_article.strip():
        try:
            with open(target_file, "w", encoding="utf-8") as f:
                f.write(draft_article)
            print(f"[SAFETY] 收到文章，已自动覆盖写入至本地 {target_file}")
        except Exception as e:
            print(f"[WARN] 写入 {target_file} 失败: {str(e)}")

    # 情况 B：未传文章（本地测试） 
    else:
        if os.path.exists(target_file):
            try:
                with open(target_file, "r", encoding="utf-8") as f:
                    draft_article = f.read()
                print(f"[INFO] 未收到外部传参，已自动读取本地现有的 {target_file}")
            except Exception as e:
                print(f"[ERROR] 读取本地 {target_file} 失败: {str(e)}")
        else:
            return {
                "success": False,
                "article_title": "",
                "wechat_media_id": None,
                "review_reason": f"未收到文章内容，且本地不存在 {target_file} 文件",
                "wechat_html": None,
            }

    # 组装输入参数，给工作流运行
    initial_input = {"draft_article": draft_article}
    if article_title:
        initial_input["article_title"] = article_title

    print("[SKILL] 接收到排版任务，开始执行工作流...")

    try:
        result = wechat_subgraph.invoke(initial_input)
        success = result.get("is_approved", False)
        return {
            "success": success,
            "article_title": result.get("article_title", ""),
            "wechat_media_id": result.get("wechat_media_id"),
            "review_reason": result.get("review_reason") or ("文章发表成功" if success else "草稿已生成"),
            # "wechat_html": result.get("wechat_html", ""),
        }
    except Exception as e:
        print(f"[SKILL ERROR] 工作流执行异常: {str(e)}")
        return {
            "success": False,
            "article_title": article_title or "",
            "wechat_media_id": None,
            "review_reason": f"技能运行异常: {str(e)}，请检查 {target_file} 文件",
            # "wechat_html": None,
        }

@tool
def wechat_publisher_tool(draft_article: str, article_title: str = "") -> str:
    """将 Markdown 格式的文章自动排版美化，并发布到微信公众号。

    :param draft_article: Markdown 格式的文章正文内容（必须包含文章主体）
    :param article_title: 文章标题（可选，若不填则会自动从文章正文中提取）
    :return: 包含发布状态 (success)、草稿 Media ID 和反馈信息的 JSON 字符串
    """
    result = run_wechat_publisher(
        draft_article=draft_article,
        article_title=article_title if article_title else None
    )
    return json.dumps(result, ensure_ascii=False)


if __name__ == "__main__":
    output = run_wechat_publisher()
    
    print("\n[技能执行结果输出]:")
    print(json.dumps(output, ensure_ascii=False, indent=2))