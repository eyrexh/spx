import yfinance as yf
import requests
import os

TICKER = "VFV"           
DROP_THRESHOLD = 0.05    
WEBHOOKS_ENV = os.environ.get("DISCORD_WEBHOOK", "")
DISCORD_WEBHOOKS = [url.strip() for url in WEBHOOKS_ENV.split(",") if url.strip()]

def check_stock_dip():
    stock = yf.Ticker(TICKER)
    hist = stock.history(period="1y")

    if hist.empty:
        print(f"未能获取到 {TICKER} 的数据")
        return

    current_price = hist['Close'].iloc[-1]
    
    # 将过去一年的最高收盘价定义为“最近的高点”
    recent_high = hist['Close'].max()
    
    # 计算回撤幅度
    drawdown = (recent_high - current_price) / recent_high

    print(f"{TICKER} 当前价格: ${current_price:.2f}")
    print(f"52周高点: ${recent_high:.2f}")
    print(f"当前回撤: {drawdown * 100:.2f}%")

    # 如果回撤达到或超过阈值，发送通知
    if drawdown >= DROP_THRESHOLD:
        msg = (
            f"📉 **定投加仓提醒: {TICKER}**\n"
            f"当前价格 `${current_price:.2f}` 已从近一年高点 `${recent_high:.2f}` "
            f"回撤了 **{drawdown * 100:.2f}%**！已达到 {DROP_THRESHOLD*100}% 的加仓线。"
        )
        send_discord_alert(msg)
    else:
        print("未达到加仓线，无需通知。")

def send_discord_alert(message):
    if not DISCORD_WEBHOOK:
        print("未配置 DISCORD_WEBHOOK 环境变量，跳过发送。")
        return
        
    response = requests.post(DISCORD_WEBHOOK, json={"content": message})
    if response.status_code == 204:
        print("Discord 提醒发送成功！")
    else:
        print(f"发送失败，状态码: {response.status_code}")

if __name__ == "__main__":
    check_stock_dip()
