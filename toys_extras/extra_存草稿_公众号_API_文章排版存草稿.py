from toys_extras.base import Base
from toys_logger import logger
from toys_utils import WeChatAPI, ToyError, insert_image_link_to_markdown, MarkdownToHtmlConverter
import re
from natsort import natsorted
import os
from pathlib import Path
import random
import shutil
import requests

__version__ = "1.1.8"


class Toy(Base, MarkdownToHtmlConverter):

    def __init__(self):
        Base.__init__(self)
        MarkdownToHtmlConverter.__init__(self)
        self.access_token = ""
        self.image_url_prefix = "mmbiz.qpic.cn"
        self.result_table_view: list = [['文章名称', '状态', '错误信息', '文档路径', "多篇合一主篇"]]

    def upload_image(self, image_path):
        return self.upload_image_client(image_path)

    def get_image_links(self, file_content):
        links = re.findall(r'<img.*?src="(.*?)"', file_content)
        links.extend(re.findall(r'background(?:-image)?:\s*url\(&quot;(https?://.*?)&quot;\)', file_content))
        return links

    @staticmethod
    def get_default_thumb():
        return os.path.join(Path(__file__).parent.parent, "toys_extras_resource", "存草稿_公众号_API_markdown插图排版存草稿", "默认缩略图.png")

    def get_html_h1(self, html_content):
        return re.findall(r'<h1>(.*?)</h1>', html_content, re.DOTALL)

    def play(self):
        if not self.file_path:
            return
        if os.path.isdir(self.file_path):
            base_dir = Path(self.file_path)
        elif os.path.isfile(self.file_path):
            base_dir = Path(self.file_path).parent
        elif os.path.isfile(self.file_path.split(",")[0]):
            base_dir = Path(self.file_path.split(",")[0]).parent
        else:
            return

        是否存稿 = self.config.get("扩展", "是否存稿 -- 填是或否，仅选择md文件时生效") == "是"
        多篇合一 = True if self.config.get("扩展", "多篇合一 -- 编辑页新建消息") == "是" else False
        appid = self.config.get("扩展", "appid")
        secret = self.config.get("扩展", "secret")
        作者 = self.config.get("扩展", "作者")
        原文链接 = self.config.get("扩展", "原文链接")
        留言开关 = True if self.config.get("扩展", "留言开关") == "是" else False
        是否粉丝才可留言 = True if self.config.get("扩展", "是否粉丝才可留言") == "是" else False
        封面图 = self.config.get("扩展", "封面图 -- 可填序号或文件夹或包含素材id的txt文件，如填序号则从1开始，注意排版引导图片也包括在内")
        指定图片链接 = self.config.get("扩展", "指定图片链接 -- 包含图片链接的txt文件，每行一个，不填则使用md文件同目录图片")
        插图数量 = self.config.get("扩展", "插图数量")
        插图位置 = self.config.get("扩展", "插图位置 -- 不填时图片均匀插入文章，填写格式'1,5,7'")
        图片最小宽度 = self.config.get("扩展", "图片最小宽度")
        图片最小高度 = self.config.get("扩展", "图片最小高度")
        输出文件格式 = "txt" if self.config.get("扩展", "输出文件格式 -- 可填txt或html") not in ["txt", "html"] else self.config.get("扩展", "输出文件格式 -- 可填txt或html")
        排版输出目录 = self.config.get("扩展", "排版输出目录")
        完成后移动文件到指定文件夹 = self.config.get("扩展", "完成后移动文件到指定文件夹")

        if 完成后移动文件到指定文件夹:
            完成后移动文件到指定文件夹 = self.make_to_move_dir(完成后移动文件到指定文件夹)

        if not 排版输出目录 and not 是否存稿:
            logger.warning(f"排版输出目录和是否存稿都未开启，无法进行排版操作")
            self.result_table_view.append(["全部文章", "失败", f"排版输出目录和是否存稿都未开启，无法进行排版操作", "", ""])
            self.is_failed = True
            return
        if not 封面图:
            logger.warning(f"封面图未设置")
            self.result_table_view.append(["全部文章", "失败", f"封面图未设置", "", ""])
            self.is_failed = True
            return

        if os.path.isdir(封面图):
            files = os.listdir(封面图)
            if not files:
                logger.warning(f"封面图文件夹为空")
                self.result_table_view.append(["全部文章", "失败", f"封面图文件夹为空", "", ""])
                self.is_failed = True
                return

        if 插图数量 and 插图数量.isdigit():
            插图数量 = int(插图数量)
        else:
            插图数量 = 0

        if 图片最小宽度 and 图片最小宽度.isdigit():
            图片最小宽度 = int(图片最小宽度)
        else:
            图片最小宽度 = 0

        if 图片最小高度 and 图片最小高度.isdigit():
            图片最小高度 = int(图片最小高度)
        else:
            图片最小高度 = 0

        specified_image_links = []
        if os.path.isfile(指定图片链接):
            with open(指定图片链接, 'r', encoding='utf-8') as f: # type: ignore
                links = f.readlines()
            specified_image_links = [x.strip() for x in links]

        网络代理 = self.config.get("扩展", "网络代理 -- 可选，填写格式“协议://用户名:密码@ip:port”")
        proxy = None
        if 网络代理:
            proxy = {"http": 网络代理, "https": 网络代理}

        公众号已设置 = bool(appid and secret)
        wechat_api = WeChatAPI(appid, secret, proxy)
        if 公众号已设置:
            try:
                wechat_api.set_access_token()
            except Exception as e:
                self.is_failed = True
                logger.warning(f"获取access_token失败: {e}")
                raise ToyError("登录公众号失败，请检查网络或代理")
            公众号已设置 = not wechat_api.access_token.startswith("登录公众号失败:")
        if not 公众号已设置 and ((插图数量 and not specified_image_links) or 是否存稿):
            self.result_table_view.append(["全部文章", "失败", f"公众号登录失败，无法存稿及上传图片排版，请检查appid、secret或IP是否在白名单", "", ""])
            self.is_failed = True
            return
        
        groups = {}
        if 多篇合一:
            for file in self.files:
                file_path = Path(file)
                relative_path = file_path.relative_to(base_dir)
                if len(relative_path.parts) == 1:
                    groups.setdefault(base_dir, set()).add(file)
                elif len(relative_path.parts) == 2:
                    file_suffix = {os.path.splitext(f)[1] for f in os.listdir(file_path.parent)}
                    if len(file_suffix) == 1:
                        groups.setdefault(file_path.parent, set()).add(file)
                    else:
                        groups.setdefault(base_dir, set()).add(file)
                elif len(relative_path.parts) == 3:
                    groups.setdefault(file_path.parent.parent, set()).add(file)
                else:
                    logger.warning(f"文件 {file} 路径层级过深，无法识别")
                    return
            if groups:
                for group_dir, files in groups.items():
                    files = natsorted(list(files))
                    main_article = f"{os.path.basename(files[0])}_{random.randint(1000, 99999)}"
                    for file in files:
                        file_name = os.path.basename(file)
                        self.result_table_view.append([file_name, "待处理", "", file, main_article])
        else:
            for file in self.files:
                file_name = os.path.basename(file)
                self.result_table_view.append([file_name, "待处理", "", file, ""])

        default_thumb = ""
        last_main_article = ""
        lines = self.result_table_view[1:]
        total_count = len(lines)
        articles = []

        for index, line in enumerate(lines):
            if self.stop_event.is_set():
                break
            self.pause_event.wait()
            try:
                line[1] = "处理中"
                file = line[3]
                dir_name = os.path.dirname(file)
                file_name_without_ext, file_ext = os.path.splitext(os.path.basename(file))
                if file_ext not in [".txt", ".html", ".md"]:
                    line[1] = "失败"
                    line[2] = f"txt、html、md文件"
                    self.is_failed = True
                    continue
                file_content = self.read_file(file)
                if file_ext == ".md" or (file_ext == ".txt" and not any(tag in file_content for tag in ["<span", "<p", "<img"])):
                    template_dirs = self.get_article_template_dirs()
                    if not template_dirs:
                        logger.warning(f"没有找到模板文件")
                        line[1] = "失败"
                        line[2] = f"没有找到模板文件"
                        self.is_failed = True
                        return
                    if 插图数量 != 0:
                        # 查找md同目录下的图片文件
                        if specified_image_links:
                            image_urls = random.sample(specified_image_links, k=插图数量)
                        else:
                            if self.upload_image_client is None:
                                self.upload_image_client = wechat_api.upload_article_image
                            image_urls = self.get_available_images(dir_name, num=插图数量, min_width=图片最小宽度, min_height=图片最小高度)
                        if 插图位置:
                            positions = [int(x) for x in 插图位置.split(',')]
                        else:
                            positions = []
                        if image_urls:
                            file_content = insert_image_link_to_markdown(file_content, image_urls, positions)
                    file_content = self.article_convert(file_content, random.choice(template_dirs))
                    if 排版输出目录:
                        is_exist = os.path.exists(排版输出目录)
                        if not is_exist:
                            os.makedirs(排版输出目录)
                        html_file_name = f"{file_name_without_ext}.{输出文件格式}"
                        with open(os.path.join(排版输出目录, html_file_name), 'w', encoding='utf-8') as f: # type: ignore
                            f.write(file_content)
                    if not 是否存稿:
                        if 完成后移动文件到指定文件夹:
                            self.move_to_done(完成后移动文件到指定文件夹, dir_name, file)
                        line[1] = "排版完成"
                        continue

                if 封面图.isdigit():
                    links = self.get_image_links(file_content)
                    封面图序号 = int(封面图)
                    if links:
                        if 封面图序号 < len(links):
                            cover_image_url = links[封面图序号 - 1]
                        else:
                            cover_image_url = links[-1]
                        resp = requests.get(cover_image_url, stream=True, headers=self.header_with_ua)
                        random.seed(dir_name)
                        temp = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"temp{random.randint(10000, 99999999)}.jpg")
                        with open(temp, 'wb') as f:
                            f.write(resp.content)
                        thumb = wechat_api.add_thumb(temp)
                        os.remove(temp)
                    elif not default_thumb:
                        thumb = default_thumb = wechat_api.add_thumb(self.get_default_thumb())
                    else:
                        thumb = default_thumb
                elif os.path.isfile(封面图) and 封面图.endswith(".txt"):
                    with open(封面图, 'r', encoding='utf-8') as f: # type: ignore
                        thumbs = f.readlines()
                    thumb = random.choice(thumbs).strip()
                elif os.path.isdir(封面图):
                    files = os.listdir(封面图)
                    thumb = wechat_api.add_thumb(random.choice(files))
                elif not default_thumb:
                    thumb = default_thumb = wechat_api.add_thumb(self.get_default_thumb())
                else:
                    thumb = default_thumb
                title = self.get_html_h1(file_content)
                if not title:
                    title = file_name_without_ext
                else:
                    title = title[0]

                article = {
                    "title": title[:64],
                    "content": file_content,
                    "thumb_media_id": thumb
                }
                if 作者:
                    article["author"] = 作者
                if 原文链接:
                    article["content_source_url"] = 原文链接
                if 留言开关:
                    article["need_open_comment"] = 留言开关
                if 是否粉丝才可留言:
                    article["only_fans_can_comment"] = 是否粉丝才可留言

                articles.append(article)

                is_last_in_group = (
                        多篇合一 and
                        (index == total_count - 1 or lines[index + 1][4] != line[4])
                )
                if not 多篇合一 or (多篇合一 and is_last_in_group):
                    res = wechat_api.save_draft(articles)
                    save_draft_msg = ""
                    if "errmsg" in res:
                        save_draft_status = "失败"
                        save_draft_msg = f"保存草稿失败:{res['errmsg']}"
                        self.is_failed = True
                    else:
                        save_draft_status = "存稿成功"
                    if 多篇合一:
                        need_to_move_files = []
                        for l in lines:
                            if l[4] == line[4]:
                                l[1] = save_draft_status
                                l[2] = save_draft_msg
                                need_to_move_files.append(l[3])
                        if save_draft_status == "存稿成功" and 完成后移动文件到指定文件夹:
                            parent_dirs = set(os.path.dirname(f) for f in need_to_move_files)
                            if len(parent_dirs) == 1:
                                # 所有文件都在同一目录下
                                if dir_name == self.file_path:
                                    for f_to_move in need_to_move_files:
                                        shutil.move(f_to_move, 完成后移动文件到指定文件夹) # type: ignore
                                else:
                                    shutil.move(dir_name, os.path.join(完成后移动文件到指定文件夹, os.path.basename(dir_name)))  # type: ignore
                            else:
                                grand_parent_dir = os.path.dirname(dir_name)
                                if grand_parent_dir == self.file_path:
                                    for f_to_move in need_to_move_files:
                                        parent_dir = os.path.dirname(f_to_move)
                                        shutil.move(parent_dir, os.path.join(完成后移动文件到指定文件夹, os.path.basename(parent_dir)))  # type: ignore
                                else:
                                    shutil.move(grand_parent_dir, os.path.join(完成后移动文件到指定文件夹, os.path.basename(grand_parent_dir)))  # type: ignore
                    else:
                        line[1] = save_draft_status
                        line[2] = save_draft_msg
                        if save_draft_status == "存稿成功" and 完成后移动文件到指定文件夹:
                            self.move_to_done(完成后移动文件到指定文件夹, dir_name, file)
                    articles.clear()
                else:
                    line[1] = "已排版，待存稿"
            except Exception as e:
                line[1] = "失败"
                line[2] = f"{e}"
                self.is_failed = True
                logger.exception(f"处理文件{line[0]}失败", exc_info=e)
            finally:
                if line[4] != last_main_article:
                    last_main_article = line[4]
        try:
            if 完成后移动文件到指定文件夹:
                os.rmdir(完成后移动文件到指定文件夹)
        except OSError:
            pass
