import json
import openpyxl
from toys_extras.base_web import BaseWeb
from playwright.sync_api import Page
from toys_logger import logger
from datetime import datetime, timedelta
import requests
import os
import re

__version__ = '1.0.1'


class Toy(BaseWeb):

    def __init__(self, page: Page):
        super().__init__(page)
        self.url = "https://mp.weixin.qq.com/"
        self.headers = {
            "Host": "mp.weixin.qq.com",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36 Edg/127.0.0.0",
        }
        self.cookies = {}
        self.token = ""
        self.result_table_view: list = [['文章标题', "链接", "发布时间", "昵称"]]

    def get_wechat_subscription(self, query):
        """获取微信公众号信息

        根据公众号名称获取其 fakeid 和昵称。

        Args:
            token (str): 登录令牌
            query (str): 公众号名称

        Returns:
            tuple: (fakeid, nickname) - 公众号ID和昵称
        """
        url = f"https://mp.weixin.qq.com/cgi-bin/searchbiz?action=search_biz&token={self.token}&lang=zh_CN&f=json&ajax=1&random=0.5182749224035845&query={query}&begin=0&count=5"
        response = requests.get(url, headers=self.headers, cookies=self.cookies, timeout=(30, 60)).json()
        fakeid = response["list"][0]["fakeid"]  # 获取第一个匹配结果的ID
        nickname = response["list"][0]["nickname"]  # 获取昵称
        return fakeid, nickname

    def get_articles(self, begin, token, fakeid):
        """获取公众号文章

        获取指定公众号的所有文章并保存。

        Args:
            token (str): 登录令牌
            fakeid (str): 公众号ID
        """
        params = {
            'sub': 'list',
            'search_field': 'null',
            'begin': begin,
            'count': '5',
            'query': '',
            'fakeid': fakeid,
            'type': '101_1',
            'free_publish_type': '1',
            'sub_action': 'list_ex',
            'fingerprint': '5ff7042658f629993a639b834a9b0ac2',
            'token': token,
            'lang': 'zh_CN',
            'f': 'json',
            'ajax': '1',
        }
        response = requests.get('https://mp.weixin.qq.com/cgi-bin/appmsgpublish', params=params, cookies=self.cookies, headers=self.headers)
        return response.json()

    def add_cookie(self, cookie_list):
        """添加cookie

        Args:
            cookie_list (list): 格式为[(name, value), (name, value)]
        """
        for cookie in cookie_list:
            if "qq.com" in cookie["domain"]:
                self.cookies[cookie["name"]] = cookie["value"]
        self.cookies["wxtokenkey"] = "777"
        self.cookies["payforreadsn"] = "EXPIRED"


    def play(self):
        公众号昵称列表 = self.config.get("扩展", "公众号昵称，多个公众号用英文逗号分隔")
        发布日期 = self.config.get("扩展", "发布日期")
        发布时间起始 = self.config.get("扩展", "发布时间起始")
        发布时间截止 = self.config.get("扩展", "发布时间截止")
        存储目录 = self.config.get("扩展", "存储目录")
        if not 公众号昵称列表:
            logger.error("公众号昵称未设置，请在配置文件中设置")
            self.is_failed = True
            self.result_table_view.append(["公众号昵称未设置", "", "", "", "", ""])
            return

        if not 发布日期:
            logger.info("发布日期未设置，不进行采集")
            self.is_failed = True
            self.result_table_view.append(["发布日期未设置", "", "", "", "", ""])
            return

        publish_date = datetime.now() - timedelta(days=int(发布日期))
        if 发布时间起始:
            publish_time_start = datetime.strptime(发布时间起始, '%H:%M:%S')
            publish_time_start = publish_date.replace(hour=publish_time_start.hour, minute=publish_time_start.minute, second=publish_time_start.second, microsecond=0)
        else:
            publish_time_start = publish_date.replace(hour=0, minute=0, second=0, microsecond=0)
        if 发布时间截止:
            publish_time_end = datetime.strptime(发布时间截止, '%H:%M:%S')
            publish_time_end = publish_date.replace(hour=publish_time_end.hour, minute=publish_time_end.minute, second=publish_time_end.second, microsecond=0)
        else:
            publish_time_end = datetime.now().replace(microsecond=0)

        # 将发布时间起始和截止转换为时间戳
        publish_time_start_timestamp = int(publish_time_start.timestamp())
        publish_time_end_timestamp = int(publish_time_end.timestamp())

        self.navigate()
        self.page.locator('[title="公众号"]').wait_for()
        if self.page.locator("a", has_text="登录").is_visible():
            self.page.locator("a", has_text="登录").click()

        # 提取浏览器cookie
        cookie_list = self.page.context.cookies()
        self.add_cookie(cookie_list)
        self.token = re.search(r"token=([^&]+)", self.page.url).group(1)

        公众号昵称列表 = 公众号昵称列表.split(",")
        collect_articles = []
        for 公众号昵称 in 公众号昵称列表:
            fakeid, nickname = self.get_wechat_subscription(公众号昵称)
            for i in range(0, 1000, 5):
                break_flag = False
                resp_json = self.get_articles(i, self.token, fakeid)
                publish_page = resp_json.get("publish_page", '')
                if not publish_page:
                    logger.error("获取文章列表失败")
                    break
                publish_list = json.loads(publish_page).get("publish_list", [])
                if not publish_list:
                    break
                for app_msg in publish_list:
                    app_msg = json.loads(app_msg["publish_info"]).get("appmsgex", [])
                    if not app_msg:
                        continue
                    app_msg = app_msg[0]
                    publish_time = int(app_msg["update_time"])
                    # publish_time 小于发布时间起始，跳过
                    if publish_time < publish_time_start_timestamp:
                        break_flag = True
                        break
                    # publish_time 大于发布时间截止，跳过
                    if publish_time > publish_time_end_timestamp:
                        continue
                    # 将publish_time转换为"YYYY-MM-DD HH:MM:SS"格式
                    publish_time = datetime.fromtimestamp(publish_time).strftime("%Y-%m-%d %H:%M:%S")
                    title = app_msg["title"]
                    link = app_msg["link"]
                    author = 公众号昵称
                    collect_articles.append([title, link, publish_time, author])
                    self.result_table_view.append([title, link, publish_time, author])
                if break_flag:
                    break
                else:
                    self.random_wait(1000, 2000)
        if not collect_articles:
            logger.info("没有找到符合条件的文章")
            return
        filename = f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_文章列表.xlsx"
        filepath = os.path.join(存储目录, filename)
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.append(self.result_table_view[0])
        for row in collect_articles:
            sheet.append(row)

        workbook.save(filepath)
