import os
import smtplib
from datetime import datetime, timedelta
from email.header import Header
from email.mime.text import MIMEText
import pandas as pd
import yfinance as yf

# ==================== 配置区域 ====================
RECEIVER_EMAIL = "pikko2025@qq.com"  # 接收结果的邮箱

# 预设全市场流动性最强、最具代表性的核心 ETF 监测名单（雅虎财经格式）
# 上海加 .SS，深圳加 .SZ
ETF_WATCHLIST = {
    "510300.SS": "沪深300ETF",
    "510500.SS": "中证500ETF",
    "159915.SZ": "创业板ETF",
    "588000.SS": "科创50ETF",
    "510050.SS": "上证50ETF",
    "159949.SZ": "创业板50ETF",
    "512100.SS": "中证1000ETF",
    "159845.SZ": "中证1000ETF易方达",
    "510880.SS": "红利ETF",
    "513100.SS": "纳指ETF",
    "159941.SZ": "纳天方达",
    "513500.SS": "标普500ETF",
    "513050.SS": "恒生ETF",
    "159920.SZ": "恒生ETF南方",
    "512880.SS": "证券ETF",
    "512000.SS": "券商ETF",
    "512800.SS": "银行ETF",
    "512660.SS": "军工ETF",
    "159939.SZ": "中证全指证券公司ETF",
    "515000.SS": "科技ETF",
    "512480.SS": "半导体ETF",
    "159995.SZ": "芯片ETF",
    "512010.SS": "医药卫生ETF",
    "512170.SS": "医疗ETF",
    "159938.SZ": "医药ETF",
    "515710.SS": "食品饮料ETF",
    "159928.SZ": "消费ETF",
    "510650.SS": "金融ETF",
    "512400.SS": "有色金属ETF",
    "512890.SS": "红利低波ETF",
    "515180.SS": "红利100ETF",
    "518880.SS": "黄金ETF",
    "159934.SZ": "黄金ETF南方",
    "513330.SS": "恒生科技ETF",
    "159740.SZ": "恒生科技ETF恒生",
    "513060.SS": "恒生医疗ETF",
    "511220.SS": "城投债ETF",
    "159839.SZ": "光伏ETF",
    "516160.SS": "新能源ETF",
    "159875.SZ": "消费者ETF",
    "159996.SZ": "家电ETF",
    "515050.SS": "5GETF",
    "513900.SS": "港股通恒生ETF",
    "513660.SS": "恒生科技龙头ETF",
    "159605.SZ": "中证500ETF南方",
    "159607.SZ": "中证1000ETF广发",
    "563000.SS": "中国A50ETF",
    "159601.SZ": "A50ETF华夏",
}


def get_etf_data_and_analyze():
    print(f"开始同步雅虎财经数据，共需扫描 {len(ETF_WATCHLIST)} 只核心ETF...")
    results = []

    # 计算历史时间窗口
    start_date = (datetime.now() - timedelta(days=250)).strftime("%Y-%m-%d")

    # 循环分析每一只ETF
    for symbol, name in ETF_WATCHLIST.items():
        try:
            # 使用 yfinance 抓取数据，设定 5 秒超时
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start_date, timeout=5)

            if df.empty or len(df) < 80:
                continue

            df = df.sort_index()

            # 计算趋势指标
            df["ma20"] = df["Close"].rolling(20).mean()
            df["ma60"] = df["Close"].rolling(60).mean()
            df["ret20"] = df["Close"] / df["Close"].shift(20) - 1
            df["ret60"] = df["Close"] / df["Close"].shift(60) - 1
            df["avg_amount20"] = (df["Close"] * df["Volume"]).rolling(20).mean()

            latest = df.iloc[-1]
            prev = df.iloc[-2]
            ma60_5days_ago = df.iloc[-6]["ma60"]

            close = latest["Close"]
            ma20 = latest["ma20"]
            ma60 = latest["ma60"]

            # 趋势过滤核心：MA60走平或向上 且 股价在MA60上方
            if not (ma60 >= ma60_5days_ago) or not (close > ma60):
                continue

            # 判断买点分类
            ma20_up = ma20 >= prev["ma20"]
            signal = None

            if close > ma20 > ma60 and ma20_up:
                signal = "A类：强势趋势"
            elif ma20 > ma60 and prev["Close"] < prev["ma20"] and close > ma20:
                signal = "B类：回调再起"
            elif prev["Close"] < prev["ma60"] and close > ma60:
                signal = "C类：突破60日线"

            if not signal:
                continue

            distance_ma60 = close / ma60 - 1
            distance_ma20 = close / ma20 - 1

            results.append(
                {
                    "代码": symbol.split(".")[0],
                    "名称": name,
                    "信号": signal,
                    "收盘价": round(close, 3),
                    "20日涨幅": round(latest["ret20"] * 100, 2),
                    "60日涨幅": round(latest["ret60"] * 100, 2),
                    "距20日线": round(distance_ma20 * 100, 2),
                    "距60日线": round(distance_ma60 * 100, 2),
                    "20日均成交额": round(latest["avg_amount20"] / 100000000, 2),
                }
            )
            print(f"✅ {name} ({symbol}) 分析完毕，符合趋势条件。")
        except Exception as e:
            print(f"⚠️ 跳过 {name} ({symbol})，原因: {e}")
            continue

    return pd.DataFrame(results)


def run():
    result_df = get_etf_data_and_analyze()

    today_str = datetime.now().strftime("%Y-%m-%d")
    subject = f"📊 国际数据源_ETF趋势候选名单_{today_str}"

    if result_df.empty:
        msg = "今日核心监测名单中没有符合趋势条件的ETF。"
    else:
        signal_order = {"A类：强势趋势": 1, "B类：回调再起": 2, "C类：突破60日线": 3}
        result_df["信号排序"] = result_df["信号"].map(signal_order)
        result_df = result_df.sort_values(
            by=["信号排序", "60日涨幅", "20日涨幅"],
            ascending=[True, False, False],
        )

        msg = "数据源：Yahoo Finance (海外节点)\n"
        msg += "筛选条件：MA60走平或向上，收盘价站上MA60。\n\n"
        msg += "=========================================\n\n"

        for _, r in result_df.iterrows():
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
                f"-> 距20日线/60日线：{r['距20日线']}% / {r['距60日线']}% ({risk})\n\n"
            )

    print("\n======= 📈 选股扫描完毕，本地日志备份 =======")
    print(msg)
    print("==============================================\n")

    send_email(subject, msg)


def send_email(subject, content):
    sender = os.environ.get("EMAIL_SENDER")
    password = os.environ.get("EMAIL_PASSWORD")

    if not sender or not password:
        print("未检测到发件箱 Secrets 配置，发送终止。")
        return

    print("正在通过 465 SSL 端口向 QQ 邮箱投递结果...")
    message = MIMEText(content, "plain", "utf-8")
    message["From"] = Header(f"ETF Monitor <{sender}>", "utf-8")
    message["To"] = Header(RECEIVER_EMAIL, "utf-8")
    message["Subject"] = Header(subject, "utf-8")

    try:
        server = smtplib.SMTP_SSL("smtp.qq.com", 465, timeout=15)
        server.login(sender, password)
        server.sendmail(sender, [RECEIVER_EMAIL], message.as_string())
        server.close()
        print("🎉 邮件成功送达！")
    except Exception as e:
        print(f"❌ 邮件因跨国网络连接最终失败: {e}")


if __name__ == "__main__":
    run()
