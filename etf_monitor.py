import os
import smtplib
import time
from datetime import datetime, timedelta
from email.header import Header
from email.mime.text import MIMEText
import akshare as ak
import pandas as pd

# ==================== 配置区域 ====================
RECEIVER_EMAIL = "pikko2025@qq.com"  # 接收结果的邮箱

# 只排除债券和货币类ETF
BLACKLIST = ["债", "货币", "银华日利", "华宝添益"]

# 最近20日平均成交额门槛：1000万
MIN_AVG_AMOUNT_20 = 10_000_000


def get_etf_list():
    """获取ETF实时列表，并过滤黑名单"""
    try:
        df = ak.fund_etf_spot_em()
        df = df.rename(
            columns={
                "代码": "code",
                "名称": "name",
                "最新价": "price",
                "成交额": "amount",
            }
        )
        df = df[["code", "name", "price", "amount"]].copy()

        for word in BLACKLIST:
            df = df[~df["name"].str.contains(word, na=False)]
        return df
    except Exception as e:
        print(f"获取ETF列表失败: {e}")
        return pd.DataFrame()


def get_etf_hist(code, days=180):
    """获取ETF历史日线数据并计算指标"""
    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=days * 2)).strftime("%Y%m%d")

    try:
        df = ak.fund_etf_hist_em(
            symbol=code,
            period="daily",
            start_date=start,
            end_date=end,
            adjust="qfq",
        )
        if df.empty:
            return None

        df = df.rename(
            columns={
                "日期": "date",
                "开盘": "open",
                "收盘": "close",
                "最高": "high",
                "最低": "low",
                "成交额": "amount",
            }
        )

        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
        df = df.dropna(subset=["close", "amount"])
        df = df.sort_values("date")

        # 计算指标
        df["ma20"] = df["close"].rolling(20).mean()
        df["ma60"] = df["close"].rolling(60).mean()
        df["ret20"] = df["close"] / df["close"].shift(20) - 1
        df["ret60"] = df["close"] / df["close"].shift(60) - 1
        df["avg_amount20"] = df["amount"].rolling(20).mean()

        return df
    except Exception:
        return None


def classify_signal(hist):
    """趋势过滤 + 买点分类"""
    if hist is None or len(hist) < 80:
        return None

    latest = hist.iloc[-1]
    prev = hist.iloc[-2]
    ma60_5days_ago = hist.iloc[-6]["ma60"]

    close = latest["close"]
    ma20 = latest["ma20"]
    ma60 = latest["ma60"]

    if pd.isna(ma20) or pd.isna(ma60) or pd.isna(ma60_5days_ago):
        return None

    # 趋势过滤：MA60走平或向上 且 股价在MA60上方
    if not (latest["ma60"] >= ma60_5days_ago) or not (close > ma60):
        return None

    ma20_up = latest["ma20"] >= prev["ma20"]

    # A类：强势趋势型
    if close > ma20 > ma60 and ma20_up:
        return "A类：强势趋势"

    # B类：回调后重新站上20日线
    if ma20 > ma60 and prev["close"] < prev["ma20"] and close > ma20:
        return "B类：回调再起"

    # C类：刚突破60日线
    if prev["close"] < prev["ma60"] and close > ma60:
        return "C类：突破60日线"

    return None


def run():
    etfs = get_etf_list()
    if etfs.empty:
        send_email("今日ETF趋势筛选", "未能获取到ETF列表数据，请检查网络。")
        return

    results = []
    print(f"开始扫描全市场 {len(etfs)} 只ETF...")

    for idx, row in etfs.iterrows():
        code = row["code"]
        name = row["name"]

        # 适当降低频率，防止被服务器封IP
        if idx % 50 == 0 and idx > 0:
            time.sleep(1)

        hist = get_etf_hist(code)
        if hist is None or len(hist) < 80:
            continue

        latest = hist.iloc[-1]

        # 流动性过滤
        if (
            pd.isna(latest["avg_amount20"])
            or latest["avg_amount20"] < MIN_AVG_AMOUNT_20
        ):
            continue

        signal = classify_signal(hist)
        if signal is None:
            continue

        distance_ma60 = latest["close"] / latest["ma60"] - 1
        distance_ma20 = latest["close"] / latest["ma20"] - 1

        results.append(
            {
                "代码": code,
                "名称": name,
                "信号": signal,
                "收盘价": round(latest["close"], 3),
                "20日涨幅": round(latest["ret20"] * 100, 2),
                "60日涨幅": round(latest["ret60"] * 100, 2),
                "距20日线": round(distance_ma20 * 100, 2),
                "距60日线": round(distance_ma60 * 100, 2),
                "20日均成交额": round(latest["avg_amount20"] / 100000000, 2),
            }
        )

    result_df = pd.DataFrame(results)

    # 组装邮件内容
    today_str = datetime.now().strftime("%Y-%m-%d")
    subject = f"📊 ETF趋势候选名单_{today_str}"

    if result_df.empty:
        msg = "今日没有符合条件的ETF。"
    else:
        signal_order = {"A类：强势趋势": 1, "B类：回调再起": 2, "C类：突破60日线": 3}
        result_df["信号排序"] = result_df["信号"].map(signal_order)
        result_df = result_df.sort_values(
            by=["信号排序", "60日涨幅", "20日涨幅"],
            ascending=[True, False, False],
        )

        msg = "筛选条件：MA60走平或向上，收盘价站上MA60，20日均成交额大于1000万。\n\n"
        msg += "=========================================\n\n"

        for _, r in result_df.head(30).iterrows():
            if r["距60日线"] > 35:
                risk = "极高位，不追高"
            elif r["距60日线"] > 25:
                risk = "高位谨慎"
            elif r["距60日线"] < 5:
                risk = "靠近60日线"
            else:
                risk = "正常"

            msg += (
                f"【{r['名称']} ({r['代码']})】\n"
                f"-> 信号：{r['信号']}\n"
                f"-> 收盘价：{r['收盘价']}\n"
                f"-> 20日涨幅/60日涨幅：{r['20日涨幅']}% / {r['60日涨幅']}%\n"
                f"-> 距20日线/60日线：{r['距20日线']}% / {r['距60日线']}% ({risk})\n"
                f"-> 20日均成交额：{r['20日均成交额']}亿\n\n"
            )

    send_email(subject, msg)


def send_email(subject, content):
    """
    通过系统的环境变量读取发件箱配置并发送邮件
    """
    # 从GitHub的环境变量中读取敏感信息，防止代码泄露密码
    sender = os.environ.get("EMAIL_SENDER")  # 发件人邮箱
    password = os.environ.get("EMAIL_PASSWORD")  # 发件人邮箱授权码

    if not sender or not password:
        print("未检测到发件箱环境变量配置，邮件发送跳过。本地打印结果：")
        print(content)
        return

    # QQ邮箱的SMTP服务器配置
    smtp_server = "smtp.qq.com"
    port = 465

    message = MIMEText(content, "plain", "utf-8")
    message["From"] = Header(f"ETF Monitor <{sender}>", "utf-8")
    message["To"] = Header(RECEIVER_EMAIL, "utf-8")
    message["Subject"] = Header(subject, "utf-8")

    try:
        server = smtplib.SMTP_SSL(smtp_server, port)
        server.login(sender, password)
        server.sendmail(sender, [RECEIVER_EMAIL], message.as_string())
        server.close()
        print("邮件发送成功！")
    except Exception as e:
        print(f"邮件发送失败: {e}")


if __name__ == "__main__":
    run()