import os
import time
import xml.etree.ElementTree as ET

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
import requests

from publisher import wechat_subgraph
from state import TeamState

load_dotenv()


def fetch_arxiv_papers(category: str = "cs.CL", max_results: int = 2) -> list[dict]:
    """从 ArXiv 官方 API 自动抓取最新论文信息（带 429 限流自动重试机制）。"""
    url = (
        "https://export.arxiv.org/api/query?"
        f"search_query=cat:{category}&start=0&max_results={max_results}"
        "&sortBy=submittedDate&sortOrder=descending"
    )

    print(f"[INFO] 正在从 ArXiv 抓取最新的 {max_results} 篇 [{category}] 论文...")
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 AutoPublisher/1.0"
        )
    }

    max_retries = 3
    wait_seconds = 5
    response = None

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(url, headers=headers, timeout=20)
            
            if response.status_code == 429:
                print(f"[WARN] 触发 ArXiv 429 限流，等待 {wait_seconds} 秒后进行第 {attempt}/{max_retries} 次重试...")
                time.sleep(wait_seconds)
                wait_seconds *= 2
                continue

            response.raise_for_status()
            break
        except requests.exceptions.RequestException as e:
            print(f"[WARN] 请求 ArXiv 发生网络异常 ({e})，等待 {wait_seconds} 秒后重试...")
            time.sleep(wait_seconds)
            wait_seconds *= 2

    if not response or response.status_code != 200:
        raise RuntimeError(f"多次重试仍无法获取 ArXiv 数据，HTTP 状态码: {response.status_code if response else 'None'}")

    xml_data = response.content
    root = ET.fromstring(xml_data)
    ns = {"atom": "http://www.w3.org/2005/Atom"}

    papers = []
    for entry in root.findall("atom:entry", ns):
        title = entry.find("atom:title", ns).text.strip().replace("\n", " ")
        summary = entry.find("atom:summary", ns).text.strip().replace("\n", " ")
        arxiv_id_url = entry.find("atom:id", ns).text.strip()

        arxiv_id = arxiv_id_url.split("/abs/")[-1]
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

        papers.append({
            "title": title,
            "summary": summary,
            "paper_url": pdf_url,
        })

    print(f"[INFO] 成功抓取到 {len(papers)} 篇论文。")
    return papers


def generate_pure_markdown_draft(title: str, summary: str) -> str:
    """利用 LLM 生成带图片的 Markdown 论文推广草稿（带网络异常自动重试机制）。"""
    # 优先读取环境变量，兼容配置名称
    api_key = os.getenv("YUNWU_API_KEY") or os.getenv("API_KEY")
    base_url = os.getenv("YUNWU_BASE_URL") or os.getenv("BASE_URL") or "https://yunwu.ai/v1"
    model_name = os.getenv("MODEL_LLM", "gpt-4o")

    llm = ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=0.3,
        timeout=60,
    )

    # 修改后的 Prompt：指示大模型在文中插入可直接加载的高清示例图片
    sys_prompt = """你是一位顶尖的 AI 科技公众号资深主笔。
请根据传入的论文标题和英文摘要，撰写一篇通俗易懂、结构清晰、排版丰富的公众号推文草稿。要求必须输出纯 Markdown 格式。

【排版与插图要求】：
1. 结构清晰：使用 Markdown 标题、重点加粗、列表以及金句总结。
2. 必须包含配图：请在文章的核心架构介绍、工作原理或实验结果等位置，插入 2~3 张 Markdown 图片。
   图片统一使用通用高清示意图 URL，格式如下：
   ![图片详细描述](https://picsum.photos/800/400?random=1)
   ![图片详细描述](https://picsum.photos/400/400?random=2)
   （注意：递增 random 参数，确保每张图片不同,可以用不同的宽高比）"""

    user_prompt = f"论文标题: {title}\n\n论文摘要 (Abstract):\n{summary}"

    print(f"[INFO] 正在为论文《{title[:30]}...》生成 Markdown 文本草稿...")

    # 增加 3 次自动重试机制，防止网络断连导致整个批处理终止
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            response = llm.invoke([
                SystemMessage(content=sys_prompt),
                HumanMessage(content=user_prompt),
            ])
            draft = response.content.strip()

            if "```markdown" in draft:
                draft = draft.split("```markdown")[1].split("```")[0].strip()
            elif "```" in draft:
                draft = draft.split("```")[1].split("```")[0].strip()

            return draft

        except Exception as e:
            print(f"[WARN] 调用 LLM 生成草稿发生网络异常 (第 {attempt}/{max_retries} 次): {e}")
            if attempt < max_retries:
                time.sleep(4)  # 发生异常时休眠 4 秒后重试
            else:
                raise e


def run_batch_test(paper_count: int = 2, category: str = "cs.CL") -> None:
    """批量测试主入口。"""
    papers = fetch_arxiv_papers(category=category, max_results=paper_count)

    for idx, paper in enumerate(papers, 1):
        print("\n" + "=" * 70)
        print(f"[INFO] 开始执行测试用例 [{idx}/{paper_count}]")
        print(f"📄 论文标题: {paper['title']}")
        print(f"🔗 PDF 链接: {paper['paper_url']}")
        print("=" * 70)

        try:
            # 1. 自动生成带插图的 Markdown 草稿
            draft_markdown = generate_pure_markdown_draft(
                title=paper["title"],
                summary=paper["summary"],
            )

            # 2. 构建初始状态
            initial_state: TeamState = {
                "article_title": paper["title"],
                "draft_article": draft_markdown,
                "cover_image_path": None,
                "wechat_thumb_media_id": None,
                "wechat_html": None,
                "wechat_media_id": None,
                "is_approved": False,
                "review_reason": None,
                "retry_count": 0,
            }

            # 3. 触发 LangGraph 工作流
            print("[INFO] 正在启动 wechat_subgraph 工作流...")
            result = wechat_subgraph.invoke(initial_state)
            print(f"[INFO] 用例 [{idx}] 执行成功！")
            print(f"[INFO] 生成的微信草稿 Media ID: {result.get('wechat_media_id')}")

        except Exception as e:
            print(f"[EXCEPT] 用例 [{idx}] 执行失败，已跳过当前用例: {str(e)}")

        # 4. 批处理防限流：每处理完一篇，暂停 3 秒，给网络和 API 留出缓冲时间
        if idx < paper_count:
            print("[INFO] 等待 3 秒后进行下一篇论文处理...")
            time.sleep(3)


if __name__ == "__main__":
    run_batch_test(paper_count=10, category="cs.CL")