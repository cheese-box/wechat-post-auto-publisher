# 🚀 微信公众号自动排版与发布技能 (WeChat Publisher Agent Skill)

这是一个专为 AI Agent（LangChain / CrewAI / AutoGen）设计的公众号自动化排版与发布技能工具（Skill）。能够接收 Markdown 格式的文章，自动进行语义分析、视觉配色搭配、生成原子组件卡片、绘制 AI 封面图、图片上传微信 CDN，并通过无头浏览器自动在微信公众号上进行发表。

---

## ✨ 核心特性

- **🎨 智能视觉排版**：大模型根据文章主题自动匹配调色盘与语义卡片（数据突破、代码块、金句等）。
- **🖼️ AI 视觉封面生成**：根据文章提炼 Prompt 并自动生成 16:9 高质量封面，上传微信素材库。
- **💾 安全存盘与离线双模**：外部传参自动覆盖备份至本地 `draft.md` 防崩溃；不传参时自动读取本地 `draft.md` 进行测试。
- **🌐 自动化 CDN 与发布**：外链图片自动转存微信 CDN，自动处理底层富文本编辑器发表流程。
- **⚡ 极简 Agent 输出**：输出极致精简的结构化 JSON 结果，省 Token 不乱码。

---

## 🛠️ 一、 环境依赖与安装

在首次使用本技能前，请确保 Python 环境（推荐 Python 3.10+）已准备就绪：

### 1. 安装依赖库
```bash
pip install -r requirements.txt
```

### 2. 安装 Playwright 无头浏览器
自动发表节点依赖 Playwright 内核，请运行命令安装 Chromium 浏览器：
```bash
playwright install chromium
```

---

## ⚙️ 二、 环境凭证配置 (.env)

复制项目根目录下的 `.env.example` 文件并重命名为 `.env`：

```bash
cp .env.example .env
```

并在 `.env` 中填入你的密钥信息：

```ini
# 1. 微信公众号 API 凭证 (微信公众平台后台获取)
WECHAT_APP_ID=
WECHAT_APP_SECRET=
WECHAT_AUTHOR_NAME=推文发布时的作者名

# 2. 大模型与视觉生成 API 配置
BASE_URL =
API_KEY=

# 3. 模型名称配置 
MODEL_LLM = "gpt-4o"
MODEL_VLM = "gpt-4o"
MODEL_PLM = "gemini-2.5-flash-image"
```

---

## 🔑 三、 账号初始化（首次使用必看）

自动化发表需要依赖微信后台的登录 Cookie。**首次使用技能前，请先在终端运行一次登录脚本：**

```bash
python login.py
```

* **操作**：运行后会弹出一个浏览器，请使用**微信公众号管理员或运营者微信扫码登录**。
* **效果**：登录成功后，脚本会自动生成 `wechat_state.json` 凭证文件。后续 Agent 运行将无需再次扫码。
* **此外**，需要在**微信开发者平台**中启用**IP白名单**

---

## 💡 四、 本地独立测试

你可以直接在项目根目录下的 `draft.md` 文件里写入 Markdown 文章，然后在终端运行：

```bash
python publisher.py
```

程序会自动读取本地 `draft.md` 并完成全套排版发表测试。

---

## 🔌 五、 在 Agent 中接入技能 (Tool API)

本技能导出了标准 LangChain `@tool` 工具接口 `wechat_publisher_tool`：

### 1. 工具接口规范

* **工具名称**：`wechat_publisher_tool`
* **输入参数 (Inputs)**：
  * `draft_article` *(str, 选填)*：Markdown 格式的文章正文。若为空则自动读取本地 `draft.md`。
  * `article_title` *(str, 选填)*：文章标题。若为空则自动从文章正文提取。
* **返回结果 (Outputs)**：
  ```json
  {
    "success": true,
    "article_title": "文章标题",
    "wechat_media_id": "草稿箱MediaID",
    "review_reason": "文章发表成功"
  }
  ```

### 2. LangChain 接入示例

```python
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

# 导入本技能导出的 Tool
from auto_publisher import wechat_publisher_tool

# 初始化你的主 Agent
llm = ChatOpenAI(model="gpt-4o", temperature=0)
tools = [wechat_publisher_tool]
agent = create_react_agent(llm, tools)

# 运行 Agent
response = agent.invoke({
    "messages": [("user", "帮我写一篇关于 Python 异步编程的技术文章，并排版发布到公众号。")]
})

print(response["messages"][-1].content)
```