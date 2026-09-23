import yfinance as yf
import requests
import os
import json
from datetime import datetime

# === 配置区 ===
# 用列表配置你要监控的所有标的。加股请加上 .TO 后缀
TICKERS = ["VOO", "XEQT.TO"] 
WEBHOOKS_ENV = os.environ.get("DISCORD_WEBHOOK", "")
DISCORD_WEBHOOKS = [url.strip() for url in WEBHOOKS_ENV.split(",") if url.strip()]
STATE_FILE = "alert_state.json"
COOLDOWN_DAYS = 7

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def check_stock_dip():
    # 读取整体状态
    all_states = load_state()
    state_changed = False

    for ticker in TICKERS:
        print(f"\n开始分析 {ticker} ...")
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1y")

        if hist.empty:
            print(f"未能获取到 {ticker} 的数据")
            continue

        current_price = hist['Close'].iloc[-1]
        recent_high = hist['Close'].max()
        drawdown = (recent_high - current_price) / recent_high
        
        # 已修复语法错误：完全移除了可能导致渲染 Bug 的特殊符号
        print(f"[{ticker}] 当前价格: ${current_price:.2f}, 52周高点: ${recent_high:.2f}, 回撤: {drawdown * 100:.2f}%")
        
        # 获取该 Ticker 的历史状态
        ticker_state = all_states.get(ticker, {"last_tier": 0, "last_date": "2000-01-01"})
        last_tier = ticker_state["last_tier"]
        last_date_str = ticker_state["last_date"]
        last_date = datetime.strptime(last_date_str, "%Y-%m-%d")
        days_since_last = (datetime.now() - last_date).days

        # 反弹重置逻辑
        if drawdown < 0.05:
            if last_tier > 0:
                ticker_state["last_tier"] = 0
                all_states[ticker] = ticker_state
                state_changed = True
                print(f"[{ticker}] 市场已反弹回 5% 以内，状态已重置。")
            else:
                print(f"[{ticker}] 未达到 5% 最低加仓线。")
            continue

        # 判断阶梯
        current_tier = 0
        action_msg = ""
        tier_label = ""
        
        if drawdown >= 0.20:
            current_tier = 20
            action_msg = "🚨 **清空备用现金池！** 建议加仓 300%"
            tier_label = "20%+"
        elif drawdown >= 0.15:
            current_tier = 15
            action_msg = "🔥 **重拳出击！** 建议加仓 200%"
            tier_label = "15% - 20%"
        elif drawdown >= 0.10:
            current_tier = 10
            action_msg = "💰 **标准加仓！** 建议加仓 100%"
            tier_label = "10% - 15%"
        elif drawdown >= 0.05:
            current_tier = 5
            action_msg = "🛒 **小幅加仓！** 建议加仓 50%"
            tier_label = "5% - 10%"

        # 冷却与发送逻辑
        should_alert = False
        if current_tier > last_tier:
            print(f"[{ticker}] 跌幅扩大，无视冷却期，立即提醒！")
            should_alert = True
        elif days_since_last >= COOLDOWN_DAYS:
            print(f"[{ticker}] 已过冷却期，触发再次提醒！")
            should_alert = True
        else:
            print(f"[{ticker}] 当前处于 {current_tier}% 档位，仍在 {COOLDOWN_DAYS} 天冷却期内，静音。")

        if should_alert:
            msg = (
                f"📉 **阶梯加仓提醒: {ticker}**\n"
                f"当前价格 `${current_price:.2f}` 已从近一年高点 `${recent_high:.2f}` "
                f"回撤了 **{drawdown * 100:.2f}%**！\n"
                f"👉 触发【{tier_label}】档位：{action_msg}"
            )
            send_discord_alert(msg)
            
            # 更新状态
            ticker_state["last_tier"] = current_tier
            ticker_state["last_date"] = datetime.now().strftime("%Y-%m-%d")
            all_states[ticker] = ticker_state
            state_changed = True

    # 如果有任何状态更新，统一保存到文件
    if state_changed:
        save_state(all_states)
        print("\n已保存所有状态更新。")

def send_discord_alert(message):
    if not DISCORD_WEBHOOKS:
        return
    for webhook in DISCORD_WEBHOOKS:
        requests.post(webhook, json={"content": message})

if __name__ == "__main__":
    check_stock_dip()
