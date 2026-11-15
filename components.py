from typing import Any


def _to_str(val: Any) -> str:
    """强制把 list、dict 或 None 转化为安全字符串，防止 .strip() 报错。"""
    if isinstance(val, list):
        return " ".join([str(x) for x in val])
    return str(val or "")


# def build_metric_card(number: str, label: str, description: str, primary_color: str, bg_color: str) -> str:
#     """【原子组件 1：数据/指标突破卡片】直接在生成时压平文本与 HTML，消除空格与异常换行"""
#     clean_num = _to_str(number).strip().replace("\n", "")
#     clean_lbl = _to_str(label).strip().replace("\n", "")
#     clean_desc = _to_str(description).strip().replace("\n", "")

#     return (
#         f'<section style="background-color: {bg_color}; border-radius: 8px; border: 1px solid {primary_color}; padding: 14px 16px; margin: 12px 0; box-sizing: border-box;">'
#         f'<section style="display: table; width: 100%; box-sizing: border-box;">'
#         f'<section style="display: table-cell; vertical-align: middle; width: 38%; text-align: left;">'
#         f'<section style="font-size: 26px; font-weight: 900; color: {primary_color}; line-height: 1.1; font-family: -apple-system, sans-serif;">{clean_num}</section>'
#         f'<section style="font-size: 11px; color: {primary_color}; font-weight: bold; margin-top: 4px;">{clean_lbl}</section>'
#         f'</section>'
#         f'<section style="display: table-cell; vertical-align: middle; width: 62%; font-size: 13px; color: #444444; line-height: 1.6; text-align: left; border-left: 2px solid {primary_color}; padding-left: 12px;">'
#         f'{clean_desc}'
#         f'</section>'
#         f'</section>'
#         f'</section>'
#     )


def build_pipeline_card(steps: list, primary_color: str, bg_color: str) -> str:
    """【原子组件 2：算法流程/步骤卡片】"""
    items_html = ""
    for idx, step in enumerate(steps):
        arrow = f'<section style="text-align: center; color: {primary_color}; font-size: 12px; line-height: 1.2; margin: 3px 0;">↓</section>' if idx < len(steps) - 1 else ''
        items_html += f"""
        <section style="background-color: #ffffff; border-left: 4px solid {primary_color}; border-radius: 0 4px 4px 0; padding: 10px 12px; font-size: 13.5px; color: #333333; line-height: 1.6; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
            <strong style="color: {primary_color}; margin-right: 4px;">STEP {idx + 1}:</strong> {step}
        </section>
        {arrow}
        """

    return f"""
    <section style="background-color: {bg_color}; border-radius: 8px; padding: 14px; margin: 20px 0; box-sizing: border-box;">
        <section style="font-size: 12px; font-weight: bold; color: {primary_color}; margin-bottom: 10px; display: block;">
            <span style="background: {primary_color}; color: #ffffff; padding: 2px 6px; border-radius: 3px; font-size: 10px; margin-right: 6px; vertical-align: middle;">WORKFLOW</span>
            <span style="vertical-align: middle;">处理流程</span>
        </section>
        {items_html}
    </section>
    """


# def build_formula_card(latex_code: str, explanation: str, primary_color: str, bg_color: str) -> str:
#     """【原子组件 3：公式/定理聚焦卡片】"""
#     return f"""
#     <section style="background-color: {bg_color}; border-radius: 8px; border: 1px solid #e0e0e0; padding: 16px; margin: 20px 0; text-align: center; box-sizing: border-box;">
#         <section style="font-size: 11px; font-weight: bold; color: {primary_color}; letter-spacing: 1px; margin-bottom: 6px; text-transform: uppercase;">KEY MATHEMATICAL SPOTLIGHT</section>
#         <section style="font-family: Georgia, serif; font-size: 16px; font-weight: bold; color: {primary_color}; margin: 10px 0;">
#             {latex_code}
#         </section>
#         <section style="font-size: 13px; color: #666666; margin-top: 8px; padding-top: 8px; border-top: 1px dashed #cccccc; text-align: justify; line-height: 1.6;">
#             💡 <strong>公式解析：</strong> {explanation}
#         </section>
#     </section>
#     """


