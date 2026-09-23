import yfinance as yf
import requests
import os
import json
import math
from datetime import datetime

# === 配置区 ===
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
    all_states = load_state()
    state_changed = False

    for ticker in TICKERS:
        print(f"\n开始分析 {ticker} ...")
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1y")

        # 【防御 1】剔除 Yahoo Finance 返回的 NaN 无效数据
        hist = hist.dropna(subset=['Close'])

        if hist.empty:
            print(f"未能获取到 {ticker} 的有效数据，跳过。")
            continue

        current_price = hist['Close'].iloc[-1]
        recent_high = hist['Close'].max()
        drawdown = (recent_high - current_price) / recent_high

        # 【防御 2】如果极端情况下依然算出了 NaN，直接跳过
        if math.isnan(drawdown):
            print(f"[{ticker}] 计算结果异常 (NaN)，跳过。")
            continue
        
        print(f"[{ticker}] 当前价格: ${current_price:.2f}, 52周高点: ${recent_high:.2f}, 回撤: {drawdown * 100:.2f}%")
        
        ticker_state = all_states.get(ticker, {"last_tier": 0, "last_date": "2000-01-01"})
        last_tier = ticker_state["last_tier"]
        last_date_str = ticker_state["last_date"]
        last_date = datetime.strptime(last_date_str, "%Y-%m-%d")
        days_since_last = (datetime.now() - last_date).days

        if drawdown < 0.05:
            if last_tier > 0:
                ticker_state["last_tier"] = 0
                all_states[ticker] = ticker_state
                state_changed = True
                print(f"[{ticker}] 市场已反弹回 5% 以内，状态已重置。")
            else:
                print(f"[{ticker}] 未达到 5% 最低加仓线。")
            continue

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

        should_alert = False
        
        # 【防御 3】必须真正触发了某个档位，才允许发送通知
        if current_tier > 0:
            if current_tier > last_tier:
                print(f"[{ticker}] 跌幅扩大，无视冷却期，立即提醒！")
                should_alert = True
            elif days_since_last >= COOLDOWN_DAYS:
                print(f"[{ticker}] 已过冷却期，触发再次提醒！")
                should_alert = True
            else:
                print(f"[{ticker}] 当前处于 {current_tier}% 档位，仍在 {COOLDOWN_DAYS} 天冷却期内，静音。")

        if should_alert:
            my_discord_id = "947719513447735346"
            msg = (
                f"<@{my_discord_id}> 📉 **阶梯加仓提醒: {ticker}**\n"
                f"当前价格 `${current_price:.2f}` 已从近一年高点 `${recent_high:.2f}` "
                f"回撤了 **{drawdown * 100:.2f}%**！\n"
                f"👉 触发【{tier_label}】档位：{action_msg}"
            )
            send_discord_alert(msg)
            
            ticker_state["last_tier"] = current_tier
            ticker_state["last_date"] = datetime.now().strftime("%Y-%m-%d")
            all_states[ticker] = ticker_state
            state_changed = True

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
