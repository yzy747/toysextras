from toys_logger import logger
from toys_extras.articles import Articles
from playwright.sync_api import Page
from toys_utils import ToyError

__version__ = "1.0.2"

# 切换文件夹方法优化

class Toy(Articles):

    def __init__(self, page: Page):
        super().__init__(page)
        self.url = "https://editor.mdnice.com/"
        self.result_table_view: list = [['文章标题', '状态']]

    def choose_catalog(self, catalog_name: str, depth: int = 1) -> None:
        print(depth)
        if depth == 5:
            raise ToyError("选择墨滴文件夹失败，请确认文件夹名称是否正确")
        try:
            catalog_btn = self.page.locator(".catalog-btn")
            item_list = self.page.locator(".ant-list")
            catalog_list = self.page.locator(".catalog-sidebar-list-item-container")
            item_list.wait_for(state="attached")
            try:
                item_list.locator(".ant-list-items").wait_for(timeout=3000)
            except Exception:
                pass
            if catalog_list.count():
                self.page.locator(".catalog-name", has_text=catalog_name).evaluate("element => element.click()")
                self.random_wait(1000, 1500)
            elif catalog_btn.text_content() != catalog_name:
                catalog_btn.click(timeout=3000)
                self.random_wait(1000, 1500)
                self.page.locator(".catalog-name", has_text=catalog_name).evaluate("element => element.click()")
                self.random_wait(1000, 1500)
        except Exception as e:
            logger.exception(f"Error: {e}")
            self.choose_catalog(catalog_name, depth+1)

    def play(self):
        catalog_name = self.config.get("扩展", "墨滴文件夹")
        self.navigate()
        # 切换文章文件夹
        self.choose_catalog(catalog_name)
        first_article = self.page.locator(".ant-list-items .ant-list-item").first
        first_article.wait_for()
        while first_article.is_visible():
            # 等待停止事件
            if self.stop_event.is_set():
                break
            self.pause_event.wait()
            title = first_article.locator(".nice-article-sidebar-list-item-top-container").text_content()
            try:
                first_article.locator(".anticon-setting").click()
                self.page.wait_for_timeout(1000)
                self.page.locator("li", has_text="删除文章").click()
                self.page.wait_for_timeout(1000)
                self.page.get_by_role("button", name="确 认").click()
                self.result_table_view.append([title, "删除成功"])
                self.page.wait_for_timeout(500)
            except Exception as e:
                logger.exception(f"Error: {e}")
                self.result_table_view.append([title, "删除失败"])
            finally:
                try:
                    first_article.wait_for(timeout=5000)
                except Exception:
                    break
        self.page.close()