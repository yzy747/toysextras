import requests
from toys_extras.base import Base

__version__ = "1.0.0"


class Toy(Base):

    def __init__(self):
        self.access_token = ""
        self.result_table_view: list = [['AppId', '状态', '错误信息']]

    def play(self):
        appid = self.config.get("扩展", "appid")
        appsecret = self.config.get("扩展", "secret")
        if not appid or not appsecret:
            self.result_table_view.append([appid, "失败", "请填写appid和secret"])
        url = "https://api.weixin.qq.com/cgi-bin/clear_quota/v2"
        payload = {"appid": appid, "appsecret": appsecret}
        response = requests.post(url, data=payload)
        resp_json = response.json()
        if response.ok:
            if resp_json["errcode"] == 0:
                self.result_table_view.append([appid, "成功", ""])
                return
        self.result_table_view.append([appid, "失败", resp_json["errmsg"]])
