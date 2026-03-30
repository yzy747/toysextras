from toys_extras.base_web import BaseWeb
from playwright.sync_api import Page, Locator
from toys_logger import logger
from datetime import datetime, timedelta
import os
import re

__version__ = "1.0.10"


class Toy(BaseWeb):

    def __init__(self, page: Page):
        super().__init__(page)
        self.result_table_view: list = [['文章名称', '状态', '错误信息', '文章链接']]
        self.url = "https://baijiahao.baidu.com/builder/rc/edit?type=news&is_from_cms=1"
        self.文章标题输入框 = self.page.locator(".input-box div[contenteditable=true]")
        self.文章第1行 = self.page.frame_locator("iframe[id='ueditor_0']").locator(".view.news-editor-pc > *").filter(has_text=re.compile(r'\S')).first
        self.文章第2行 = self.page.frame_locator("iframe[id='ueditor_0']").locator(".view.news-editor-pc > *").filter(has_text=re.compile(r'\S')).nth(1)
        self.hove_导入文档 = self.page.locator(".edui-for-bjhInsertionDrawer")
        self.button_导入文档 = self.page.get_by_text("导入文档")
        self.button_选择文档 = self.page.locator('.cheetah-upload button')
        self.button_保存 = self.page.locator(".op-btn-outter-content", has_text="存草稿").locator("button")
        self.上传文档成功提示 = self.page.get_by_text("导入成功")
        self.保存草稿成功提示 = self.page.get_by_text("内容已存入草稿")

        self.下方输入组件 = self.page.locator(".cheetah-form-item")
        self.封面设置 = self.下方输入组件.filter(has_text="封面")
        # self.摘要输入框 = self.page.get_by_placeholder("请输入摘要")
        # self.分类选择 = self.下方输入组件.filter(has_text="分类")
        # self.事件来源时间 = self.page.get_by_placeholder("请选择时间")
        # self.事件来源地点 = self.page.locator(".cheetah-select-selector", has_text="请选择地点").locator("input")
        self.智能创作 = self.下方输入组件.filter(has_text="智能创作").last
        self.创作声明 = self.下方输入组件.filter(has_text="创作声明").last
        self.设置选项 = self.下方输入组件.filter(has_text="拓展设置")

    def delete_first_paragraph(self):
        first_line_length = len(self.文章第1行.text_content() or "")
        self.文章第2行.click(position={"x": 0, "y": 0})
        self.random_wait(500, 1000)
        for _ in range(first_line_length + 10):
            self.page.keyboard.press("Backspace")

    def _set_checkboxes(self, container: Locator, target_options: list[str], match_mode: str = "exact"):
        """
        设置复选框状态
        :param container: 包含复选框的容器定位器
        :param target_options: 目标选项列表
        :param match_mode: 匹配模式，"exact" 表示精确匹配，"contains" 表示包含匹配
        """
        for checkbox in container.locator(".cheetah-checkbox-wrapper").all():
            checkbox_text = checkbox.inner_text().strip()
            is_target = False

            if match_mode == "exact":
                is_target = checkbox_text in target_options
            elif match_mode == "contains":
                is_target = any(opt in checkbox_text for opt in target_options)

            is_checked = checkbox.locator(".cheetah-checkbox-checked").count() > 0

            if is_target and not is_checked:
                checkbox.click()
                self.random_wait(500, 1000)
            elif not is_target and is_checked:
                checkbox.locator("input").click()
                self.random_wait(500, 1000)

    def _upload_document(self, file: str):
        self.hove_导入文档.click()
        self.random_wait(500, 1000)
        self.button_导入文档.evaluate("(el) => el.click()")
        self.random_wait(500, 1000)

        with self.page.expect_file_chooser() as fc_info:
            self.button_选择文档.click()
        file_chooser = fc_info.value
        file_chooser.set_files(file)

        self.上传文档成功提示.wait_for(state="visible", timeout=60000)
        self.random_wait(1000, 2000)

    def _set_cover(self, cover_indices: list[int]):
        if not cover_indices:
            return True

        if len(cover_indices) > 1:
            self.封面设置.locator(".cheetah-radio-wrapper", has_text="三图").locator("input").click()
        else:
            self.封面设置.locator(".cheetah-radio-wrapper", has_text="单图").locator("input").click()
            self.random_wait(1000, 1500)

        try:
            cover_locator = self.page.locator('.cheetah-form-item-control-input [class*=cheetah-spin-container]')
            if cover_locator.get_by_text("更换").count() > 0:
                for _ in self.page.locator("[class*='removeIcon'] [class*='BjhBasicGuanbiteshu']").all():
                    self.page.locator("[class*='removeIcon'] [class*='BjhBasicGuanbiteshu']").first.evaluate("(el) => el.click()")
                    self.random_wait(500, 1000)
            cover_locator.get_by_text("选择封面").locator("visible=true").first.click()

            image_locator = self.page.locator("div.cheetah-modal-content [class*=imgItem]")
            image_locator.first.wait_for(state="visible", timeout=30_000)
            self.random_wait(2000, 3000)

            for idx in cover_indices:
                available_images = image_locator.all()
                if idx < len(available_images):
                    if idx == 0:
                        continue
                    available_images[idx].click()
                    self.random_wait(1500, 3000)

            self.page.locator("button", has_text="确定").locator("visible=true").first.click()
            self.random_wait(500, 1000)
            return True
        except Exception as e:
            logger.warning(f"选择封面图时出错: {e}")
            return False

    def _set_creation_declaration(self, declaration_options: list[str], event_time: str, event_location: str):
        for option_loc in self.创作声明.locator(".cheetah-checkbox-wrapper").all():
            option_text = option_loc.inner_text().strip()
            matched_option = None

            for opt in declaration_options:
                if opt in option_text:
                    matched_option = opt
                    break

            is_checked = option_loc.locator(".cheetah-checkbox-checked").count() > 0

            if matched_option:
                if not is_checked:
                    option_loc.get_by_text(matched_option).click()
                    self.random_wait(500, 1000)

                if matched_option == "来源说明":
                    self._fill_event_info(event_time, event_location)
            elif is_checked:
                option_loc.locator("input").click()
                self.random_wait(500, 1000)

    def _fill_event_info(self, event_time: str, event_location: str):
        if event_time:
            time_value = event_time
            if event_time == "今日":
                time_value = datetime.now().strftime("%Y-%m-%d")
            elif event_time == "昨日":
                time_value = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            self.page.get_by_placeholder("请选择时间").fill(time_value)
            self.random_wait(500, 1000)

        if event_location:
            self.创作声明.locator(".cheetah-cascader").last.click()
            for location_part in event_location.split("->"):
                self.random_wait(500, 1000)
                self.page.get_by_text(location_part).evaluate("(el) => el.click()")

    def _set_extended_options(self, options: list[str]):
        for option_loc in self.设置选项.locator(".setting-item .cheetah-checkbox-wrapper").all():
            option_text = option_loc.inner_text().strip()
            matched_option = None

            for opt in options:
                if opt in option_text:
                    matched_option = opt
                    break

            is_checked = option_loc.locator(".cheetah-checkbox-checked").count() > 0

            if matched_option and not is_checked:
                option_loc.get_by_text(matched_option).click()
                self.random_wait(500, 1000)
            elif not matched_option and is_checked:
                option_loc.locator("input").click()
                self.random_wait(500, 1000)

    def play(self):
        文章包含标题 = self.config.get("扩展", "文章包含标题")
        封面图序号 = self.config.get("扩展", "封面图序号 -- 多图用英文逗号隔开，如1,3,4")
        智能创作 = self.config.get("扩展", "智能创作", fallback="")
        创作声明 = self.config.get("扩展", "创作声明", fallback="")
        # 摘要 = self.config.get("扩展", "摘要")
        # 分类 = self.config.get("扩展", "分类 -- 可填格式“历史->考古”", fallback="")
        事件来源时间 = self.config.get("扩展", "事件来源说明 -- 时间，可填格式“2023-01-01”或“今日”或“昨日”", fallback="")
        事件来源地点 = self.config.get("扩展", "事件来源说明 -- 地点，可填格式“河北省->北京市”", fallback="")
        设置选项 = self.config.get("扩展", "设置 -- 多个设置使用英文逗号隔开，如：自动生成播客,图文转动态")
        完成后移动至 = self.config.get("扩展", "完成后移动至")

        for file in self.files:
            if not file.endswith(".docx"):
                logger.warning(f"仅支持上传格式docx的word文档：{file}")
                continue
            self.result_table_view.append([file, "", "", ""])

        def handler():
            self.page.locator(".cheetah-popconfirm-message .l-icon-BjhBasicGuanbi svg").click()

        self.page.add_locator_handler(
            self.page.get_by_text("如您发布的内容涉及公共政策和时事，请注明引用来源、事件时间及地点。"),
            handler
        )

        智能创作列表 = [opt.strip() for opt in 智能创作.split(",") if opt.strip()]
        创作声明列表 = [opt.strip() for opt in 创作声明.split(",") if opt.strip()]
        设置选项列表 = [opt.strip() for opt in 设置选项.split(",") if opt.strip()]
        封面图序号列表 = [int(idx.strip()) - 1 for idx in 封面图序号.split(",") if idx.strip().isdigit()]

        for row in self.result_table_view[1:]:
            file = row[0]
            try:
                dir_name, _ = os.path.split(file)
                self.page.goto(self.url)

                article_editor = self.page.frame_locator("iframe[id='ueditor_0']").locator(".view.news-editor-pc")
                if article_editor.inner_text().strip():
                    article_editor.clear()

                self._upload_document(file)

                文章标题 = self.文章第1行.inner_text().strip().replace("\n", " ")[:64]
                if len(文章标题) < 2:
                    logger.warning(f"文档{file}内容太短，无法提取有效标题")
                    row[1] = "失败"
                    row[2] = "文档内容太短，无法提取有效标题"
                    self.is_failed = True
                    continue

                if 文章包含标题 == "是":
                    self.文章标题输入框.fill(文章标题)
                    self.delete_first_paragraph()
                self.random_wait(500, 1000)

                if not self._set_cover(封面图序号列表):
                    self.is_failed = True
                    row[2] = "选择封面图可能错误"

                self._set_checkboxes(self.智能创作, 智能创作列表)
                self._set_creation_declaration(创作声明列表, 事件来源时间, 事件来源地点)
                self._set_extended_options(设置选项列表)

                self.button_保存.click()
                self.保存草稿成功提示.wait_for(state="visible", timeout=30000)
                self.random_wait(1000, 2000)

                article_url = self.page.url
                row[1] = "成功"
                row[3] = article_url

                logger.info(f"文章《{文章标题}》保存草稿成功，链接：{article_url}")

                if 完成后移动至 != "":
                    self.move_to_done(完成后移动至, dir_name, file)

            except Exception as e:
                logger.error(f"处理文件 {file} 时发生错误", exc_info=True)
                row[1] = "失败"
                row[2] = str(e)
                self.is_failed = True

        if not self.page.is_closed():
            self.page.close()
