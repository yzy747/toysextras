from toys_extras.base_web import BaseWeb
from playwright.sync_api import Page
from toys_logger import logger
from datetime import datetime, timedelta
import os

__version__ = "1.0.7"

class Toy(BaseWeb):

    def __init__(self, page: Page):
        super().__init__(page)
        self.result_table_view: list = [['文章名称', '状态', '错误信息', '文章链接']]
        self.url = "https://baijiahao.baidu.com/builder/rc/edit?type=news&is_from_cms=1"
        self.文章标题输入框 = self.page.locator(".input-box div[contenteditable=true]")
        self.文章第1行 = self.page.frame_locator("iframe[id='ueditor_0']").locator(".view.news-editor-pc p").first
        self.文章第2行 = self.page.frame_locator("iframe[id='ueditor_0']").locator(".view.news-editor-pc p").nth(1)
        self.hove_导入文档 = self.page.locator(".edui-for-bjhInsertionDrawer")
        self.button_导入文档 = self.page.get_by_text("导入文档")
        self.button_选择文档 = self.page.locator('.cheetah-upload button')
        self.button_保存 = self.page.locator(".op-btn-outter-content", has_text="存草稿").locator("button")
        self.上传文档成功提示 = self.page.get_by_text("导入成功")
        self.保存草稿成功提示 = self.page.get_by_text("内容已存入草稿")
        
        self.下方输入组件 = self.page.locator(".cheetah-form-item-control-input")
        self.封面设置 = self.下方输入组件.filter(has_text="封面")
        self.摘要输入框 = self.page.get_by_placeholder("请输入摘要")
        self.分类选择 = self.下方输入组件.filter(has_text="分类")
        self.事件来源时间 = self.page.get_by_placeholder("请选择时间")
        self.事件来源地点 = self.page.locator(".cheetah-select-selector", has_text="请选择地点").locator("input")

        self.设置选项 = self.page.locator(".cheetah-form-item", has_text="设置")
    
    def delete_first_paragraph(self):
        first_line_length = len(self.文章第1行.text_content() or "")
        self.文章第2行.click(position={"x": 0, "y": 0})
        self.random_wait(500, 1000)
        for i in range(first_line_length + 10):
            self.page.keyboard.press("Backspace")
    
    def play(self):
        文章包含标题 = self.config.get("扩展", "文章包含标题")
        封面图序号 = self.config.get("扩展", "封面图序号 -- 多图用英文逗号隔开，如1,3,4")
        摘要 = self.config.get("扩展", "摘要")
        分类 = self.config.get("扩展", "分类 -- 可填格式“历史->考古”", fallback="")
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

        for row in self.result_table_view[1:]:
            article_url = ""
            file = row[0]
            try:
                dir_name, filename = os.path.split(file)
                self.page.goto(self.url)
        
                # 上传文档
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
                
                文章标题 = self.文章第1行.inner_text().strip().replace("\n", " ")[:64]
                if len(文章标题) < 2:
                    logger.warning(f"文档{file}内容太短，无法提取有效标题")
                    row[1] = "失败"
                    row[2] = "文档内容太短，无法提取有效标题"
                    self.is_failed = True
                    continue

                # 如果文章包含标题为"是"，则填写标题
                if 文章包含标题 == "是":

                    self.文章标题输入框.fill(文章标题)
                    self.delete_first_paragraph()
                self.random_wait(500, 1000)
                
                # 设置封面
                封面图序号列表 = [int(序号.strip()) - 1 for 序号 in 封面图序号.split(",") if 序号.strip().isdigit()]
                if 封面图序号列表:  
                    if len(封面图序号列表) > 1:
                        self.封面设置.locator(".cheetah-radio-wrapper", has_text="三图").locator("input").click()
                    else:
                        self.封面设置.locator(".cheetah-radio-wrapper", has_text="单图").locator("input").click()
                        self.random_wait(1000, 1500)
                    self.page.locator('.cheetah-form-item-control-input .coverUploaderView', has_text="选择封面").locator("visible=true").first.click()

                    image_locator = self.page.locator("div.cheetah-modal-content .image")
                    image_locator.first.wait_for(state="visible", timeout=30_000)
                    
                    # 根据配置的序号选择封面图
                    for 序号 in 封面图序号列表:
                        available_images = image_locator.all()
                        if 序号 < len(available_images):
                            available_images[序号].click()
                            self.random_wait(1500, 3000)                
                    self.page.get_by_role("button", name="确认").click()
                    self.random_wait(500, 1000)         

                if 摘要:
                    self.摘要输入框.fill(摘要)
                    self.random_wait(500, 1000)
                
                # 选择分类
                if 分类:
                    self.分类选择.locator(".cheetah-select-selector").click()
                    self.random_wait(500, 1000)
                    for 分类部分 in 分类.split("->"):
                        self.page.get_by_text(分类部分).evaluate("(el) => el.click()")
                        self.random_wait(500, 1000)
                
                if 事件来源时间:
                    if 事件来源时间 == "今日":
                        事件来源时间 = datetime.now().strftime("%Y-%m-%d")
                    elif 事件来源时间 == "昨日":
                        事件来源时间 = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
                    self.事件来源时间.fill(事件来源时间)
                    self.random_wait(500, 1000)
                
                if 事件来源地点:
                    self.事件来源地点.click()
                    for 地点部分 in 事件来源地点.split("->"):
                        self.random_wait(500, 1000)
                        self.page.get_by_text(地点部分).evaluate("(el) => el.click()")
                self.random_wait(500, 1000)
                设置选项列表 = [选项.strip() for 选项 in 设置选项.split(",") if 选项.strip()]
                for option_loc in self.设置选项.locator(".setting-item .cheetah-checkbox-wrapper").all():
                    option_text = option_loc.inner_text().strip()
                    is_matched = False
                    
                    for 选项 in 设置选项列表:
                        if 选项 in option_text:
                            is_matched = True
                            if option_loc.locator(".cheetah-checkbox-checked").count() == 0:
                                option_loc.get_by_text(选项).click()
                                self.random_wait(500, 1000)
                            break
                    
                    if not is_matched and option_loc.locator(".cheetah-checkbox-checked").count() > 0:
                        option_loc.locator("input").click()
                        self.random_wait(500, 1000)
                
                # 保存草稿
                self.button_保存.click()
                self.保存草稿成功提示.wait_for(state="visible", timeout=30000)
                self.random_wait(1000, 2000)
                
                # 获取文章链接
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
