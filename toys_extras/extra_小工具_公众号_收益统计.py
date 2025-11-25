import os.path
from openpyxl import load_workbook
from toys_extras.base import Base
from toys_logger import logger
from toys_utils import WeChatAPI, ToyError
import pandas as pd


__version__ = "1.0.0"


class Toy(Base):

    def __init__(self):
        self.access_token = ""
        self.result_table_view: list = [['公众号', '状态', '错误信息']]

    def play(self):
        excel_files = [file for file in self.files if file.endswith(".xlsx")]
        if len(excel_files) != 1:
            logger.error("选择文件，并确保文件类型为.xlsx")
        account_pd = pd.read_excel(excel_files[0])
        columns = account_pd.columns
        if any(column not in columns for column in ['公众号名称', 'appid','secret']):
            logger.error("excel文件必须包含公众号名称、appid、secret三列")
            return
        has_proxy_col = "网络代理" in columns

        revenue_pd = pd.DataFrame(columns=['公众号名称', '累计收入',  '程序化广告收入(昨日)', '返佣商品总预计收入(昨日)'])
        for index, row in account_pd.iterrows():
            account = row['公众号名称']
            appid = row['appid'] if pd.notna(row['appid']) else ""
            secret = row['secret'] if pd.notna(row['secret']) else ""
            proxy = None
            # 判断account_pd是否有"网络代理"列,且网络代理不为空
            if has_proxy_col and pd.notna(row['网络代理']):
                proxy = {"http": row['网络代理'], "https": row['网络代理']}

            公众号已设置 = bool(appid and secret)
            wechat_api = WeChatAPI(appid, secret, proxy)
            if 公众号已设置:
                try:
                    wechat_api.set_access_token()
                except Exception as e:
                    self.result_table_view.append([account, "失败", str(e)])
                    logger.warning(f"获取access_token失败: {e}")
                    raise ToyError("登录公众号失败，请检查网络或代理")
                公众号已设置 = not wechat_api.access_token.startswith("登录公众号失败:")

            if 公众号已设置:
                total_revenue = wechat_api.publisher_stat()
                print(total_revenue)
                if "err_msg" in total_revenue:
                    self.result_table_view.append([account, "失败", total_revenue["err_msg"]])
                    continue
                revenue_all = int(total_revenue.get("revenue_all", 0)) / 100
                adpos_genera = wechat_api.publisher_stat("分广告位数据")
                if "err_msg" in adpos_genera:
                    self.result_table_view.append([account, "失败", adpos_genera["err_msg"]])
                    continue
                adpos_income = int(adpos_genera["summary"]["income"]) / 100
                cps_general = wechat_api.publisher_stat("返佣商品数据")
                if "err_msg" in cps_general:
                    self.result_table_view.append([account, "失败", cps_general["err_msg"]])
                    continue
                cps_income = int(cps_general["summary"]["total_commission"]) / 100
                revenue_pd.loc[index] = [account, revenue_all, adpos_income, cps_income]
                self.result_table_view.append([account, "成功", ""])
            else:
                self.result_table_view.append([account, "失败", "公众号未设置"])
        if revenue_pd.shape[0] > 0:
            filename = os.path.join(os.path.dirname(excel_files[0]), f"公众号收益统计{pd.Timestamp.now().strftime('%Y%m%d%H%M%S')}.xlsx")
            revenue_pd.to_excel(filename, index=False, sheet_name='Sheet1')
            workbook = load_workbook(filename)
            worksheet = workbook.active

            for column in worksheet.columns:
                column_letter = column[0].column_letter  # 获取列字母
                worksheet.column_dimensions[column_letter].width = 25

            workbook.save(filename)

