import akshare as ak
import pandas as pd
import requests
from datetime import datetime, timedelta

# 企业微信机器人 Webhook
WECHAT_WEBHOOK = ""

# 只排除债券和货币类ETF
# “债”可以覆盖国债、政金债、信用债、可转债等
# “货币”覆盖货币ETF
BLACKLIST = [
    "债",
    "货币",
    "银华日利",
    "华宝添益"
]

# 最近20日平均成交额门槛：1000万
MIN_AVG_AMOUNT_20 = 10_000_000


def get_etf_list():
    """
    获取ETF实时列表。
    保留跨境ETF、商品ETF、黄金ETF、港股ETF、美股ETF等。
    只排除债券和货币类ETF。
    """
    df = ak.fund_etf_spot_em()

    df = df.rename(columns={
        "代码": "code",
        "名称": "name",
        "最新价": "price",
        "成交额": "amount"
    })

    df = df[["code", "name", "price", "amount"]].copy()

    for word in BLACKLIST:
        df = df[~df["name"].str.contains(word, na=False)]

    return df


def get_etf_hist(code, days=180):
    """
    获取ETF历史日线数据，并计算MA20、MA60、20日涨幅、60日涨幅、20日平均成交额。
    """
    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=days * 2)).strftime("%Y%m%d")

    df = ak.fund_etf_hist_em(
        symbol=code,
        period="daily",
        start_date=start,
        end_date=end,
        adjust="qfq"
    )

    if df.empty:
        return None

    df = df.rename(columns={
        "日期": "date",
        "开盘": "open",
        "收盘": "close",
        "最高": "high",
        "最低": "low",
        "成交额": "amount"
    })

    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")

    df = df.dropna(subset=["close", "amount"])
    df = df.sort_values("date")

    df["ma20"] = df["close"].rolling(20).mean()
    df["ma60"] = df["close"].rolling(60).mean()

    df["ret20"] = df["close"] / df["close"].shift(20) - 1
    df["ret60"] = df["close"] / df["close"].shift(60) - 1

    df["avg_amount20"] = df["amount"].rolling(20).mean()

    return df


def classify_signal(hist):
    """
    趋势过滤 + 买点分类。

    趋势过滤条件：
    1. MA60今日 >= MA60前5日
    2. ETF收盘价 > MA60

    买点分类：
    A类：强势趋势
    B类：回调再起
    C类：突破60日线
    """
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

    # 你的新趋势过滤条件
    ma60_up_or_flat = latest["ma60"] >= ma60_5days_ago
    price_above_ma60 = close > ma60

    if not ma60_up_or_flat:
        return None

    if not price_above_ma60:
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
    results = []

    for _, row in etfs.iterrows():
        code = row["code"]
        name = row["name"]

        try:
            hist = get_etf_hist(code)

            if hist is None or len(hist) < 80:
                continue

            latest = hist.iloc[-1]

            # 流动性过滤：最近20日平均成交额 > 1000万
            if pd.isna(latest["avg_amount20"]):
                continue

            if latest["avg_amount20"] < MIN_AVG_AMOUNT_20:
                continue

            signal = classify_signal(hist)

            if signal is None:
                continue

            distance_ma60 = latest["close"] / latest["ma60"] - 1
            distance_ma20 = latest["close"] / latest["ma20"] - 1

            results.append({
                "代码": code,
                "名称": name,
                "信号": signal,
                "收盘价": round(latest["close"], 3),
                "20日涨幅": round(latest["ret20"] * 100, 2),
                "60日涨幅": round(latest["ret60"] * 100, 2),
                "距20日线": round(distance_ma20 * 100, 2),
                "距60日线": round(distance_ma60 * 100, 2),
                "20日均成交额": round(latest["avg_amount20"] / 100000000, 2)
            })

        except Exception as e:
            print(f"{code} {name} error: {e}")

    result_df = pd.DataFrame(results)

    if result_df.empty:
        msg = "今日没有符合条件的ETF。"
    else:
        # 信号优先级排序
        signal_order = {
            "A类：强势趋势": 1,
            "B类：回调再起": 2,
            "C类：突破60日线": 3
        }

        result_df["信号排序"] = result_df["信号"].map(signal_order)

        result_df = result_df.sort_values(
            by=["信号排序", "60日涨幅", "20日涨幅"],
            ascending=[True, False, False]
        )

        msg = "## 今日ETF趋势候选名单\n\n"
        msg += "筛选条件：MA60走平或向上，收盘价站上MA60，20日均成交额大于1000万。\n\n"

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
                f"**{r['名称']}（{r['代码']}）**\n"
                f"> 信号：{r['信号']}\n"
                f"> 收盘价：{r['收盘价']}\n"
                f"> 20日涨幅：{r['20日涨幅']}%\n"
                f"> 60日涨幅：{r['60日涨幅']}%\n"
                f"> 距20日线：{r['距20日线']}%\n"
                f"> 距60日线：{r['距60日线']}%｜{risk}\n"
                f"> 20日均成交额：{r['20日均成交额']}亿\n\n"
            )

    send_wechat(msg)


def send_wechat(content):
    """
    企业微信机器人推送。
    """
    if not WECHAT_WEBHOOK:
        print(content)
        return

    data = {
        "msgtype": "markdown",
        "markdown": {
            "content": content
        }
    }

    response = requests.post(WECHAT_WEBHOOK, json=data, timeout=10)

    if response.status_code != 200:
        print("推送失败：", response.text)


if __name__ == "__main__":
    run()