import base64
import re
from dotenv import load_dotenv
from PIL import Image


load_dotenv()

def decode_base64_to_image(base64_str: str, output_path: str) -> str:
    """【工具函数】将 Base64 字符串（或 Data URI）解码并保存为本地图片文件。"""
    try:
        # 1. 自动清洗：提取真正的 Base64 字符串（兼容 data:image/xxx;base64, 格式）
        if "base64," in base64_str:
            base64_str = base64_str.split("base64,")[1]
            
        # 2. 清洗尾部多余的 Markdown 括号、换行符或空格
        base64_str = base64_str.split(")")[0].strip()

        # 3. 解码为二进制数据
        img_bytes = base64.b64decode(base64_str)

        # 4. 写入文件
        with open(output_path, "wb") as f:
            f.write(img_bytes)

        return output_path
    except Exception as e:
        raise ValueError(f"Base64 图片解码保存失败: {str(e)}")


def encode_image_to_base64(image_path: str) -> str:
    """将图片按比例压缩并编码为 Base64 字符串（彻底解决 SiliconFlow 20015 体积超限报错）。"""
    try:
        with Image.open(image_path) as img:
            # RGBA / P 通道转 RGB（JPEG 不支持 Alpha 通道）
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            
            # 如果尺寸超过 1280px，按比例缩小，极大节省 Token 与网络体积
            if img.width > 1280 or img.height > 1280:
                img.thumbnail((1280, 1280), Image.Resampling.LANCZOS)
            
            import io
            buffer = io.BytesIO()
            # 压缩为 JPEG，质量设为 80（兼顾清晰度与体积）
            img.save(buffer, format="JPEG", quality=80)
            return base64.b64encode(buffer.getvalue()).decode("utf-8")
    except Exception as e:
        # 兜底：若非图片则直接读取二进制
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode("utf-8")


def extract_article_title(draft_article: str) -> str:
    """从 Markdown 文章草稿中自动提取一级标题 `# 标题`"""
    if not draft_article:
        return "公众号推文"
    # 优先匹配 Markdown 的 `# 标题`
    match = re.search(r"^#\s+(.+)$", draft_article, re.MULTILINE)
    if match:
        return match.group(1).strip()
    # 兜底：如果没写 `#`，直接取第一行非空文本
    lines = [line.strip() for line in draft_article.splitlines() if line.strip()]
    return lines[0] if lines else "公众号推文"


