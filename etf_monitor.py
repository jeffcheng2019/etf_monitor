import os
import smtplib
from datetime import datetime, timedelta
from email.header import Header
from email.mime.text import MIMEText
import pandas as pd
import yfinance as yf

# ==================== 配置区域 ====================
RECEIVER_EMAIL = "pikko2025@qq.com"  # 接收结果的邮箱

# 精选全市场 300+ 只主流核心 ETF 监测池（上海.SS / 深圳.SZ）
ETF_WATCHLIST = {
    # --- 核心大宽基指数 ---
    "510300.SS": "沪深300ETF", "159919.SZ": "300ETF华夏", "510500.SS": "中证500ETF", "159605.SZ": "中证500ETF南方",
    "159915.SZ": "创业板ETF", "159949.SZ": "创业板50ETF", "588000.SS": "科创50ETF", "588080.SS": "科创板ETF易方达",
    "510050.SS": "上证50ETF", "512100.SS": "中证1000ETF", "159845.SZ": "中证1000ETF易方达", "563000.SS": "中国A50ETF",
    "159601.SZ": "A50ETF华夏", "512500.SS": "中证500ETF建信", "510210.SS": "上证指数ETF", "159922.SZ": "500ETF嘉实",
    "159607.SZ": "中证1000ETF广发", "159901.SZ": "深100ETF", "159902.SZ": "中小100ETF", "510180.SS": "上证180ETF",
    "588100.SS": "科创双创50ETF", "159781.SZ": "双创50ETF南方", "159782.SZ": "双创50ETF华夏", "159783.SZ": "双创50ETF易方达",
    "588200.SS": "科创100ETF", "588190.SS": "科创100ETF银华", "159588.SZ": "中证A50ETF", "560350.SS": "中证A50ETF摩根",
    
    # --- 跨境指数与全球核心商品 ---
    "513100.SS": "纳指ETF", "159941.SZ": "纳天方达", "513500.SS": "标普500ETF", "159655.SZ": "标普500ETF博时",
    "513050.SS": "恒生ETF", "159920.SZ": "恒生ETF南方", "513330.SS": "恒生科技ETF", "159740.SZ": "恒生科技ETF恒生",
    "513660.SS": "恒生科技龙头ETF", "513900.SS": "港股通恒生ETF", "513060.SS": "恒生医疗ETF", "159850.SZ": "恒生互联网ETF",
    "513090.SS": "中概互联网ETF", "159509.SZ": "纳斯达克100ETF", "513300.SS": "纳指100ETF华夏", "513880.SS": "高端制造港股ETF",
    "159711.SZ": "港股通科技ETF", "513180.SS": "恒生科技ETF华夏", "159980.SZ": "恒生红利ETF", "513600.SS": "恒生红利ETF华夏",
    "513260.SS": "恒生医疗龙头", "159751.SZ": "港股通医药ETF", "518880.SS": "黄金ETF", "159934.SZ": "黄金ETF南方",
    "159937.SZ": "黄金ETF博时", "518800.SS": "黄金基金ETF", "159981.SZ": "豆粕ETF", "159985.SZ": "有色期货ETF",

    # --- 半导体、芯片与人工智能 ---
    "512480.SS": "半导体ETF", "159995.SZ": "芯片ETF", "512760.SS": "芯片/半导体ETF国泰", "159813.SZ": "半导体芯片ETF",
    "159801.SZ": "芯片龙头ETF", "159732.SZ": "消费电子ETF", "515880.SS": "通信ETF", "159994.SZ": "5G中证ETF",
    "515050.SS": "5GETF", "159806.SZ": "云计算ETF", "516630.SS": "云计算ETF华夏", "515230.SS": "软件ETF",
    "159851.SZ": "软件龙头ETF", "159869.SZ": "游戏ETF", "516010.SS": "游戏动漫ETF", "159529.SZ": "人工智能ETF",
    "515980.SS": "人工智能ETF华夏", "562500.SS": "机器人ETF", "159770.SZ": "机器人ETF龙头", "159516.SZ": "AI人工智能ETF",

    # --- 新能源、光伏与汽车 ---
    "515790.SS": "光伏产业ETF", "159839.SZ": "光伏ETF", "516160.SS": "新能源ETF", "159875.SZ": "新能源汽车ETF",
    "159725.SZ": "电池ETF", "516390.SS": "新能源汽车ETF国泰", "159611.SZ": "电力ETF", "561600.SS": "智能汽车ETF",
    "515030.SS": "新能源车ETF", "159861.SZ": "碳中和ETF", "512580.SS": "环保ETF", "159852.SZ": "绿电ETF",
    "159755.SZ": "电池龙头ETF", "159757.SZ": "光伏龙头ETF",

    # --- 金融、券商与红利低波 ---
    "512880.SS": "证券ETF", "512000.SS": "券商ETF", "159939.SZ": "中证全指证券公司ETF", "159841.SZ": "证券龙头ETF",
    "512800.SS": "银行ETF", "515020.SS": "银行ETF天弘", "159887.SZ": "银行ETF富国", "510880.SS": "红利ETF",
    "512890.SS": "红利低波ETF", "515100.SS": "红利低波龙头ETF", "515450.SS": "红利低波ETF南方", "515080.SS": "中证红利ETF",
    "515900.SS": "红利低波ETF博时", "512510.SS": "中证红利个股ETF", "159747.SZ": "大湾区红利ETF", "159690.SZ": "红利低波100ETF", 
    "510650.SS": "金融ETF",

    # --- 大消费、白酒与医疗中药 ---
    "512690.SS": "酒ETF", "159928.SZ": "消费ETF", "513890.SS": "港股通消费ETF", "515650.SS": "消费TOP ETF",
    "515310.SS": "沪深300大消费ETF", "159996.SZ": "家电ETF", "159766.SZ": "旅游ETF", "159943.SZ": "食品饮料ETF",
    "512010.SS": "医药卫生ETF", "512170.SS": "医疗ETF", "159938.SZ": "医药ETF", "159849.SZ": "医疗器械ETF",
    "159795.SZ": "中药ETF", "561510.SS": "中药ETF华泰", "159647.SZ": "中药ETF鹏华", "159820.SZ": "医疗创新ETF",
    "159896.SZ": "创新药ETF", "515120.SS": "创新药ETF易方达", "512220.SS": "生物医药ETF",

    # --- 资源、基建与军工 ---
    "512660.SS": "军工ETF", "159929.SZ": "中证国防ETF", "512710.SS": "军工龙头ETF", "159804.SZ": "国防军工ETF",
    "512400.SS": "有色金属ETF", "159976.SZ": "有色ETF", "515220.SS": "煤炭ETF", "510410.SS": "资源ETF",
    "511220.SS": "城投债ETF", "512200.SS": "房地产ETF", "159768.SZ": "地产ETF", "516950.SS": "基建ETF",
    "515110.SS": "化工ETF", "159870.SZ": "化工ETF鹏华", "512980.SS": "传媒ETF", "159805.SZ": "传媒ETF广发",
    "159620.SZ": "基建50ETF", "516070.SS": "工业有色ETF",
}

