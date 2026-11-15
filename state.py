from typing import Optional, TypedDict


class TeamState(TypedDict):
    """微信公众号排版与发布工作流的状态定义。"""

    # 提取/生成的文章标题与原始 Markdown 文章正文
    article_title: Optional[str]
    draft_article: Optional[str]

    # 封面图本地路径与微信素材库 Media ID
    cover_image_path: Optional[str]
    wechat_thumb_media_id: Optional[str]

    # 组装/渲染后的 HTML 与草稿 Media ID
    wechat_html: Optional[str]
    wechat_media_id: Optional[str]

    # 审查与发表状态字段
    is_approved: Optional[bool]
    review_reason: Optional[str]
    retry_count: Optional[int]