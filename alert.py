import yfinance as yf
import requests
import os
import json
from datetime import datetime

# === 配置区 ===
TICKER = "VFV" # 或 VFV.TO
WEBHOOKS_ENV = os.environ.get("DISCORD_WEBHOOK", "")
DISCORD_WEBHOOKS = [url.strip() for url in WEBHOOKS_ENV.split(",") if url.strip()]
STATE_FILE = "alert_state.json"
COOLDOWN_DAYS = 7 # 冷却期天数

def load_state():
    """读取上次发送通知的状态"""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_tier": 0, "last_date": "2000-01-01"}

def save_state(tier):
    """保存当前状态到文件"""
    state = {
        "last_tier": tier,
        "last_date": datetime.now().strftime("%Y-%m-%d")
    }
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)
    print(f"已更新状态文件: 档位 {tier}%, 日期 {state['last_date']}")

def check_stock_dip():
    stock = yf.Ticker(TICKER)
    hist = stock.history(period="1y")

    if hist.empty:
        print(f"未能获取到 {TICKER} 的数据")
        return

    current_price = hist['Close'].iloc[-1]
    recent_high = hist['Close'].max()
    drawdown = (recent_high - current_price) / recent_high

    print(f"{TICKER} 当前价格: ${current_price:.2f}")
    print(f"52周高点: ${recent_high:.2f}")
    print(f"当前回撤: {drawdown * 100:.2f}%")

    # 载入上次通知的状态
    state = load_state()
    last_tier = state.get("last_tier", 0)
    last_date_str = state.get("last_date", "2000-01-01")
    last_date = datetime.strptime(last_date_str, "%Y-%m-%d")
    days_since_last = (datetime.now() - last_date).days

    # 如果市场反弹，脱离了加仓区，重置状态
    if drawdown < 0.05:
        if last_tier > 0:
            save_state(0)
            print("市场已反弹回 5% 以内，状态已重置。")
        else:
            print("未达到 5% 最低加仓线，无需通知。")
        return

    # 判断当前所处的阶梯 (数字越大跌得越狠)
    current_tier = 0
    action_msg = ""
    tier_label = ""
    
    if drawdown >= 0.20:
        current_tier = 20
        action_msg = "🚨 **清空备用现金池！** 建议加仓 300%"
        tier_label = "20%+"
    elif drawdown >= 0.15:
        current_tier = 15
        action_msg = "🔥 **大幅加仓！** 建议加仓 200%"
        tier_label = "15% - 20%"
    elif drawdown >= 0.10:
        current_tier = 10
        action_msg = "💰 **标准加仓！** 建议加仓 100%"
        tier_label = "10% - 15%"
    elif drawdown >= 0.05:
        current_tier = 5
        action_msg = "🛒 **小幅加仓！** 建议加仓 50%"
        tier_label = "5% - 10%"

    # 核心判断逻辑
    should_alert = False
    
    if current_tier > last_tier:
        print(f"跌幅扩大 (从 {last_tier}% 跌入 {current_tier}%)，无视冷却期，立即提醒！")
        should_alert = True
    elif days_since_last >= COOLDOWN_DAYS:
        print(f"已过 {COOLDOWN_DAYS} 天冷却期，触发再次提醒！")
        should_alert = True
    else:
        print(f"当前档位 {current_tier}%，距上次提醒过了 {days_since_last} 天 (冷却期 {COOLDOWN_DAYS} 天)，静音处理。")

    if should_alert:
        msg = (
            f"📉 **阶梯加仓提醒: {TICKER}**\n"
            f"当前价格 `${current_price:.2f}` 已从近一年高点 `${recent_high:.2f}` "
            f"回撤了 **{drawdown * 100:.2f}%**！\n"
            f"👉 触发【{tier_label}】档位：{action_msg}"
        )
        send_discord_alert(msg)
        save_state(current_tier) # 成功后记录到文件

def send_discord_alert(message):
    if not DISCORD_WEBHOOKS:
        print("未配置 DISCORD_WEBHOOK，跳过发送。")
        return
        
    for webhook in DISCORD_WEBHOOKS:
        requests.post(webhook, json={"content": message})

if __name__ == "__main__":
    check_stock_dip()