def get_etf_data_and_analyze():
    print(f"🚀 开始同步雅虎财经数据，精选库共需扫描 {len(ETF_WATCHLIST)} 只ETF...")
    results = []
    start_date = (datetime.now() - timedelta(days=250)).strftime("%Y-%m-%d")

    for symbol, name in ETF_WATCHLIST.items():
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start_date, timeout=3)

            if df.empty or len(df) < 80:
                continue

            df = df.sort_index()

            # 计算核心趋势技术指标
            df["ma20"] = df["Close"].rolling(20).mean()
            df["ma60"] = df["Close"].rolling(60).mean()
            df["ret20"] = df["Close"] / df["Close"].shift(20) - 1
            df["ret60"] = df["Close"] / df["Close"].shift(60) - 1

            latest = df.iloc[-1]
            prev = df.iloc[-2]
            ma60_5days_ago = df.iloc[-6]["ma60"]

            close = latest["Close"]
            ma20 = latest["ma20"]
            ma60 = latest["ma60"]

            # 趋势过滤核心：MA60走平或向上 且 股价在MA60上方
            if not (ma60 >= ma60_5days_ago) or not (close > ma60):
                continue

            # 判断买点形态分类
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

            results.append({
                "代码": symbol.split(".")[0],
                "名称": name,
                "信号": signal,
                "收盘价": round(close, 3),
                "20日涨幅": round(latest["ret20"] * 100, 2),
                "60日涨幅": round(latest["ret60"] * 100, 2),
                "距20日线": round(distance_ma20 * 100, 2),
                "距60日线": round(distance_ma60 * 100, 2),
            })
            print(f"符合趋势条件: {name} ({symbol})")
        except Exception:
            continue

    return pd.DataFrame(results)

def run():
    result_df = get_etf_data_and_analyze()
    today_str = datetime.now().strftime("%Y-%m-%d")
    subject = f"📊 ETF全赛道趋势候选名单_{today_str}"

    if result_df.empty:
        msg = "今日精选主流名单中，没有满足MA20/60右侧大趋势的ETF。"
    else:
        signal_order = {"A类：强势趋势": 1, "B类：回调再起": 2, "C类：突破60日线": 3}
        result_df["信号排序"] = result_df["信号"].map(signal_order)
        result_df = result_df.sort_values(by=["信号排序", "60日涨幅", "20日涨幅"], ascending=[True, False, False])

        msg = "数据源：Yahoo Finance (纯趋势技术面版)\n"
        msg += "趋势条件：MA60走平或向上，收盘价站上MA60\n"
        msg += "=========================================\n\n"

        for _, r in result_df.iterrows():
            if r["距60日线"] > 25:
                risk = "高位谨慎"
            elif r["距60日线"] < 5:
                risk = "靠近60日线"
            else:
                risk = "正常"

            msg += (
                f"【{r['名称']} ({r['代码']})】\n"
                f"-> 信号分类：{r['信号']}\n"
                f"-> 今日收盘：{r['收盘价']}\n"
                f"-> 20日/60日涨幅：{r['20日涨幅']}% / {r['60日涨幅']}%\n"
                f"-> 距20日线/60日线：{r['距20日线']}% / {r['距60日线']}% ({risk})\n\n"
            )

    print("\n======= 📈 300+核心全赛道技术面扫描完毕 =======")
    print(msg)
    print("==============================================\n")
    send_email(subject, msg)

def send_email(subject, content):
    sender = os.environ.get("EMAIL_SENDER")
    password = os.environ.get("EMAIL_PASSWORD")

    if not sender or not password:
        print("未检测到发件箱 Secrets 配置，发送终止。")
        return

    message = MIMEText(content, "plain", "utf-8")
    message["From"] = sender
    message["To"] = RECEIVER_EMAIL
    message["Subject"] = Header(subject, "utf-8")

    try:
        server = smtplib.SMTP_SSL("smtp.qq.com", 465, timeout=15)
        server.login(sender, password)
        server.sendmail(sender, [RECEIVER_EMAIL], message.as_string())
        server.close()
        print("🎉 邮件成功送达！全技术面监控任务圆满结束。")
    except Exception as e:
        print(f"❌ 邮件因跨国网络连接最终失败: {e}")

if __name__ == "__main__":
    run()