# def build_comparison_card(old_method: str, new_method: str, primary_color: str) -> str:
#     """【原子组件 4：A/B 对比卡片】"""
#     return f"""
#     <section style="margin: 20px 0; width: 100%; box-sizing: border-box;">
#         <section style="display: table; width: 100%; table-layout: fixed; box-sizing: border-box;">
#             <section style="display: table-cell; width: 48%; background-color: #f5f5f5; border-radius: 6px; padding: 12px; border-top: 3px solid #9e9e9e; vertical-align: top; box-sizing: border-box;">
#                 <section style="font-size: 11px; font-weight: bold; color: #616161; margin-bottom: 6px;">❌ 传统/现有方法</section>
#                 <section style="font-size: 12.5px; color: #555555; line-height: 1.5;">{old_method}</section>
#             </section>
#             <section style="display: table-cell; width: 4%;"></section>
#             <section style="display: table-cell; width: 48%; background-color: #ffffff; border-radius: 6px; padding: 12px; border-top: 3px solid {primary_color}; border-right: 1px solid #eee; border-bottom: 1px solid #eee; border-left: 1px solid #eee; vertical-align: top; box-sizing: border-box;">
#                 <section style="font-size: 11px; font-weight: bold; color: {primary_color}; margin-bottom: 6px;">✨ 本文提出方法</section>
#                 <section style="font-size: 12.5px; color: #222222; line-height: 1.5; font-weight: 500;">{new_method}</section>
#             </section>
#         </section>
#     </section>
#     """


def build_takeaway_card(quote_text: str, primary_color: str, bg_color: str) -> str:
    """【原子组件 5：核心 Insight / 结论金句卡片】"""
    clean_text = _to_str(quote_text).strip().replace("\n", "")
    return (
        f'<section style="background-color: {bg_color}; border-left: 4px solid {primary_color}; border-radius: 0 8px 8px 0; padding: 16px 18px; margin: 20px 0; box-sizing: border-box;">'
        f'<section style="font-size: 14.5px; font-weight: bold; color: #222222; line-height: 1.8;">'
        f'<span style="font-size: 18px; color: {primary_color}; font-family: Georgia, serif; margin-right: 2px;">“</span>'
        f'{clean_text}'
        f'<span style="font-size: 18px; color: {primary_color}; font-family: Georgia, serif; margin-left: 2px;">”</span>'
        f'</section></section>'
    )


# def build_multi_metric_card(metrics: list, primary_color: str, bg_color: str) -> str:
#     """
#     【原子组件 6：多维数据矩阵卡片 (2x2 网格布局)】
#     适用于：同时展示 2~4 个核心指标（如准确率、训练速度、显存占用、参数量）。
#     `metrics` 示例: [{"label": "准确率", "value": "98.5%", "sub": "+2.3% SOTA"}, ...]
#     """
#     rows_html = ""
#     for i in range(0, len(metrics), 2):
#         pair = metrics[i:i + 2]
#         cells_html = ""
#         for item in pair:
#             lbl = str(item.get("label", "")).strip().replace("\n", "")
#             val = str(item.get("value", "")).strip().replace("\n", "")
#             sub = str(item.get("sub", "")).strip().replace("\n", "")
#             sub_html = f'<section style="font-size: 10px; color: #888888; margin-top: 2px;">{sub}</section>' if sub else ''

#             cells_html += (
#                 f'<section style="display: table-cell; width: 50%; vertical-align: top; padding: 4px; box-sizing: border-box;">'
#                 f'<section style="background-color: #ffffff; border-radius: 6px; padding: 10px 8px; border: 1px solid #e8e8e8; text-align: center;">'
#                 f'<section style="font-size: 11px; color: #666666; font-weight: bold;">{lbl}</section>'
#                 f'<section style="font-size: 20px; font-weight: 900; color: {primary_color}; line-height: 1.2; margin-top: 4px; font-family: -apple-system, sans-serif;">{val}</section>'
#                 f'{sub_html}'
#                 f'</section>'
#                 f'</section>'
#             )

