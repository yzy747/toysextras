import os
from toys_extras.base import Base
from toys_utils import sanitize_filename
import pandas as pd

__version__ = '1.0.4'


class Toy(Base):

    标题列名 = '标题'
    内容列名 = '内容'

    def __init__(self):
        super().__init__()
        self.result_table_view: list = [['文件名', '状态', "txt文件"]]

    def play(self):
        一份txt一个文件夹 =True if self.config.get('扩展', "一份txt一个文件夹") == "是" else False
        for file in self.files:
            if not file.endswith('.xlsx'):
                continue
            dir_name = os.path.splitext(file)[0]
            article_dir = dir_name
            os.makedirs(dir_name, exist_ok=True)
            df = pd.read_excel(file)
            for i, row in df.iterrows():
                title = row[self.标题列名]
                if not title or pd.isna(title):
                    continue
                content = row[self.内容列名]
                if not content or pd.isna(content):
                    content = ''
                # 去除标题中的非法字符
                title = sanitize_filename(title)
                if 一份txt一个文件夹:
                    article_dir = os.path.join(dir_name, title)
                    os.makedirs(article_dir, exist_ok=True)
                file_name = os.path.join(article_dir, title + '.txt')
                with open(file_name, 'w', encoding='utf-8') as f:
                    f.write(content)
                self.result_table_view.append([file, '成功', file_name])