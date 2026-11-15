from playwright.sync_api import sync_playwright

def update_wechat_state():
    print("[INFO] 启动有头浏览器，请在弹出的浏览器中手动扫码/完成验证...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        page.goto("https://mp.weixin.qq.com/")
        print("[ACTION] 请在浏览器中完成扫码登录...")
        
        # 等待成功进入首页（等待页面加载出控制台特有的 DOM 元素）
        page.wait_for_selector(".weui-desktop-layout__main", timeout=120000) # 留出2分钟时间扫码
        
        # 登录成功后，更新保存最新的 state
        context.storage_state(path="wechat_state.json")
        print("[SUCCESS] Cookie 状态更新成功！已保存至 wechat_state.json")
        browser.close()

if __name__ == "__main__":
    update_wechat_state()