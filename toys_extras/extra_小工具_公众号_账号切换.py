from toys_extras.base_web import BaseWeb
from playwright.sync_api import Page
from toys_logger import logger
import re


__version__ = '1.0.6'


class Toy(BaseWeb):

    def __init__(self, page: Page):
        super().__init__(page)
        self.url = "https://mp.weixin.qq.com/"
        self.result_table_view: list = [['账号', "状态", "失败原因"]]


    def play(self):
        停留时长 = self.config.get("扩展", "停留时长(秒)", fallback="0")

        停留时长 = int(停留时长) * 1000
        pages = self.page.context.pages
        for p in pages:
            if self.url in p.url:
                page = p
                self.page.close()
                break
        else:
            page = self.page
            page.goto(self.url)
        page.locator('[title="公众号"]').wait_for()
        login_button = page.locator("a", has_text=re.compile("^登录$"))
        if login_button.is_visible():
            login_button.click()
        
        # 切换至小程序
        page.locator(".account_box-body").click()
        page.locator(".account_box-panel-item", has_text="切换账号").click()

        # 当前登录账号
        current_login_locator = page.locator(".switch-account-dialog_section .section-item", has_text="当前登录")
        current_login_locator.wait_for()
        current_login_account = current_login_locator.locator(".section-item__desc").first.text_content()
        current_login_nickname = current_login_locator.locator(".section-item__nickname").first.text_content()

        # 如果有小程序账号，切换至小程序账号
        miniprogram_account = page.locator(".switch-account-dialog_section", has_text="小程序").locator(".section-item__nickname").first
        if miniprogram_account.is_visible():
            miniprogram_account.click()
        else:
            logger.warning("无小程序账号")
            self.is_failed = True
            self.result_table_view.append([current_login_nickname, "失败", ""])
        
        page.wait_for_timeout(停留时长)
        
        # 切换回当前登录账号
        try:
            page.locator(".header_user_logo").or_(page.locator(".account_info")).wait_for()
            if page.locator(".header_user_logo").count():
                page.locator(".header_user_logo").click()
                page.locator(".header_user_logo").get_by_text("切换账号").click()
            else:
                page.locator(".account_info").click()
                page.locator('[title="切换账号"]').click()
            page.get_by_text(current_login_account).click()
            page.locator('[title="公众号"]').wait_for()
            page.wait_for_timeout(3_000)
            self.result_table_view.append([current_login_nickname, "成功", ""])
        except Exception as e:
            self.is_failed = True
            self.result_table_view.append([current_login_nickname, "失败", "切换回当前登录账号失败"])
            logger.error("切换回当前登录账号失败", exc_info=True)
