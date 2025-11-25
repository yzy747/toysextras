import os
import re
from toys_extras.base_web import BaseWeb
from toys_utils import sanitize_filename
from toys_logger import logger
from playwright.sync_api import Page, TimeoutError
import random
from PIL import Image
from io import BytesIO

__version__ = '1.1.8'


class Toy(BaseWeb):

    def __init__(self, page: Page):
        super().__init__(page)
        self.result_table_view: list = [['文章连接', "状态", "错误信息", "保存路径"]]
        self.patten = re.compile(r"https?:\/\/sns-webpic-qc\.xhscdn\.com\/\d+\/[0-9a-z]+\/(\S+)!")
        self.title_locator = self.page.locator("#detail-title")
        self.content_locator = self.page.locator("#detail-desc .note-text")

    def get_article_title(self) -> str:
        return self.title_locator.text_content(timeout=2_000).strip()

    def get_article_content(self, tags: bool = False) -> str:
        content = ""
        detail_locators = self.content_locator.locator("xpath=/*")
        try:    
            detail_locators.last.wait_for()
        except TimeoutError:
            pass
        exclude_tags = ["note-content-user"]
        if not tags:
            exclude_tags.append("tag")
        for locator in detail_locators.all():
            class_name = locator.get_attribute("class")
            if class_name in exclude_tags:
                continue
            content += locator.text_content()
        return content

    def download_pictures(self, article_dir: str, 图片下载隔间: int):
        image_index = 1
        try:
            self.page.locator(".swiper-slide-active[data-swiper-slide-index]").last.wait_for(timeout=10000)
        except TimeoutError:
            pass

        图片下载隔间_max = 图片下载隔间 * 1000
        if 图片下载隔间_max < 1000:
            图片下载隔间_max = 1000
            图片下载隔间_min = 500
        else:
            图片下载隔间_min = 图片下载隔间_max - 500

        image_locator = self.page.locator("div[data-swiper-slide-index]:not(.swiper-slide-duplicate)").locator("img")
        for locator in image_locator.all():
            image_url = locator.get_attribute("src")
            match = self.patten.search(image_url)
            if not match:
                continue
            image_url = f"https://ci.xiaohongshu.com/{match.group(1)}?imageView2/format/png"
            if image_url:
                response = self.page.request.get(image_url, ignore_https_errors=True)
                if response.status == 200:
                    resource_picture = response.body()
                    image = Image.open(BytesIO(resource_picture))
                    image_type = "gif" if image.format.lower() == "gif" else "jpg"
                    img_file_path = os.path.join(article_dir, f"图{image_index}.{image_type}")
                    if image.mode != 'RGB':
                        image = image.convert('RGB')
                    image.save(img_file_path)
                    image_index += 1
            self.page.wait_for_timeout(random.randint(图片下载隔间_min, 图片下载隔间_max))
        return image_index

    def play(self):
        笔记链接 = self.config.get("扩展", "文章链接")
        存储目录 = self.config.get("扩展", "存储目录")
        保留话题 = True if self.config.get("扩展", "保留话题 -- 填是或否，是则采集时保留笔记中#话题") == "是" else False
        文章间隔 = self.config.get("扩展", "文章间隔 -- 填数字，单位秒，表示两篇笔记之间的时间间隔")
        图片下载间隔 = self.config.get("扩展", "图片下载间隔 -- 填数字，单位秒")
        if not 笔记链接 and not self.files:
            return
        if not 文章间隔 or not 文章间隔.isdigit():
            文章间隔 = 3
        else:
            文章间隔 = int(文章间隔)
        if not 图片下载间隔 or not 图片下载间隔.isdigit():
            图片下载间隔 = 2
        else:
            图片下载间隔 = int(图片下载间隔)
        urls = []
        if 笔记链接:
            urls.append(笔记链接)
        for file in self.files:
            if not file.endswith('.txt'):
                continue
            with open(file, "r", encoding="utf-8") as f:
                urls_in_file = f.readlines()
            for url in urls_in_file:
                if url.startswith("https://www.xiaohong"):
                    urls.append(url)
        for url in urls:
            try:
                self.page.goto(url)
                self.title_locator.or_(self.content_locator).last.wait_for()
                title = self.get_article_title()
                content = self.get_article_content(tags=保留话题)
                if not title or not content:
                    self.result_table_view.append([url, "失败", "标题或内容为空", ""])
                    continue
                file_title = sanitize_filename(title)
                # 检查文件标题是否已存在，如果存在则添加序号
                folder_title = file_title
                counter = 1
                while os.path.exists(os.path.join(存储目录, folder_title)):
                    folder_title = f"{file_title}（{counter}）"
                    counter += 1
                os.makedirs(os.path.join(存储目录, folder_title), exist_ok=True)
                with open(os.path.join(存储目录, folder_title, f"{file_title}.txt"), "w", encoding="utf-8") as f:
                    f.write(f"标题:{title}\n内容:\n{content}")
                self.download_pictures(os.path.join(存储目录, folder_title), 图片下载间隔)
                self.result_table_view.append([url, "成功", "", os.path.join(存储目录, folder_title)])
                self.page.wait_for_timeout(random.randint(1000, 3000))
            except Exception as e:
                logger.exception(e, exc_info=True)
                self.result_table_view.append([url, "失败", "", ""])
            finally:
                self.page.wait_for_timeout(文章间隔 * 1000)
        self.page.close()