#         # 如果是奇数项，补充一个空白占位单元格保持网格对齐
#         if len(pair) < 2:
#             cells_html += '<section style="display: table-cell; width: 50%;"></section>'

#         rows_html += f'<section style="display: table-row;">{cells_html}</section>'

#     return (
#         f'<section style="background-color: {bg_color}; border-radius: 8px; padding: 8px; margin: 20px 0; box-sizing: border-box;">'
#         f'<section style="display: table; width: 100%; table-layout: fixed; box-sizing: border-box;">'
#         f'{rows_html}'
#         f'</section>'
#         f'</section>'
#     )


def build_code_card(code_text: str, language: str, primary_color: str) -> str:
    """
    【原子组件 7：暗黑模式代码/伪代码块卡片】
    适用于：展示核心算法伪代码或关键 Python/PyTorch 代码段。自带 Mac 窗口三色小圆点。
    """
    clean_lang = _to_str(language).strip().upper()
    # 彻底转义特殊字符与换行，确保微信编辑器不破坏代码缩进
    escaped_code = (
        code_text.strip()
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br>")
        .replace(" ", "&nbsp;")
    )

    return (
        f'<section style="background-color: #1e1e1e; border-radius: 8px; margin: 20px 0; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.15); box-sizing: border-box;">'
        f'<section style="background-color: #2d2d2d; padding: 8px 12px; display: table; width: 100%; box-sizing: border-box; border-bottom: 1px solid #3d3d3d;">'
        f'<section style="display: table-cell; vertical-align: middle;">'
        f'<span style="display: inline-block; width: 10px; height: 10px; background-color: #ff5f56; border-radius: 50%; margin-right: 6px;"></span>'
        f'<span style="display: inline-block; width: 10px; height: 10px; background-color: #ffbd2e; border-radius: 50%; margin-right: 6px;"></span>'
        f'<span style="display: inline-block; width: 10px; height: 10px; background-color: #27c93f; border-radius: 50%;"></span>'
        f'</section>'
        f'<section style="display: table-cell; vertical-align: middle; text-align: right; font-size: 11px; color: #888888; font-weight: bold; font-family: Consolas, Monaco, monospace;">'
        f'{clean_lang}'
        f'</section>'
        f'</section>'
        f'<section style="padding: 14px 16px; font-family: Consolas, Monaco, \'Courier New\', monospace; font-size: 12.5px; color: #d4d4d4; line-height: 1.6; word-break: break-all; overflow-x: auto;">'
        f'{escaped_code}'
        f'</section>'
        f'</section>'
    )


def build_spec_card(title: str, specs: dict, primary_color: str) -> str:
    """
    【原子组件 8：参数/配置清单卡片 (Key-Value 网格)】
    适用于：展示模型超参数、训练配置、硬件资源要求等。
    `specs` 示例: {"Batch Size": "64", "Learning Rate": "3e-4", "Optimizer": "AdamW"}
    """
    clean_title = _to_str(title).strip().replace("\n", "")
    rows_html = ""

    for idx, (k, v) in enumerate(specs.items()):
        clean_k = str(k).strip().replace("\n", "")
        clean_v = str(v).strip().replace("\n", "")
        bg = "#ffffff" if idx % 2 == 0 else "#fcfcfc"

        rows_html += (
            f'<section style="display: table-row; background-color: {bg};">'
            f'<section style="display: table-cell; padding: 8px 12px; font-size: 12px; color: #666666; border-bottom: 1px solid #f0f0f0; width: 40%; font-weight: bold;">{clean_k}</section>'
            f'<section style="display: table-cell; padding: 8px 12px; font-size: 12px; color: #222222; border-bottom: 1px solid #f0f0f0; width: 60%; font-family: Consolas, monospace;">{clean_v}</section>'
            f'</section>'
        )

    return (
        f'<section style="border: 1px solid #e8e8e8; border-radius: 8px; margin: 20px 0; overflow: hidden; box-sizing: border-box;">'
        f'<section style="background-color: {primary_color}; color: #ffffff; padding: 8px 14px; font-size: 12px; font-weight: bold; letter-spacing: 0.5px;">'
        f'⚙️ {clean_title}'
        f'</section>'
        f'<section style="display: table; width: 100%; border-collapse: collapse; box-sizing: border-box;">'
        f'{rows_html}'
        f'</section>'
        f'</section>'
    )


