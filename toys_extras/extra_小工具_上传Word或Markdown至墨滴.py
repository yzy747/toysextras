import os
from toys_utils import ToyError
from toys_logger import logger
from toys_extras.articles import Articles
from playwright.sync_api import Page

__version__ = "1.0.4"
# 更新日志
# 1.0.1 修复选择墨滴文件夹失败的问题
# 1.0.2 同步墨滴网站改版，修复上传失败的问题
# 1.0.3 切换文件夹方法优化


class Toy(Articles):

    def __init__(self, page: Page):
        super().__init__(page)
        self.url = "https://editor.mdnice.com/"
        self.result_table_view: list = [['文件名', '状态', "错误信息", '文档路径']]

    def chose_theme(self, theme: str) -> None:
        self.page.locator("#nice-menu-theme").click()
        self.page.locator("[data-node-key=collection] div").click()
        self.page.locator(".banner-card", has_text=theme).get_by_text("使 用").click()

    def choose_catalog(self, catalog_name: str, depth: int = 1) -> None:
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
        theme = self.config.get("扩展", "墨滴主题")
        catalog_name = self.config.get("扩展", "墨滴文件夹")
        no_space = False
        for file in self.files:
            if not file.endswith(".md") and not file.endswith(".docx"):
                continue
            self.result_table_view.append([os.path.basename(file).rsplit(".", maxsplit=1)[0], "待处理", "", file])
        for line in self.result_table_view[1:]:
            if no_space:
                self.result_table_view[self.result_table_view.index(line)][1] = "失败"
                self.result_table_view[self.result_table_view.index(line)][2] = "墨滴空间不足"
                continue
            self.navigate()
            # 等待停止事件
            if self.stop_event.is_set():
                break
            self.pause_event.wait()
            try:
                file = line[3]
                title = line[0]
                self.choose_catalog(catalog_name)
                self.page.locator("button.add-btn").click()
                self.page.get_by_placeholder("请输入标题").fill(title)
                self.page.get_by_role("button", name="新 增").click()
                self.chose_theme(theme)
                self.page.locator("#nice-menu-file").click()
                with self.page.expect_file_chooser() as fc_info:
                    if file.endswith(".docx"):
                        self.page.locator("#nice-menu-import-word").click()
                    else:
                        self.page.locator("#nice-menu-import-markdown").click()
                fc_info.value.set_files(file)
                self.page.get_by_text("导入文件成功").wait_for()
                try:
                    self.page.locator("#nice-md-editor").click(button="right")
                    self.page.locator('.nice-editor-menu').get_by_text('格式化文档').click()
                    self.page.get_by_text("自动保存成功", exact=True).wait_for(timeout=5000)
                except Exception as e:
                    self.result_table_view[self.result_table_view.index(line)][1] = "可能失败"
                    self.result_table_view[self.result_table_view.index(line)][2] = "未等待自动保存成功提示"
                    logger.exception(f"上传Word或Markdown至墨滴失败: {e}")
                    continue
                self.result_table_view[self.result_table_view.index(line)][1] = "已处理"
            except Exception as e:
                self.page.wait_for_timeout(2000)
                if self.page.get_by_role("button", name="升级会员").is_visible():
                    no_space = True
                    e = "墨滴空间不足"
                else:
                    logger.exception(f"Error: {e}")
                self.result_table_view[self.result_table_view.index(line)][1] = "失败"
                self.result_table_view[self.result_table_view.index(line)][2] = str(e)
        self.page.close()