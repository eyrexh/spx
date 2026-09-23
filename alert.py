import yfinance as yf
import requests
import os

# 建议改为 "VFV.TO" 如果你买的是加股 TSX 上的 VFV
TICKER = "VFV"            
WEBHOOKS_ENV = os.environ.get("DISCORD_WEBHOOK", "")
DISCORD_WEBHOOKS = [url.strip() for url in WEBHOOKS_ENV.split(",") if url.strip()]

def check_stock_dip():
    stock = yf.Ticker(TICKER)
    hist = stock.history(period="1y")

    if hist.empty:
        print(f"未能获取到 {TICKER} 的数据，请检查 Ticker 是否需要加后缀 (如 VFV.TO)")
        return

    current_price = hist['Close'].iloc[-1]
    
    # 将过去一年的最高收盘价定义为“最近的高点”
    recent_high = hist['Close'].max()
    
    # 计算回撤幅度
    drawdown = (recent_high - current_price) / recent_high

    print(f"{TICKER} 当前价格: ${current_price:.2f}")
    print(f"52周高点: ${recent_high:.2f}")
    print(f"当前回撤: {drawdown * 100:.2f}%")

    # 判断回撤属于哪个阶梯 (从大到小判断)
    action_msg = ""
    tier = ""
    
    if drawdown >= 0.20:
        action_msg = "🚨 **清空备用现金池！** 建议加仓平时定投额的 **300%**"
        tier = "20%+"
    elif drawdown >= 0.15:
        action_msg = "🔥 **重拳出击！** 建议加仓平时定投额的 **200%**"
        tier = "15% - 20%"
    elif drawdown >= 0.10:
        action_msg = "💰 **标准加仓！** 建议加仓平时定投额的 **100%**"
        tier = "10% - 15%"
    elif drawdown >= 0.05:
        action_msg = "🛒 **小幅加仓！** 建议加仓平时定投额的 **50%**"
        tier = "5% - 10%"

    # 如果触发了任何一档，发送通知
    if action_msg:
        msg = (
            f"📉 **阶梯加仓提醒: {TICKER}**\n"
            f"当前价格 `${current_price:.2f}` 已从近一年高点 `${recent_high:.2f}` "
            f"回撤了 **{drawdown * 100:.2f}%**！\n"
            f"👉 触发【{tier}】档位：{action_msg}"
        )
        send_discord_alert(msg)
    else:
        print("未达到 5% 最低加仓线，无需通知。")

def send_discord_alert(message):
    if not DISCORD_WEBHOOKS:
        print("未配置 DISCORD_WEBHOOK 环境变量，跳过发送。")
        return
        
    # 支持发送到多个 Webhook
    for webhook in DISCORD_WEBHOOKS:
        response = requests.post(webhook, json={"content": message})
        if response.status_code == 204:
            print("Discord 提醒发送成功！")
        else:
            print(f"发送失败，状态码: {response.status_code}")

if __name__ == "__main__":
    check_stock_dip()