def build_warning_card(title: str, content: str, alert_type: str = "warning") -> str:
    """
    【原子组件 9：避坑指南/预警卡片】
    适用于：强调算法局限性、复现踩坑点、硬件要求。
    `alert_type`: "warning" (警告黄), "danger" (危险红), "info" (提示蓝)
    """
    clean_title = _to_str(title).strip().replace("\n", "")
    clean_content = _to_str(content).strip().replace("\n", "")

    if alert_type == "danger":
        border_color = "#f5222d"
        bg_color = "#fff2f0"
        icon = "🚨"
    elif alert_type == "info":
        border_color = "#1890ff"
        bg_color = "#e6f7ff"
        icon = "ℹ️"
    else:  # warning
        border_color = "#fa8c16"
        bg_color = "#fffbe6"
        icon = "⚠️"

    return (
        f'<section style="background-color: {bg_color}; border-left: 4px solid {border_color}; border-radius: 0 8px 8px 0; padding: 14px 16px; margin: 20px 0; box-sizing: border-box;">'
        f'<section style="font-size: 13.5px; font-weight: bold; color: {border_color}; margin-bottom: 6px;">'
        f'<span style="margin-right: 6px;">{icon}</span>{clean_title}'
        f'</section>'
        f'<section style="font-size: 12.5px; color: #444444; line-height: 1.6; text-align: justify;">'
        f'{clean_content}'
        f'</section>'
        f'</section>'
    )


def build_qa_card(question: str, answer: str, primary_color: str) -> str:
    """
    【原子组件 10：Q&A / 常见问题解答卡片】
    适用于：以问答形式预判并解答读者核心疑问。
    """
    clean_q = _to_str(question).strip().replace("\n", "")
    clean_a = _to_str(answer).strip().replace("\n", "")

    return (
        f'<section style="background-color: #f9f9f9; border-radius: 8px; padding: 14px 16px; margin: 20px 0; border: 1px solid #eee; box-sizing: border-box;">'
        f'<section style="font-size: 14px; font-weight: bold; color: #222222; margin-bottom: 8px; line-height: 1.5; display: table; width: 100%;">'
        f'<section style="display: table-cell; width: 24px; vertical-align: top;">'
        f'<span style="background-color: {primary_color}; color: #ffffff; font-size: 11px; font-weight: 900; padding: 2px 5px; border-radius: 3px;">Q</span>'
        f'</section>'
        f'<section style="display: table-cell; vertical-align: top; padding-left: 6px;">'
        f'{clean_q}'
        f'</section>'
        f'</section>'
        f'<section style="font-size: 13px; color: #555555; line-height: 1.6; padding-top: 8px; border-top: 1px dashed #e0e0e0; display: table; width: 100%;">'
        f'<section style="display: table-cell; width: 24px; vertical-align: top;">'
        f'<span style="background-color: #e0e0e0; color: #444444; font-size: 11px; font-weight: 900; padding: 2px 5px; border-radius: 3px;">A</span>'
        f'</section>'
        f'<section style="display: table-cell; vertical-align: top; padding-left: 6px; text-align: justify;">'
        f'{clean_a}'
        f'</section>'
        f'</section>'
        f'</section>'
    )


