from toys_extras.base_web import BaseWeb
from playwright.sync_api import Page, TimeoutError
from toys_logger import logger
from toys_utils import MarkdownToHtmlConverter, insert_image_link_to_markdown, copy_to_clipboard, exec_cmd_with_run
import os
import re
import json
import random
from natsort import natsorted
from pathlib import Path
import shutil
from glob import glob


__version__ = "1.2.10"


class Toy(BaseWeb, MarkdownToHtmlConverter):

    def __init__(self, page: Page):
        BaseWeb.__init__(self, page)
        MarkdownToHtmlConverter.__init__(self)
        self.url = "https://mp.weixin.qq.com"
        self.image_url_prefix = "mmbiz.qpic.cn"
        self.token = ""
        self.result_table_view: list = [['文件名', '状态', "错误信息", '文档路径', "多篇合一主篇"]]

    # ── 配置解析辅助 ──────────────────────────────

    def _cfg(self, key, fallback=""):
        return self.config.get("扩展", key, fallback=fallback)

    def _cfg_bool(self, key, true_val="是"):
        return self._cfg(key) == true_val

    def _cfg_int(self, key, default=0):
        v = self._cfg(key)
        return int(v) if v and v.isdigit() else default

    def _parse_config(self):
        c = {
            "前置执行": self._cfg("前置执行"),
            "是否存稿": self._cfg_bool("是否存稿 -- 填是或否，仅选择md文件时生效"),
            "多篇合一": self._cfg_bool("多篇合一 -- 编辑页新建消息"),
            "作者": self._cfg("作者"),
            "原创声明": self._cfg("原创声明 -- 填写文字原创或者不声明"),
            "留言开关": self._cfg_bool("留言开关 -- 填写开启或者不开启", "开启"),
            "封面图": self._cfg("封面图 -- 可填序号或文件夹，如填序号则从1开始，注意排版引导图片也包括在内"),
            "合集": self._cfg("合集"),
            "原文链接": self._cfg("原文链接"),
            "创作来源": self._cfg("创作来源"),
            "素材来源": self._cfg("素材来源"),
            "来源平台": self._cfg("来源账号/平台"),
            "事件时间": self._cfg("事件时间"),
            "事件地点": self._cfg("事件地点"),
            "平台推荐": self._cfg("平台推荐"),
            "文中空行": self._cfg_bool("文中插入1个空行 -- 填写是或否"),
            "随机分割": self._cfg_bool("随机分割"),
            "指定图片链接": self._cfg("指定图片链接 -- 包含图片链接的txt文件，每行一个，不填则使用md文件同目录图片"),
            "插图数量": self._cfg_int("插图数量"),
            "插图位置": self._cfg("插图位置 -- 不填时图片均匀插入文章，填写格式'1,5,7'"),
            "图片最小宽度": self._cfg_int("图片最小宽度"),
            "图片最小高度": self._cfg_int("图片最小高度"),
            "视频": self._cfg("视频"),
            "话题数量": self._cfg_int("话题数量 -- 话题数量小于话题个数时，将会随机抽取"),
            "排版输出目录": self._cfg("排版输出目录"),
            "完成后移动至": self._cfg("完成后移动至"),
        }
        话题_raw = self._cfg("话题 -- 多个话题用英文逗号隔开，使用此功能排版时生效")
        c["话题"] = [x.strip() for x in 话题_raw.split(",")] if 话题_raw else []
        fmt = self._cfg("输出文件格式 -- 可填txt或html")
        c["输出文件格式"] = fmt if fmt in ("txt", "html") else "txt"
        return c

    # ── 登录辅助 ──────────────────────────────────

    def _login_and_get_token(self, page: Page):
        page.goto(self.url)
        page.locator('[title="公众号"]').or_(page.locator('[title="服务号"]')).wait_for()
        login_button = page.locator("a", has_text=re.compile(r"^登录$"))
        if login_button.is_visible():
            login_button.click()
        self.token = page.url.split("token=")[1].split("&")[0]

    # ── 图片上传 ──────────────────────────────────

    def upload_image(self, image_path):
        self.upload_image_client.bring_to_front()
        if "type=2" not in self.upload_image_client.url:
            url = f"{self.url}/cgi-bin/filepage?type=2&begin=0&count=12&token={self.token}&lang=zh_CN"
            self.upload_image_client.goto(url)
            self.upload_image_client.locator(".weui-desktop-block__title", has_text="素材库").wait_for(state="visible")

        upload_btn_locator = self.upload_image_client.locator(".weui-desktop-upload_global-media")
        upload_btn_locator.wait_for(state="visible")

        image_locator = self.upload_image_client.locator("li[class*=weui-desktop-img-picker]").first
        if image_locator.is_visible():
            background_style = image_locator.locator('[role="img"]').get_attribute("style")
            current_image_link = background_style.split('url("')[1].split('")')[0]
        else:
            current_image_link = ""

        with self.upload_image_client.expect_response(lambda response: "/cgi-bin/filetransfer" in response.url) as response:
            with self.upload_image_client.expect_file_chooser() as fc:
                upload_btn_locator.click()
            fc.value.set_files([image_path])
        try:
            url = response.value.json()["cdn_url"].replace('\\', '')
            self.upload_image_client.locator(".weui-desktop-block__title", has_text="素材库").wait_for(state="visible")
            return url
        except:
            logger.info("通过Response获取图片链接失败，尝试通过网页获取图片链接")

        for _ in range(30):
            self.upload_image_client.locator(".weui-desktop-block__title", has_text="素材库").wait_for(state="visible")
            image_locator = self.upload_image_client.locator("li[class*=weui-desktop-img-picker]").first
            image_locator.wait_for(state="visible")
            background_style = image_locator.locator('[role="img"]').get_attribute("style")
            image_link = background_style.split("url('")
            if len(image_link) > 1:
                image_link = image_link[1].split("')")[0]
                if image_link != current_image_link:
                    return image_link
            self.random_wait(1000, 1500)

    # ── 视频上传 / 查询 ──────────────────────────

    def upload_video(self, video_path, max_retries=3):
        add_video_url = self.url + f"/cgi-bin/appmsg?t=media/videomsg_edit&action=video_edit&type=15&isNew=1&token={self.token}&lang=zh_CN"
        
        self.page.bring_to_front()
        self.page.goto(add_video_url, wait_until="domcontentloaded")

        selector = "input[name=vid][type=file]"
        self.page.locator(selector).wait_for(state="attached", timeout=60_000)

        cdp_session = self.page.context.new_cdp_session(self.page)
        dom_snapshot = cdp_session.send("DOM.getDocument")
        node_result = cdp_session.send("DOM.querySelector", {
            "nodeId": dom_snapshot["root"]["nodeId"],
            "selector": selector
        })
        if not node_result or "nodeId" not in node_result:
            raise Exception("无法找到文件输入节点的nodeId")

        cdp_session.send("DOM.setFileInputFiles", {
            "nodeId": node_result["nodeId"],
            "files": [os.path.abspath(video_path)]
        })
        self.page.get_by_text("视频上传成功").wait_for(state="visible", timeout=180_000)
        cdp_session.detach()

        random_order = str(random.randint(999, 1000000))
        video_title = os.path.basename(video_path).split(".")[0]
        video_title = video_title[:64 - len(random_order)] + random_order

        for attempt in range(max_retries):
            try:
                self.page.locator(".cover__options__item img").first.wait_for(state="visible", timeout=120_000)
                self.page.locator(".cover__options__item img").first.click()
                
                self.page.get_by_role("button", name="完成").wait_for(state="visible", timeout=10_000)
                self.page.wait_for_timeout(1000)
                self.page.get_by_role("button", name="完成").click()

                self.page.locator("input[name=title]").fill(video_title)
                self.page.locator("[class*=video-setting]", has_text="原创声明").locator("label").first.click()
                self.page.get_by_role("button", name="确定").click()
                self.page.wait_for_timeout(2000)
                self.page.get_by_text("我已阅读并同意《公众平台视频上传服务规则》").click()
                self.page.wait_for_timeout(1000)
                self.page.get_by_role("button", name="保存", exact=True).click()
                
                return video_title
                
            except Exception as e:
                logger.warning(f"视频元素操作失败 (第{attempt + 1}次尝试): {e}")
                if attempt == max_retries - 1:       
                    raise Exception(f"视频元素操作失败，已重试{max_retries}次: {e}")

    def wait_video_check(self, video_title, max_retries=3):
        url = self.url + f"/cgi-bin/appmsg?begin=0&count=9&t=media/video_list&action=list_video&type=15&query={video_title}&token={self.token}&lang=zh_CN"
        for _ in range(max_retries):
            try:
                try:
                    self.page.goto(url)
                except Exception:
                    continue
                self.page.wait_for_timeout(1000)
                approved = self.page.locator("tr").filter(has_text=video_title, visible=True).get_by_text("已通过")
                no_result = self.page.locator("tr").get_by_text("没有搜索结果，请重新输入关键字或者查看")
                approved.or_(no_result).wait_for(state="visible", timeout=180_000)
                if no_result.is_visible():
                    continue
                if approved.is_visible():
                    return True       
            except TimeoutError:
                return False
            except Exception:
                self.random_wait(1000, 2000)
                continue
        return False

    # ── 草稿保存（循环重试）────────────────────────

    def save_draft(self, page: Page):
        success_loc = page.locator("#js_save_success").get_by_text("已保存", exact=True).locator("visible=true")
        saving_loc = page.get_by_text("已有流程保存中，请稍后再试").locator("visible=true")

        for _ in range(3):
            page.get_by_role("button", name="保存为草稿").click()
            try:
                success_loc.or_(saving_loc).wait_for(state="attached", timeout=5000)
                if saving_loc.is_visible():
                    已保存 = page.locator(".auto_save_container").get_by_text("已保存")
                    自动保存失败 = page.locator(".auto_save_container").get_by_text("自动保存失败")
                    已保存.or_(自动保存失败).wait_for(state="attached", timeout=30_000)
                    self.random_wait(1000, 2000)
                    page.get_by_role("button", name="保存为草稿").click()
                    try:
                        success_loc.wait_for(state="attached", timeout=5_000)
                    except Exception:
                        pass
                return True
            except Exception:
                continue
        return False

    # ── 编辑器：打开 / 添加文章 ───────────────────

    def _open_new_article(self, page_home):
        page_home.bring_to_front()
        with page_home.expect_popup() as popup_info:
            page_home.locator(".new-creation__menu-item", has_text="文章").click()
        return popup_info.value

    def _add_article_to_popup(self, popup):
        popup.bring_to_front()
        if popup.locator(".weui-desktop-dialog").locator("visible=true").first.is_visible():
            popup.locator(".weui-desktop-dialog__close-btn").locator("visible=true").first.click()
        popup.locator("#js_add_appmsg").click()
        self.random_wait(200, 400)
        popup.locator('.js_create_article[title="写新文章"]').evaluate("element => element.click()")

    # ── 编辑器：粘贴内容 ─────────────────────────

    def _paste_content(self, popup, file_content):
        article_div = popup.locator("div[contenteditable=true]:visible")
        if any(tag in file_content for tag in ["<html", "<body", "<head"]):
            chinese_src = "".join(re.findall(r"[\u4e00-\u9fa5]+", file_content))
            for _ in range(10):
                article_div.click()
                copy_to_clipboard(file_content)
                logger.info(f"粘贴 {file_content[:10]} 到文章中")
                popup.keyboard.press("Control+V")
                chinese_dst = "".join(re.findall(r"[\u4e00-\u9fa5]+", article_div.inner_text()))
                logger.info(f"粘贴完成，文章内容为 {article_div.inner_text()[:10]}")
                if chinese_dst and chinese_src and chinese_dst[:10] not in chinese_src:
                    article_div.clear()
                    self.random_wait(1000, 5000)
                else:
                    article_div.evaluate("element => element.scrollIntoView({ behavior: 'smooth', block: 'start' })")
                    self.random_wait(500, 1500)
                    break
        else:
            article_div.evaluate("(element, html) => { element.innerHTML = html }", file_content)
            self.random_wait(1000, 2000)

    # ── 编辑器：设置封面图 ────────────────────────

    def _set_cover(self, popup, 封面图):
        self.random_wait()
        popup.locator(".select-cover__btn").click(timeout=10_000)
        if 封面图.isdigit():
            popup.locator(".js_cover_preview_new .js_selectCoverFromContent").evaluate("element => element.click()")
            popup.locator(".appmsg_content_img_item").nth(int(封面图) - 1).click()
        else:
            cover_image = 封面图
            if os.path.isdir(封面图):
                cover_images = [os.path.join(封面图, f) for f in os.listdir(封面图) if f.endswith(('.jpg', '.png', '.jpeg'))]
                cover_image = random.choice(cover_images)
            popup.locator(".js_cover_preview_new .js_imagedialog").evaluate("element => element.click()")
            with popup.expect_file_chooser() as fc:
                self.random_wait()
                popup.locator(".js_upload_btn_container", has_text="上传文件").locator("visible=true").click()
            fc.value.set_files([cover_image])
            popup.get_by_text("上传成功").wait_for()
            self.random_wait()

        next_btn = popup.locator(".weui-desktop-btn", has_text="下一步")
        while "btn_disabled" in next_btn.get_attribute("class"):
            self.random_wait()
        self.random_wait(1000, 2000)
        next_btn.click()
        self.random_wait(1000, 2000)
        popup.get_by_role("button", name="确认").click()
        loading = popup.locator("#js_cover_area .weui-desktop-loading").locator("visible=true")
        try:
            loading.wait_for(state="attached", timeout=2_000)
        except Exception:
            ...
        finally:
            loading.wait_for(state="detached")
        self.random_wait()

    # ── Markdown 内容预处理 ──────────────────────

    def _prepare_md_content(self, file_content, file, dir_name, cfg, specified_image_links, template_dirs, topics):
        if cfg["插图数量"]:
            if specified_image_links:
                image_urls = random.sample(specified_image_links, k=cfg["插图数量"])
            else:
                image_urls = self.get_available_images(dir_name, num=cfg["插图数量"],
                                                       min_width=cfg["图片最小宽度"], min_height=cfg["图片最小高度"])
            positions = [int(x) for x in cfg["插图位置"].split(',')] if cfg["插图位置"] else []
            if image_urls:
                file_content = insert_image_link_to_markdown(file_content, image_urls, positions)

        file_content = self.article_convert(file_content, random.choice(template_dirs), topics=topics, random_split=cfg["随机分割"])

        if cfg["排版输出目录"]:
            os.makedirs(cfg["排版输出目录"], exist_ok=True)
            out_name = f"{os.path.splitext(os.path.basename(file))[0]}.{cfg['输出文件格式']}"
            with open(os.path.join(cfg["排版输出目录"], out_name), 'w', encoding='utf-8') as f:  # type: ignore
                f.write(file_content)

        return file_content

    # ── 编辑器：设置文章属性 ──────────────────────

    def _set_article_options(self, popup: Page, cfg, video_files):
        if cfg["文中空行"]:
            contents_loc = popup.locator('div[contenteditable="true"] > p,section')
            middle_element = contents_loc.nth(len(contents_loc.all()) // 2)
            middle_element.evaluate("element => element.insertAdjacentHTML('afterend', '<br>')")
        
        if video_files:
            try:
                video_index = int(cfg["视频"])
            except ValueError:
                video_index = -1
            boundbox = popup.locator('div[contenteditable="true"] > p,section').nth(video_index).bounding_box()
            popup.locator('div[contenteditable="true"] > p,section').nth(video_index).click(position={"x": boundbox["width"] -1 , "y": boundbox["height"] -1 })
            popup.locator("#js_editor_insertvideo").click()
            self.random_wait(2000, 3000)
            for video in video_files:
                video_found = False
                for _ in range(100):
                    if popup.locator(".more-video__item", has_text=video).is_visible():
                        popup.locator(".more-video__item", has_text=video).locator(".more-video__item-wrp").click()
                        video_found = True
                        self.random_wait()
                        break
                    next_btn = popup.locator(".weui-desktop-pagination__nav .weui-desktop-btn_mini")
                    if next_btn.is_visible() and next_btn.is_enabled():
                        next_btn.click()
                        self.random_wait(2000, 3000)
                    else:
                        break
                if not video_found:
                    logger.warning(f"视频 {video} 未找到")
            popup.get_by_role("button", name="确定").click()


        if cfg["作者"]:
            popup.locator("#author").fill(cfg["作者"])

        if cfg["封面图"]:
            if not os.path.exists(cfg["封面图"]) and not cfg["封面图"].isdigit():
                raise ValueError(f"封面图 {cfg['封面图']} 不存在")
            self._set_cover(popup, cfg["封面图"])

        if cfg["原创声明"] and cfg["原创声明"] != "不声明":
            popup.locator("#js_original .js_original_type").locator("visible=true").click()
            popup.locator(".original_agreement").wait_for()
            is_checked = popup.evaluate('''() => {
              const i = document.querySelector('i.weui-desktop-icon-checkbox');
              return window.getComputedStyle(i, '::before').content;
            }''')
            if is_checked == "none":
                popup.locator(".original_agreement label").click(position={"x": 10, "y": 10})
                self.random_wait()
            popup.get_by_role("button", name="确定").click()
            self.random_wait()

        留言已开启 = popup.locator("#js_comment_and_fansmsg_area .selected").count() > 0
        if cfg["留言开关"] != 留言已开启:
            popup.locator("#js_comment_and_fansmsg_area").click()
            self.random_wait(300, 1000)
            if 留言已开启:
                popup.locator(".comment-switcher").first.click()
                self.random_wait(300, 1000)
            popup.get_by_role("button", name="确定").click()
            self.random_wait(300, 1000)

        if cfg["合集"]:
            popup.locator("#js_article_tags_area .js_article_tags_label").click()
            popup.get_by_placeholder("请选择合集").fill(cfg["合集"])
            popup.locator(".select-opt-li", has_text=cfg["合集"]).first.click()
            self.random_wait()
            popup.get_by_role("button", name="确认").click()

        if cfg["原文链接"]:
            popup.locator("#js_article_url_area .js_article_url_allow_click").click()
            popup.get_by_placeholder("输入或粘贴原文链接").fill(cfg["原文链接"])
            popup.get_by_role('link', name='确定').locator("visible=true").click()
            self.random_wait(500, 1000)

        if cfg["创作来源"] and cfg["创作来源"] != "不声明":
            popup.locator("#js_claim_source_area .js_claim_source_desc").click()
            popup.locator(".weui-desktop-form__check-label", has_text=cfg["创作来源"]).click()
            if cfg["创作来源"] == "素材来源官方媒体/网络新闻":
                popup.locator(".weui-desktop-form__check-label", has_text=cfg["素材来源"]).click()
                self.random_wait(500, 1000)
                popup.locator(".claim-source_offcial_other input").fill(cfg["来源平台"])
                self.random_wait(500, 1000)
                popup.locator(".claim-source_offcial_time input").click()
                popup.locator(".weui-desktop-picker__selected").click()
                popup.locator(".claim-source_offcial_time input").evaluate(f"element => element.value = '{cfg['事件时间']}'")
                self.random_wait(500, 1000)
                popup.locator(".region-text").click()
                places = cfg["事件地点"].split(">")
                for i, place in enumerate(places):
                    place = place.strip()
                    loc = popup.locator("div.item", has_text=place)
                    if i == len(places) - 1:
                        loc.click()
                    else:
                        loc.evaluate("element => element.click()")
                    self.random_wait(300, 500)
            self.random_wait(500, 1000)
            popup.get_by_role("button", name='确认').locator("visible=true").click()
            self.random_wait()

        if cfg["平台推荐"] and cfg["平台推荐"] != "开启":
            popup.locator("#js_not_recommend_area .js_not_recommend_desc").click()
            popup.locator(".weui-desktop-form__check-label[for^=not_recomment]").get_by_text(cfg["平台推荐"], exact=True).click()

    # ── 构建结果表 ────────────────────────────────

    def _build_result_table(self, base_dir, 多篇合一):
        if not 多篇合一:
            for file in self.files:
                self.result_table_view.append([os.path.basename(file), "待处理", "", file, ""])
            return True

        groups = {}
        for file in self.files:
            file_path = Path(file)
            depth = len(file_path.relative_to(base_dir).parts)
            if depth == 1:
                groups.setdefault(base_dir, set()).add(file)
            elif depth == 2:
                file_suffix = {os.path.splitext(f)[1] for f in os.listdir(file_path.parent)}
                key = file_path.parent if len(file_suffix) == 1 else base_dir
                groups.setdefault(key, set()).add(file)
            elif depth == 3:
                groups.setdefault(file_path.parent.parent, set()).add(file)
            else:
                logger.warning(f"文件 {file} 路径层级过深，无法识别")
                return False

        for _, files in groups.items():
            files = natsorted(list(files))
            main_article = f"{os.path.basename(files[0])}_{random.randint(1000, 99999)}"
            for file in files:
                self.result_table_view.append([os.path.basename(file), "待处理", "", file, main_article])
        return True

    # ── 主流程 ────────────────────────────────────

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

        cfg = self._parse_config()

        template_dirs = self.get_article_template_dirs()

        if cfg["创作来源"] == "素材来源官方媒体/网络新闻" and (not cfg["素材来源"] or not cfg["来源平台"]):
            self.result_table_view.append(["所有", "失败", "素材来源官方媒体/网络新闻时，素材来源和来源账号/平台不能为空", "", ""])
            self.is_failed = True
            return

        完成后移动 = self.make_to_move_dir(cfg["完成后移动至"]) if cfg["完成后移动至"] else None

        specified_image_links = []
        if os.path.isfile(cfg["指定图片链接"]):
            with open(cfg["指定图片链接"], 'r', encoding='utf-8') as f:  # type: ignore
                specified_image_links = [x.strip() for x in f.readlines()]

        if cfg["前置执行"]:
            exec_cmd_with_run(cfg["前置执行"])

        topics = None
        if cfg["话题数量"] or cfg["话题"]:
            topics = {"type": "wx", "num": cfg["话题数量"], "tags": cfg["话题"]}

        context = self.page.context
        page_home, popup = None, None
        
        video_file_map = {}
        if cfg["视频"]:
            self._login_and_get_token(self.page)
            for file in self.files:
                for video_file in glob(os.path.join(os.path.dirname(file), "*.mp4")):
                    video_title = self.upload_video(video_file)
                    video_file_map.setdefault(file, set()).add(video_title)
            for file, video_titles in video_file_map.items():
                for video_title in video_titles:
                    if not self.wait_video_check(video_title):
                        logger.warning(f"视频 {video_title} 审核未通过")
                        continue
        if (cfg["插图数量"] and not specified_image_links) or cfg["是否存稿"]:
            page_home = context.new_page()
            self._login_and_get_token(page_home)

        if not self._build_result_table(base_dir, cfg["多篇合一"]):
            return

        last_main_article = ""
        lines = self.result_table_view[1:]
        total_count = len(lines)

        try:
            for index, line in enumerate(lines):
                if self.stop_event.is_set():
                    break
                self.pause_event.wait()

                if (line[4] != last_main_article or not cfg["多篇合一"]) and popup is not None:
                    popup.close()

                line[1] = "处理中"
                file = line[3]
                dir_name = os.path.dirname(file)
                file_name_without_ext, file_ext = os.path.splitext(os.path.basename(file))

                if file_ext not in ['.docx', '.doc', ".txt", ".html", ".md"]:
                    self.is_failed = True
                    line[1], line[2] = "失败", "仅支持docx、doc、txt、html、md文件"
                    continue

                try:
                    is_new_group = line[4] == "" or line[4] != last_main_article

                    if file_ext in [".docx", ".doc"]:
                        if is_new_group:
                            popup = self._open_new_article(page_home)
                        else:
                            self._add_article_to_popup(popup)
                        self.random_wait()
                        popup.locator("#js_import_file").click()
                        self.random_wait()
                        popup.locator(".import-file-dialog input[type=file]").set_input_files(file)
                        popup.get_by_text("已完成导入", exact=True).wait_for()
                    else:
                        file_content = self.read_file(file)
                        is_md_like = file_ext == ".md" or (file_ext == ".txt" and not any(tag in file_content for tag in ["<span", "<p", "<img"]))

                        if is_md_like:
                            if self.upload_image_client is None:
                                self.upload_image_client = self.page
                            template_dirs = self.get_article_template_dirs()
                            if not template_dirs:
                                logger.warning("没有找到模板文件")
                                line[1], line[2] = "失败", "没有找到模板文件"
                                return

                            file_content = self._prepare_md_content(
                                file_content, file, dir_name, cfg, specified_image_links,
                                template_dirs, topics)
                            if not cfg["是否存稿"]:
                                if 完成后移动:
                                    self.move_to_done(完成后移动, dir_name, file)
                                line[1] = "排版成功"
                                continue

                        if is_new_group:
                            popup = self._open_new_article(page_home)
                        else:
                            self._add_article_to_popup(popup)
                        self.random_wait()
                        self._paste_content(popup, file_content)

                    self.random_wait()

                    # 标题
                    h1 = popup.locator("#ueditor_0 div[contenteditable=true] h1").first
                    if h1.is_visible():
                        title = h1.inner_text()
                        h1.evaluate("element => element.remove()")
                    else:
                        title = file_name_without_ext.replace("改写_", "")
                    popup.get_by_placeholder("请在这里输入标题").fill(title[:64])

                    # 文章属性
                    try:
                        self._set_article_options(popup, cfg, video_file_map.get(file, set()))
                    except ValueError as e:
                        self.is_failed = True
                        logger.warning(str(e))
                        line[1], line[2] = "失败", str(e)
                        continue

                    # 保存草稿
                    is_last_in_group = cfg["多篇合一"] and (index == total_count - 1 or lines[index + 1][4] != line[4])

                    if not cfg["多篇合一"] or is_last_in_group:
                        if not self.save_draft(popup):
                            self.is_failed = True
                            line[1], line[2] = "可能失败,请手动检查", "未识别到保存草稿按钮"
                            continue
                        if cfg["多篇合一"]:
                            need_to_move_files = []
                            for l in lines:
                                if l[4] == line[4]:
                                    l[1] = "存稿成功"
                                    need_to_move_files.append(l[3])
                            if 完成后移动:
                                parent_dirs = set(os.path.dirname(f) for f in need_to_move_files)
                                if len(parent_dirs) == 1:
                                    if Path(dir_name).resolve() == Path(self.file_path).resolve():
                                        for f_to_move in need_to_move_files:
                                            shutil.move(f_to_move, 完成后移动)  # type: ignore
                                    else:
                                        shutil.move(dir_name, os.path.join(完成后移动, os.path.basename(dir_name)))  # type: ignore
                                else:
                                    grand_parent_dir = os.path.dirname(dir_name)
                                    if Path(grand_parent_dir).resolve() == Path(self.file_path).resolve():
                                        for f_to_move in need_to_move_files:
                                            parent_dir = os.path.dirname(f_to_move)
                                            shutil.move(parent_dir, os.path.join(完成后移动, os.path.basename(parent_dir)))  # type: ignore
                                    else:
                                        shutil.move(grand_parent_dir, os.path.join(完成后移动, os.path.basename(grand_parent_dir)))  # type: ignore
                        else:
                            line[1] = "存稿成功"
                            if 完成后移动:
                                self.move_to_done(完成后移动, dir_name, file)
                    else:
                        line[1] = "已编辑"
                except Exception as e:
                    self.is_failed = True
                    logger.exception(f"处理文件 {file} 失败: {e}")
                    line[1], line[2] = "失败", str(e)
                finally:
                    if line[4] != last_main_article:
                        last_main_article = line[4]
        finally:
            if 完成后移动:
                try:
                    os.rmdir(完成后移动)
                except OSError:
                    pass
            for p in (popup, page_home):
                if p is not None:
                    try:
                        p.close()
                    except Exception:
                        pass
            self.page.close()
