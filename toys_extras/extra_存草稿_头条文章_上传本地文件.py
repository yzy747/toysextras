from toys_extras.articles import Articles
from playwright.sync_api import Page
from toys_logger import logger
from toys_utils import MarkdownToHtmlConverter, insert_image_link_to_markdown
import os
import random


__version__ = "1.0.1"


class Toy(Articles, MarkdownToHtmlConverter):

    def __init__(self, page: Page):
        Articles.__init__(self, page)
        MarkdownToHtmlConverter.__init__(self)
        self.url = "https://mp.toutiao.com/profile_v4/graphic/publish?from=toutiao_pc"
        self.image_url_prefix = "image-tt-private.toutiao.com/"
        self.result_table_view: list = [['文件名', '状态', "错误信息", '文档路径']]
        self.文章标题输入框 = self.page.locator('.editor-title textarea')
        self.button_导入文档 = self.page.locator(".doc-import")
        self.button_选择文档 = self.page.locator('input[type="file"]')
        self.上传文档成功提示 = self.page.get_by_text("导入成功", exact=True)
        self.保存草稿成功提示 = self.page.get_by_text("草稿已保存", exact=True)

    def play(self):
        合集 = self.config.get("扩展", "合集")
        添加位置 = self.config.get("扩展", "添加位置")
        同时发布微头条 = self.config.get("扩展", "同时发布微头条")
        作品声明 = self.config.get("扩展", "作品声明")
        完成后移动文件到指定文件夹 = self.config.get("扩展", "完成后移动文件到指定文件夹")

        for file in self.files:
            file_name = os.path.basename(file)
            self.result_table_view.append([file_name, "待处理", "", file])

        for line in self.result_table_view[1:]:
            if self.stop_event.is_set():
                break
            self.pause_event.wait()
            line[1] = "处理中"
            file = line[3]
            dir_name = os.path.dirname(file)
            file_name_without_ext, file_ext = os.path.splitext(os.path.basename(file))
            if file_ext != ".docx":
                line[1] = "失败"
                line[2] = f"仅支持docx文件"
                continue
            try:
                self.navigate()
                self.upload_document(file)
                self.random_wait()
                input_title = self.文章标题输入框.inner_text()
                if input_title.strip() == "":
                    self.文章标题输入框.fill(file_name_without_ext)
                if 添加位置:
                    self.page.locator(".byte-select-view", has_text="标记城市，让更多同城用户看到").click()
                    self.page.locator(".byte-select-view", has_text="标记城市，让更多同城用户看到").locator("input").fill(添加位置)
                    self.random_wait(300, 600)
                    self.page.locator(".byte-select-option", has_text=添加位置).click()
                if 合集:
                    self.page.get_by_role("button", name="添加至合集").click()
                    self.page.locator(".add-collection-item", has=self.page.get_by_text(合集, exact=True)).click()
                    self.random_wait(300, 600)
                    self.page.locator("button", has_text="确定").click()
                if 同时发布微头条 and 同时发布微头条  != "是":
                    self.page.locator(".form-item", has_text="同时发布微头条").click()
                    self.random_wait(300, 600)
                if 作品声明 and 作品声明 != "个人观点，仅供参考":
                    self.page.locator(".source-wrap .byte-checkbox", has_text=作品声明).click()
                try:
                    self.保存草稿成功提示.wait_for(timeout=5000)
                except Exception:
                    line[1] = "可能失败,请手动检查"
                    line[2] = "未识别到保存草稿成功提示"
                    continue
                if 完成后移动文件到指定文件夹:
                    self.move_to_done(完成后移动文件到指定文件夹, dir_name, file)
                line[1] = "存稿成功"
            except Exception as e:
                logger.exception(f"处理文件 {file} 失败: {e}")
                line[1] = "失败"
                line[2] = str(e)
            finally:
                self.random_wait()
        self.page.close()
