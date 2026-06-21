# 종목 뉴스 알림 봇 (Finnhub → Telegram, GitHub Actions 무료 호스팅)

관심 종목에 새 뉴스가 뜨면 텔레그램으로 즉시 푸시합니다. 서버 없이
GitHub Actions에서 15분마다 자동 실행됩니다.

```
Finnhub company-news 조회  →  신규 기사만 추림(state.json)  →  Telegram 푸시
        ↑ 15분마다 GitHub Actions가 자동 실행
```

---

## 준비물 3가지 (모두 무료)

### 1) Telegram 봇 토큰 + chat_id

1. 텔레그램에서 **@BotFather** 검색 → `/newbot` → 안내대로 진행 → **봇 토큰** 발급
   (형식: `123456789:AAH...`)
2. 방금 만든 내 봇과의 채팅창을 열어 아무 메시지나 한 번 보냅니다.
3. **chat_id** 얻기: 브라우저 주소창에 아래 주소 입력(토큰만 본인 것으로 교체)
   ```
   https://api.telegram.org/bot<봇토큰>/getUpdates
   ```
   응답 JSON에서 `"chat":{"id": 숫자 ...}` 의 **숫자가 chat_id** 입니다.
   (또는 텔레그램에서 **@userinfobot** 에게 말 걸면 본인 id를 알려줍니다.)

> 봇이 잘 동작하는지 미리 테스트하려면(선택):
> ```
> curl "https://api.telegram.org/bot<봇토큰>/sendMessage?chat_id=<chat_id>&text=test"
> ```
> 텔레그램에 `test` 가 도착하면 정상입니다.

### 2) Finnhub API 키

- https://finnhub.io 가입 → 대시보드에서 **무료 API Key** 복사
- 무료 플랜으로 미국 상장사(NASDAQ/NYSE) company-news 조회가 됩니다.
  (분당 60회 호출 제한 — 종목 몇 개 모니터링에는 충분)

### 3) GitHub 계정 + 새 저장소(repository)

비공개(private)로 만드는 것을 권장합니다.

---

## 설치

1. 이 폴더의 파일들을 새 GitHub 저장소에 그대로 올립니다. 구조:
   ```
   ├─ monitor.py
   ├─ config.json
   ├─ requirements.txt
   └─ .github/
      └─ workflows/
         └─ news-alert.yml
   ```
   (`.github/workflows/` 경로가 정확해야 Actions가 인식합니다.)

2. **Secrets 등록**
   저장소 → **Settings → Secrets and variables → Actions → New repository secret**
   아래 3개를 각각 등록:
   | Name | Value |
   |------|-------|
   | `FINNHUB_API_KEY` | Finnhub 키 |
   | `TELEGRAM_BOT_TOKEN` | 봇 토큰 |
   | `TELEGRAM_CHAT_ID` | chat_id |

3. **모니터링할 종목 입력** — `config.json` 수정
   ```json
   {
     "tickers": ["PFE", "MRNA", "ABCD"],
     "keywords": []
   }
   ```
   - `tickers`: 미국 티커 심볼 목록
   - `keywords`: 비워두면 **모든 뉴스 알림**. 특정 단어가 포함된 뉴스만 받고
     싶으면 예: `["FDA", "approval", "trial", "acquisition"]`
     (제목·요약에 하나라도 들어가면 알림)

4. **첫 실행(테스트)**
   저장소 → **Actions 탭 → news-alert → Run workflow** 클릭
   - **첫 실행은 기존 뉴스를 알림 없이 등록(seeding)만 합니다.** 옛날 뉴스가
     쏟아지는 것을 막기 위해서입니다. → **두 번째 실행부터 새 뉴스만 알림**이 옵니다.

이후에는 15분마다 자동으로 돌며, 새 뉴스가 있을 때만 텔레그램이 울립니다.

---

## 자주 묻는 것

- **알림 주기를 바꾸려면?** `news-alert.yml`의 `cron: "*/15 * * * *"` 에서
  `*/15`를 `*/30`(30분) 등으로 변경. (GitHub 무료 cron은 최소 5분, 다만 부하에
  따라 실제 실행이 몇 분 지연될 수 있습니다.)
- **종목 추가/삭제?** `config.json`만 수정하면 됩니다. 새로 추가한 종목은
  다음 실행에서 seeding 후 그 다음부터 알림.
- **알림이 너무 많다?** `keywords`로 필터하거나 종목 수를 줄이세요.
- **state.json 은 뭔가요?** 이미 보낸 기사 id 기록입니다. Actions가 자동으로
  커밋합니다. 손대지 않아도 됩니다.

---

## 참고 — finviz 직접 사용을 원할 경우

뉴스 소스로 finviz를 직접 쓰는 대신 Finnhub를 택한 이유: finviz는 ToS상
스크래핑을 권장하지 않고 봇 차단도 있으며, finviz/news 자체가 외부 매체를 모아
보여주는 aggregator라 Finnhub의 종목별 company-news로 거의 같은 결과를 더
안정적·합법적으로 얻을 수 있기 때문입니다.

코드 없이 바로 쓰고 싶다면 **Finviz Elite**(7일 무료, 이후 약 $24.96~39.50/월)의
종목 페이지 **Set Alert**로 news/ratings/SEC filings 알림을 이메일·푸시로 받을 수
있습니다.
