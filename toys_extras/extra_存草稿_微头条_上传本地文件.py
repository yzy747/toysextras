from toys_extras.articles import Articles
from playwright.sync_api import Page

__version__ = "1.0.0"


class Toy(Articles):

    def __init__(self, page: Page):
        super().__init__(page)
        self.url = "https://mp.toutiao.com/profile_v4/weitoutiao/publish?from=toutiao_pc"
        self.button_导入文档 = self.page.locator("text=文档导入")
        self.button_选择文档 = self.page.locator('input[type="file"]')
        self.button_保存 = self.page.get_by_role("button", name="存草稿")
        self.上传文档成功提示 = self.page.get_by_text("导入成功", exact=True).or_(self.page.get_by_text("图片上传成功", exact=True))
        self.保存草稿成功提示 = self.page.get_by_text("保存成功", exact=True)