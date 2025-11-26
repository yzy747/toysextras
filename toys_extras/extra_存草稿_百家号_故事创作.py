from toys_extras.base_web import BaseWeb
from playwright.sync_api import Page, expect as pwexpect
from toys_logger import logger
import os

__version__ = "1.0.1"


class Toy(BaseWeb):

    def __init__(self, page: Page):
        super().__init__(page)
        self.result_table_view: list = [['文章名称', '状态', '错误信息', "分发封面图片数", "文章链接"]]
        self.url = "https://story.baidu.com/builder/rc/story/creating?type=publish"
        self.右侧输入组件 = self.page.locator(".cheetah-form-item-control-input")
        self.故事标题输入框 = self.右侧输入组件.filter(has_text="故事标题").locator('textarea')
        self.故事名称输入框 = self.右侧输入组件.filter(has_text="故事名称").locator('textarea')
        self.故事标签 = self.右侧输入组件.filter(has_text="故事标签").locator("#tags > div:nth-child(3) > div")
        self.题材类型 = self.故事标签.nth(0)
        self.时空类型 = self.故事标签.nth(1)
        self.情节类型 = self.故事标签.nth(2)
        self.情绪类型 = self.故事标签.nth(3)
        self.故事类型 = self.右侧输入组件.filter(has_text="故事类型")
        self.分发封面 = self.右侧输入组件.filter(has_text="分发封面")
        self.故事封面 = self.右侧输入组件.filter(has_text="故事封面").locator(".cheetah-spin-container div").first
        self.付费故事 = self.故事类型.locator(".cheetah-radio-wrapper", has_text="付费故事").locator("input")
        self.付费订阅 = self.右侧输入组件.filter(has_text="售卖方式").get_by_text("付费订阅")
        self.生成授权 = self.右侧输入组件.filter(has_text="生成授权").locator("input")
        self.达人分销比例 = self.page.locator("#commissionRate")
        self.内容输入框 = self.page.locator('div[contenteditable][aria-placeholder="请输入故事内容，至少1000字"]')
        self.文章第1行 = self.内容输入框.locator("p.bjh-paragraph").first
        self.文章第2行 = self.内容输入框.locator("p.bjh-paragraph").nth(1)
        self.button_导入文档 = self.page.locator("div.cheetah-upload-select")
        self.button_保存 = self.page.get_by_role("button", name="保存")
        self.上传文档成功提示 = self.page.get_by_text("文件上传成功")
        self.保存草稿成功提示 = self.page.get_by_text("保存成功")
    
    def delete_first_paragraph(self):
        first_line_length = len(self.文章第1行.text_content() or "")
        self.文章第2行.click(position={"x": 0, "y": 0})
        self.random_wait(500, 1000)
        for i in range(first_line_length + 10):
            self.page.keyboard.press("Backspace")

    def play(self):
        题材类型 = self.config.get("扩展", "题材类型")
        时空类型 = self.config.get("扩展", "时空类型")
        情节类型 = self.config.get("扩展", "情节类型 -- 多类型以英文逗号隔开，如出轨,家庭")
        情绪类型 = self.config.get("扩展", "情绪类型 -- 多类型以英文逗号隔开，如甜宠,爽文")
        付费故事 = True if self.config.get("扩展", "故事类型") == "付费故事" else False
        试读比例 = True if self.config.get("扩展", "设置试读比例 -- 填是或否") == "是" else False
        付费订阅 = True if self.config.get("扩展", "售卖方式") == "付费订阅" else False
        生成授权 = True if self.config.get("扩展", "生成授权") == "是" else False
        达人分销比例 = self.config.get("扩展", "达人分销比例 -- 填数字即可，如75")
        完成后移动至 = self.config.get("扩展", "完成后移动至")
        
        # 处理多选类型    
        情节类型 = [x.strip() for x in 情节类型.split(",") if x.strip()]
        情绪类型 = [x.strip() for x in 情绪类型.split(",") if x.strip()]
        

        for file in self.files:
            if not file.endswith(".docx"):
                logger.warning(f"仅支持上传格式docx的word文档：{file}")
                continue
            self.result_table_view.append([file, "", "", "", ""])
        for row in self.result_table_view[1:]:
            article_url = ""
            file = row[0]
            try:
                dir_name, filename = os.path.split(file)
                self.page.goto(self.url)
                self.内容输入框.click()
                with self.page.expect_file_chooser() as fc_info:
                    self.button_导入文档.click()
                file_chooser = fc_info.value
                file_chooser.set_files(file)
                self.上传文档成功提示.wait_for(state="visible", timeout=60000)
                self.random_wait(500, 1500)
                for i in range(30):
                    if self.page.url != self.url:
                        article_url = self.page.url
                        break
                    self.random_wait(1000, 2000)
                else:
                    logger.warning(f"文档{file}上传后页面未跳转，可能上传失败，跳过")
                    row[1] = "失败"
                    row[2] = "文档上传后页面未跳转，可能上传失败"
                    self.is_failed = True
                    continue
                # 取第一行文字作为标题
                故事标题 = self.文章第1行.inner_text().strip().replace("\n", " ")[:64]
                self.故事标题输入框.fill(故事标题)
                self.delete_first_paragraph()
                self.random_wait(500, 1500)
                # 再取第一行文字作为名称
                故事名称 = self.文章第1行.inner_text().strip().replace("\n", " ")[:15]
                self.故事名称输入框.fill(故事名称)
                self.delete_first_paragraph()
                self.random_wait(500, 1500)
                # 选择题材类型
                self.题材类型.get_by_text(题材类型).click()
                self.random_wait(500, 1500)
                # 选择时空类型
                self.时空类型.get_by_text(时空类型).click()
                self.random_wait(500, 1500)
                # 选择情节类型
                for 情节 in 情节类型:
                    self.情节类型.get_by_text(情节).click()
                    self.random_wait(500, 1000)
                # 选择情绪类型
                for 情绪 in 情绪类型:
                    self.情绪类型.get_by_text(情绪).click()
                    self.random_wait(500, 1000)
                # 分发封面
                self.分发封面.locator(".cheetah-radio-wrapper", has_text="多图").locator("input").click()
                self.page.locator('.cheetah-form-item-control-input .cheetah-spin-container').first.click()
                try:
                    self.page.locator("div.cheetah-modal-content img").first.wait_for(state="visible", timeout=30_000)
                    image_locator = self.page.locator(
                        "div.cheetah-modal-content div", has=self.page.locator(".cheetah-upload-wrapper")
                        ).last.locator(
                            "> div .cheetah-public"
                        )
                    image_locator.first.wait_for(state="visible", timeout=10_000)
                    self.random_wait(2000, 3000)
                    upload_count = 0
                    for up_index, _ in enumerate(image_locator.all()[:3]):
                        _.locator("div").click()
                        self.random_wait(2000, 3000)
                        upload_count += 1
                    self.page.get_by_role("button", name="确定").click()
                    row[3] = str(upload_count)
                    self.random_wait(500, 1000)
                except Exception:
                    logger.warning(f"选择分发封面图失败", exc_info=True)          
                # 故事封面
                self.故事封面.click()
                try:
                    self.page.locator("div.cheetah-modal-content img").first.wait_for(state="visible", timeout=30_000)
                    self.random_wait(2000, 3000)
                    for retry in range(5):
                        try:
                            self.page.get_by_role("button", name="确定").click(timeout=3_000)
                            self.random_wait(500, 1000)
                            pwexpect(self.page.get_by_role("button", name="确定")).not_to_be_visible(timeout=3_000)
                            break
                        except Exception as e:
                            logger.exception(f"选择故事封面图-重试{retry}次失败，{e}", exc_info=True)
                        self.random_wait(2000, 3000)
                    else:
                        logger.warning(f"选择故事封面图失败，重试5次后仍未出现图片")
                        row[1] = "失败"
                        row[2] = "选择故事封面图失败，重试5次后仍未出现图片"
                        self.is_failed = True
                        continue
                    
                except Exception:
                    logger.warning(f"选择故事封面图失败", exc_info=True)      
                if 付费故事:
                    self.付费故事.click()
                    self.random_wait(500, 1500)
                if 试读比例:
                    self.page.locator("#freePercentage > div").nth(1).click()
                    self.random_wait(500, 1500)
                if 付费订阅:
                    self.付费订阅.click()
                    self.random_wait(500, 1500)
                if 生成授权:
                    self.生成授权.click()
                    self.random_wait(500, 1500)
                if 达人分销比例 != "":
                    self.达人分销比例.fill(达人分销比例.replace("%", "").strip())
                    self.random_wait(500, 1500)
                self.button_保存.click()
                try:
                    self.保存草稿成功提示.wait_for(state="visible", timeout=30_000)
                except Exception:
                    logger.warning(f"文档{file}保存草稿后未出现成功提示，可能保存失败，跳过")
                    row[1] = "失败"
                    row[2] = "保存草稿后未出现成功提示，可能保存失败"
                    self.is_failed = True
                    continue
                row[1] = "成功"
                row[4] = article_url
                logger.info(f"文档{file}处理完成，已保存为草稿")
                self.random_wait(2000, 3000)
                if 完成后移动至 != "":
                    self.move_to_done(完成后移动至, dir_name, file)
            except Exception as e:
                logger.exception(f"处理文档{file}出错，跳过", exc_info=True)
                row[1] = "失败"
                row[2] = str(e)
                row[4] = article_url
                self.is_failed = True
                continue
