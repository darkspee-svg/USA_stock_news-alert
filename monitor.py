#!/usr/bin/env python3
"""
특정 종목 뉴스 알림 봇 (Finnhub -> Telegram)

동작:
  1) config.json의 관심 종목에 대해 Finnhub company-news API를 조회
  2) 처음 보는 기사만 Telegram으로 푸시
  3) 이미 본 기사 id는 state.json에 저장하여 중복 알림 방지
  4) 어떤 종목을 '처음' 조회할 때는 기존 기사를 알림 없이 seeding만 함
     (오래된 뉴스가 한꺼번에 쏟아지는 것을 방지)

환경변수(=GitHub Secrets):
  FINNHUB_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent
CONFIG_PATH = BASE / "config.json"
STATE_PATH = BASE / "state.json"

FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "").strip()
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

FINNHUB_URL = "https://finnhub.io/api/v1/company-news"
TELEGRAM_URL = "https://api.telegram.org/bot{token}/sendMessage"

LOOKBACK_DAYS = 3          # 며칠치 뉴스를 조회할지
MAX_IDS_PER_TICKER = 800   # state.json 무한정 커지는 것 방지


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_state():
    if STATE_PATH.exists():
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def fetch_news(symbol):
    today = datetime.now(timezone.utc).date()
    frm = today - timedelta(days=LOOKBACK_DAYS)
    params = {
        "symbol": symbol,
        "from": frm.isoformat(),
        "to": today.isoformat(),
        "token": FINNHUB_API_KEY,
    }
    r = requests.get(FINNHUB_URL, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, list):
        print(f"[{symbol}] 예상치 못한 응답: {data}")
        return []
    return data


def keyword_match(item, keywords):
    """keywords가 비어 있으면 모든 기사 통과. 아니면 제목/요약에 키워드 포함 시 통과."""
    if not keywords:
        return True
    text = (item.get("headline", "") + " " + item.get("summary", "")).lower()
    return any(k.lower() in text for k in keywords)


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def format_message(symbol, item):
    headline = item.get("headline", "(제목 없음)")
    source = item.get("source", "")
    url = item.get("url", "")
    ts = item.get("datetime")
    when = ""
    if ts:
        when = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [f"📢 <b>${esc(symbol)}</b> 뉴스", f"<b>{esc(headline)}</b>"]
    meta = " · ".join(x for x in [esc(source), when] if x)
    if meta:
        lines.append(meta)
    if url:
        lines.append(esc(url))
    return "\n".join(lines)


def send_telegram(text):
    url = TELEGRAM_URL.format(token=TELEGRAM_BOT_TOKEN)
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    r = requests.post(url, json=payload, timeout=30)
    if r.status_code != 200:
        print(f"Telegram 전송 실패: {r.status_code} {r.text}")
    r.raise_for_status()


def main():
    missing = [
        name for name, val in [
            ("FINNHUB_API_KEY", FINNHUB_API_KEY),
            ("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN),
            ("TELEGRAM_CHAT_ID", TELEGRAM_CHAT_ID),
        ] if not val
    ]
    if missing:
        print("환경변수 누락:", ", ".join(missing))
        sys.exit(1)

    config = load_config()
    tickers = [t.strip().upper() for t in config.get("tickers", []) if t.strip()]
    keywords = config.get("keywords", [])
    state = load_state()

    if not tickers:
        print("config.json의 tickers가 비어 있습니다.")
        return

    total_sent = 0
    for symbol in tickers:
        prev_ids = state.get(symbol, [])
        seen = set(prev_ids)
        first_run = len(prev_ids) == 0

        try:
            news = fetch_news(symbol)
        except Exception as e:
            print(f"[{symbol}] 조회 실패, 건너뜀: {e}")
            continue

        # 오래된 기사부터 알림이 가도록 시간 오름차순 정렬
        news.sort(key=lambda x: x.get("datetime", 0))

        newly_seen = []  # 이번 실행에서 '본 것'으로 저장할 id
        seeded = 0
        for item in news:
            nid = str(item.get("id"))
            if not nid or nid in seen or nid in newly_seen:
                continue

            # 첫 실행: 알림 없이 seeding만
            if first_run:
                newly_seen.append(nid)
                seeded += 1
                continue

            # 키워드 필터 미통과: 본 것으로만 처리(재검사 방지)
            if not keyword_match(item, keywords):
                newly_seen.append(nid)
                continue

            # 알림 발송 성공 시에만 seen 처리(실패하면 다음 실행에서 재시도)
            try:
                send_telegram(format_message(symbol, item))
            except Exception as e:
                print(f"[{symbol}] 전송 실패(다음 실행 재시도): {e}")
                continue
            newly_seen.append(nid)
            total_sent += 1
            time.sleep(1)  # Telegram rate limit 여유

        if first_run:
            print(f"[{symbol}] 첫 실행 seeding {seeded}건 (알림 미발송)")

        state[symbol] = (prev_ids + newly_seen)[-MAX_IDS_PER_TICKER:]

    save_state(state)
    print(f"완료: 총 {total_sent}건 전송")


if __name__ == "__main__":
    main()
