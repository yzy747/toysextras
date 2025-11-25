import os
from toys_extras.base import Base
from toys_utils import sanitize_filename

__version__ = '1.0.5'


class Toy(Base):

    def __init__(self):
        super().__init__()
        self.result_table_view: list = [['文件', '状态']]

    @staticmethod
    def rename(path, file_name, new_name, file_type):
        if "\n" in new_name:
            return False
        new_name = new_name + '.' + file_type
        for file in os.listdir(path):
            if file.startswith(file_name) and file.endswith(file_type):
                os.rename(os.path.join(path, file), os.path.join(path, new_name))
                return True
        return False

    def play(self):
        txt汇总目录 = self.config.get("扩展", "txt汇总目录")
        markdown汇总目录 = self.config.get("扩展", "markdown汇总目录")
        word汇总目录 = self.config.get("扩展", "word汇总目录")
        for file in self.files:
            if file.endswith('.txt') and "改写_标题_" in file:
                file_name = os.path.basename(file).rsplit('.', maxsplit=1)[0].replace('改写_标题_', '')
                try:
                    with open(file, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        content = sanitize_filename(content)
                    txt_status, markdown_status, word_status = '失败', '失败', '失败'
                    file_path = os.path.dirname(file)
                    txt_file_name = file_name
                    if txt汇总目录 == "":
                        txt汇总目录 = file_path
                        txt_file_name = "改写_" + file_name
                    if markdown汇总目录 == "":
                        markdown汇总目录 = file_path
                    if word汇总目录 == "":
                        word汇总目录 = file_path
                    if self.rename(txt汇总目录, txt_file_name, content, file_type='txt'):
                        txt_status = '成功'
                    if self.rename(markdown汇总目录, file_name, content, file_type='md'):
                        markdown_status = '成功'
                    if self.rename(word汇总目录, file_name, content, file_type='docx'):
                        word_status = '成功'
                    self.result_table_view.append([file_name, f"txt:{txt_status}, markdown:{markdown_status}, word:{word_status}"])
                except Exception as e:
                    self.result_table_view.append([file_name, f"失败: {e}"])

