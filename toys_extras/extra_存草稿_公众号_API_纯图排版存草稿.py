from toys_extras.base import Base
from toys_logger import logger
from toys_utils import WeChatAPI, ToyError, MarkdownToHtmlConverter
import os
import random
import shutil
from natsort import natsorted

__version__ = "1.0.6"


class Toy(Base, MarkdownToHtmlConverter):

    def __init__(self):
        Base.__init__(self)
        MarkdownToHtmlConverter.__init__(self)
        self.access_token = ""
        self.image_url_prefix = "mmbiz.qpic.cn"
        self.result_table_view: list = [['文章名称', '状态', '错误信息']]

    def upload_image(self, image_path) -> str:
        return self.upload_image_client(image_path)

    def get_image_dirs(self):
        files_map = {}
        for file in self.files:
            dir_name = os.path.dirname(file)
            file_ext = os.path.splitext(file)[1]
            if file_ext not in [".jpg", ".jpeg", ".png"]:
                continue
            files_map.setdefault(dir_name, []).append(file)
        return files_map

    def play(self):
        appid = self.config.get("扩展", "appid")
        secret = self.config.get("扩展", "secret")
        是否存稿 = True if self.config.get("扩展", "是否存稿") == "是" else False
        作者 = self.config.get("扩展", "作者")
        原文链接 = self.config.get("扩展", "原文链接")
        留言开关 = True if self.config.get("扩展", "留言开关") == "是" else False
        是否粉丝才可留言 = True if self.config.get("扩展", "是否粉丝才可留言") == "是" else False
        输出文件格式 = "txt" if self.config.get("扩展", "输出文件格式 -- 可填txt或html") not in ["txt", "html"] else self.config.get("扩展", "输出文件格式 -- 可填txt或html")
        排版输出目录 = self.config.get("扩展", "排版输出目录")
        完成后移动文件到指定文件夹 = self.config.get("扩展", "完成后移动文件到指定文件夹")

        if not 排版输出目录 and not 是否存稿:
            logger.warning("排版输出目录和是否存稿不能同时为空")
            self.is_failed = True
            return

        网络代理 = self.config.get("扩展", "网络代理 -- 可选，填写格式“协议://用户名:密码@ip:port”")
        proxy = None
        if 网络代理:
            proxy = {"http": 网络代理, "https": 网络代理}

        wechat_api = WeChatAPI(appid, secret, proxy)
        公众号已设置 = True if appid and secret else False
        if 公众号已设置:
            try:
                wechat_api.set_access_token()
            except Exception as e:
                logger.warning(f"获取access_token失败: {e}")
                self.is_failed = True
                self.result_table_view.append(["所有", "失败", f"获取access_token失败: {e}"])
                raise ToyError("登录公众号失败，请检查网络或代理")
            公众号已设置 = not wechat_api.access_token.startswith("登录公众号失败:")

        if not 公众号已设置:
            logger.warning("公众号未设置，此功能不可用")
            self.is_failed = True
            self.result_table_view.append(["所有", "失败", "公众号未设置，此功能不可用，请检查AppID和Secret以及白名单"])
            return

        self.upload_image_client = wechat_api.upload_article_image

        template_dirs = self.get_image_article_template_dirs()
        if not template_dirs:
            logger.warning(f"没有找到模板文件")
            self.is_failed = True
            self.result_table_view.append(["所有", "失败", "没有找到模板文件，请检查多模板文件夹配置"])
            return

        if 排版输出目录:
            is_exist = os.path.exists(排版输出目录)
            if not is_exist:
                os.makedirs(排版输出目录)


        for dir_name, files in self.get_image_dirs().items():
            if not files:
                continue
            files = natsorted(files)
            image_links = [wechat_api.upload_article_image(file) for file in files]
            html_content = self.images_article_convert(image_links, random.choice(template_dirs))
            if 排版输出目录:
                html_file_name = os.path.basename(dir_name)
                with open(os.path.join(排版输出目录, f"{html_file_name}.{输出文件格式}"), 'w', encoding='utf-8') as f:  # type: ignore
                    f.write(html_content)
            if not 是否存稿:
                if 完成后移动文件到指定文件夹:
                    shutil.move(dir_name, os.path.join(完成后移动文件到指定文件夹, dir_name))  # type: ignore
                self.result_table_view.append([dir_name, "排版成功", ""])
                continue
            title = self.get_html_h1(html_content)
            if not title:
                title = os.path.basename(dir_name)
            else:
                title = title[0]
            article = {
                "title": title,
                "content": html_content,
                "thumb_media_id": wechat_api.add_thumb(files[0]),
            }
            if 作者:
                article["author"] = 作者
            if 原文链接:
                article["content_source_url"] = 原文链接
            if 留言开关:
                article["need_open_comment"] = 留言开关
            if 是否粉丝才可留言:
                article["only_fans_can_comment"] = 是否粉丝才可留言
            res = wechat_api.save_draft([article])
            if "errmsg" in res:
                self.result_table_view.append([dir_name, "失败", res["errmsg"]])
                self.is_failed = True
            else:
                self.result_table_view.append([dir_name, "成功", ""])
            if 完成后移动文件到指定文件夹:
                shutil.move(dir_name, os.path.join(完成后移动文件到指定文件夹, dir_name))  # type: ignore


