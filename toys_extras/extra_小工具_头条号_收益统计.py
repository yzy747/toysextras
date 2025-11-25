import os.path
import requests
from openpyxl import load_workbook
from toys_extras.base import Base
from toys_logger import logger
import pandas as pd


__version__ = "1.0.0"


class Toy(Base):

    def __init__(self):
        self.access_token = ""
        self.result_table_view: list = [['头条号', '状态', '错误信息']]

    def play(self):
        excel_files = [file for file in self.files if file.endswith(".xlsx")]
        if len(excel_files) != 1:
            logger.error("选择文件，并确保文件类型为.xlsx")
        account_pd = pd.read_excel(excel_files[0])
        columns = account_pd.columns
        if any(column not in columns for column in ['头条号名称', 'ck']):
            logger.error("excel文件必须包含头条号名称、ck两列")
            return
        revenue_pd = pd.DataFrame(columns=['头条号名称', '累计收益', '本月收益', '昨日收益'])
        URL = "https://mp.toutiao.com/pgc/mp/income/income_statement_abstract?only_mid_income=false&days=30&app_id=1231"
        USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0"
        for index, row in account_pd.iterrows():
            account = row['头条号名称']
            cookies_str = row['ck']
            headers = {
                "User-Agent": USER_AGENT,
                "Cookie": cookies_str
            }
            resp = requests.get(URL, headers=headers).json()
            code = resp.get("code")
            if code != 0:
                self.result_table_view.append([account, "失败", f"获取收益失败，错误信息：{resp.get('message')}"])
                continue

            total_revenue, month_revenue, yesterday_revenue = "", "", "数据未更新"
            for item in resp.get("data", []):
                if item.get("type") == "total_income":
                    total_revenue = item.get("total")
                if item.get("type") == "period_income":
                    if item.get("is_yesterday_income_ready"):
                        yesterday_revenue = item.get("lastday")
                if item.get("type") == "monthly_income":
                    month_revenue = item.get("total")
            revenue_pd.loc[index] = [account, total_revenue, month_revenue, yesterday_revenue]
            self.result_table_view.append([account, "成功", ""])

        if revenue_pd.shape[0] > 0:
            filename = os.path.join(os.path.dirname(excel_files[0]), f"头条号收益统计{pd.Timestamp.now().strftime('%Y%m%d%H%M%S')}.xlsx")
            revenue_pd.to_excel(filename, index=False, sheet_name='Sheet1')
            workbook = load_workbook(filename)
            worksheet = workbook.active

            for column in worksheet.columns:
                column_letter = column[0].column_letter  # 获取列字母
                worksheet.column_dimensions[column_letter].width = 25

            workbook.save(filename)

