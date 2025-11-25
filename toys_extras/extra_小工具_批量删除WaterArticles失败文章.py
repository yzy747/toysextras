import os
from toys_extras.base import Base
import shutil

__version__ = '1.0.1'


class Toy(Base):

    def __init__(self):
        super().__init__()
        self.result_table_view: list = [['文件', '状态']]

    def play(self):
        processed_dirs = []
        for file in self.files:
            dir_path, file_name = os.path.split(file)
            if dir_path in processed_dirs:
                continue
            processed_dirs.append(dir_path)
            counter = 0
            has_title_rewritten = False
            for f in os.listdir(dir_path):
                if f.endswith(("txt", "md", 'docx')):
                    counter += 1
                    if f.startswith("改写_标题_") and f.endswith(("txt")):
                        has_title_rewritten = True

            should_delete = False
            if counter <= 1:
                should_delete = True

            elif counter == 2 and has_title_rewritten:
                should_delete = True

            if should_delete:
                try:
                    shutil.rmtree(dir_path)
                    self.result_table_view.append([dir_path, '删除成功'])
                except Exception as e:
                    self.is_failed = True
                    self.result_table_view.append([dir_path, f'删除失败: {str(e)}'])
