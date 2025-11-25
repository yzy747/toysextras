import os
from toys_utils import date_time
from toys_extras.base import Base
from toys_logger import logger

__version__ = "1.0.0"


class Toy(Base):

    def __init__(self):
        self.result_table_view: list = [['文件名', '状态', '存储路径']]

    def play(self):
        文件名称 = self.config.get("扩展", "文件名称")
        目标路径 = self.config.get("扩展", "目标路径")
        merge_contents = []
        for file in self.files:
            try:
                if not file.endswith(".txt"):
                    continue
                with open(file, "r", encoding="utf-8") as f:
                    paragraph = f.read().strip()
                merge_contents.append(paragraph)
                self.result_table_view.append([file, "成功", "文件读取成功"])
            except Exception as e:
                logger.exception(e, exc_info=True)
                self.result_table_view.append([file, "失败", "文件读取失败"])
                continue
        if not merge_contents:
            return
        merged_text = "\n\n".join(merge_contents)
        if not os.path.exists(目标路径):
            os.makedirs(目标路径, exist_ok=True)
        file_path = os.path.join(目标路径, 文件名称 if 文件名称 else date_time(fmt="%Y%m%d%H%M%S"))
        with open(f"{file_path}.txt", "w", encoding="utf-8") as f:
            f.write(merged_text)
