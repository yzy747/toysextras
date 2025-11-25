from toys_extras.base import Base
from toys_logger import logger
from toys_utils import WeChatAPI, ToyError
import os
import shutil
from natsort import natsorted

__version__ = "1.0.5"


class Toy(Base):

    def __init__(self):
        self.access_token = ""
        self.result_table_view: list = [['文章名称', '状态', '错误信息']]

    def play(self):
        appid = self.config.get("扩展", "appid")
        secret = self.config.get("扩展", "secret")
        上传图片数量 = self.config.getint("扩展", "上传图片数量")
        txt首行是标题 = True if self.config.get("扩展", "txt首行是标题") == "是" else False
        存稿后移动文件到指定文件夹 = self.config.get("扩展", "存稿后移动文件到指定文件夹")

        网络代理 = self.config.get("扩展", "网络代理 -- 可选，填写格式“协议://用户名:密码@ip:port”")
        proxy = None
        if 网络代理:
            proxy = {"http": 网络代理, "https": 网络代理}

        公众号已设置 = True if appid and secret else False
        wechat_api = WeChatAPI(appid, secret, proxy)
        if 公众号已设置:
            try:
                wechat_api.set_access_token()
            except Exception as e:
                logger.warning(f"获取access_token失败: {e}")
                self.is_failed = True
                raise ToyError("登录公众号失败，请检查网络或代理")
            公众号已设置 = not wechat_api.access_token.startswith("登录公众号失败:")
        if not 公众号已设置:
            logger.warning("公众号未设置，无法上传图片")
            self.is_failed = True
            return
        if 上传图片数量 > 20:
            上传图片数量 = 20
        for file in self.files:
            if self.stop_event.is_set():
                break
            self.pause_event.wait()
            dir_path, file_name = os.path.split(file)
            file_name_without_ext, file_ext = os.path.splitext(file_name)
            if file_ext != ".txt":
                continue
            images = [file for file in os.listdir(dir_path) if os.path.splitext(file)[1] in [".jpg", ".png", ".jpeg"]]
            images = natsorted(images)
            if len(images) == 0:
                logger.warning(f"没有找到图片文件: {file}")
                self.result_table_view.append([file_name_without_ext, "失败", "没有找到图片文件"])
                self.is_failed = True
                continue
            image_media_ids = []
            if len(images) < 上传图片数量:
                上传图片数量_本文 = len(images)
            else:
                上传图片数量_本文 = 上传图片数量
            for image in images[:上传图片数量_本文]:
                image_path = os.path.join(dir_path, image)
                image_media_id = wechat_api.add_image_material(image_path)
                image_media_ids.append({"image_media_id": image_media_id})
            with open(file, "r", encoding="utf-8") as f:
                file_content = f.read()
            if txt首行是标题:
                file_content = file_content.replace("内容:", "内容：").replace("标题:", "标题：")
                file_content_split = file_content.split("内容：", 1)
                title = file_content_split[0].lstrip("标题：").strip()
                content = file_content_split[1]
            else:
                title = file_name_without_ext
                content = file_content
            content = content.strip()
            res = wechat_api.save_draft([{
                "article_type": "newspic",
                "title": title,
                "content": content,
                "need_open_comment": 0,
                "only_fans_can_comment": 0,
                "image_info": {
                    "image_list": image_media_ids
                }
            }])
            if "errmsg" in res:
                logger.exception(f"上传文章失败: {res['errmsg']}", exc_info=True)
                self.result_table_view.append([title, "失败", res["errmsg"]])
                self.is_failed = True
                continue
            self.result_table_view.append([title, "成功", ""])
            if 存稿后移动文件到指定文件夹:
                shutil.move(dir_path, os.path.join(存稿后移动文件到指定文件夹, os.path.basename(dir_path))) # type: ignore