def build_timeline_card(title: str, events: list, primary_color: str) -> str:
    """
    【原子组件 11：演进历程/时间线卡片】
    适用于：技术演进历史、模型版本迭代、阶段性训练流程。
    `events` 示例: [{"time": "2023.03", "title": "v1.0 发布", "desc": "首次引入..."}, ...]
    """
    clean_title = _to_str(title).strip().replace("\n", "")
    items_html = ""

    for idx, ev in enumerate(events):
        time_str = str(ev.get("time", "")).strip().replace("\n", "")
        ev_title = str(ev.get("title", "")).strip().replace("\n", "")
        ev_desc = str(ev.get("desc", "")).strip().replace("\n", "")

        is_last = idx == len(events) - 1
        border_left = "none" if is_last else f"2px solid {primary_color}"

        items_html += (
            f'<section style="position: relative; padding-left: 20px; padding-bottom: {0 if is_last else 16}px; border-left: {border_left}; margin-left: 6px;">'
            f'<section style="position: absolute; left: -6px; top: 2px; width: 10px; height: 10px; border-radius: 50%; background-color: {primary_color}; border: 2px solid #ffffff; box-shadow: 0 0 0 2px {primary_color};"></section>'
            f'<section style="font-size: 11px; font-weight: bold; color: {primary_color}; line-height: 1.2;">{time_str}</section>'
            f'<section style="font-size: 13px; font-weight: bold; color: #222222; margin-top: 2px;">{ev_title}</section>'
            f'<section style="font-size: 12px; color: #666666; margin-top: 2px; line-height: 1.5;">{ev_desc}</section>'
            f'</section>'
        )

    return (
        f'<section style="background-color: #fcfcfc; border-radius: 8px; border: 1px solid #f0f0f0; padding: 16px; margin: 20px 0; box-sizing: border-box;">'
        f'<section style="font-size: 12px; font-weight: bold; color: {primary_color}; margin-bottom: 14px; text-transform: uppercase; letter-spacing: 0.5px;">'
        f'⏳ {clean_title}'
        f'</section>'
        f'<section style="padding-left: 4px;">'
        f'{items_html}'
        f'</section>'
        f'</section>'
    )


def build_resource_card(title: str, desc: str, link_info: str, primary_color: str, bg_color: str) -> str:
    """
    【原子组件 12：资源获取/开源链接卡片】
    适用于：引导获取 GitHub 代码库、论文 PDF 或数据集。
    """
    clean_title = _to_str(title).strip().replace("\n", "")
    clean_desc = _to_str(desc).strip().replace("\n", "")
    clean_link = _to_str(link_info).strip().replace("\n", "")

    return (
        f'<section style="background-color: {bg_color}; border-radius: 8px; border: 1px solid {primary_color}; padding: 14px 16px; margin: 20px 0; box-sizing: border-box;">'
        f'<section style="display: table; width: 100%; box-sizing: border-box;">'
        f'<section style="display: table-cell; vertical-align: middle;">'
        f'<section style="font-size: 13.5px; font-weight: bold; color: #222222; line-height: 1.4;">📦 {clean_title}</section>'
        f'<section style="font-size: 11.5px; color: #666666; margin-top: 4px; line-height: 1.4;">{clean_desc}</section>'
        f'</section>'
        f'<section style="display: table-cell; vertical-align: middle; text-align: right; width: 100px;">'
        f'<section style="background-color: {primary_color}; color: #ffffff; font-size: 11px; font-weight: bold; padding: 6px 10px; border-radius: 4px; display: inline-block; text-align: center;">'
        f'{clean_link}'
        f'</section>'
        f'</section>'
        f'</section>'
        f'</section>'
    )


def build_checklist_card(title: str, items: list, primary_color: str, bg_color: str) -> str:
    """
    【原子组件 13：总结清单卡片 (Takeaway Checklist)】
    适用于：文章结尾，带 ✅ 标志的多要点核心结论总结。
    """
    clean_title = _to_str(title).strip().replace("\n", "")
    items_html = ""

    for item in items:
        clean_item = str(item).strip().replace("\n", "")
        items_html += (
            f'<section style="display: table; width: 100%; margin-bottom: 8px; box-sizing: border-box;">'
            f'<section style="display: table-cell; width: 20px; vertical-align: top; font-size: 13px;">✅</section>'
            f'<section style="display: table-cell; vertical-align: top; font-size: 13px; color: #333333; line-height: 1.6; text-align: justify;">{clean_item}</section>'
            f'</section>'
        )

    return (
        f'<section style="background-color: {bg_color}; border-left: 4px solid {primary_color}; border-radius: 0 8px 8px 0; padding: 14px 16px; margin: 20px 0; box-sizing: border-box;">'
        f'<section style="font-size: 13px; font-weight: bold; color: {primary_color}; margin-bottom: 10px; letter-spacing: 0.5px;">'
        f'📌 {clean_title}'
        f'</section>'
        f'{items_html}'
        f'</section>'
    )