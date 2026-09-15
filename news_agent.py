import os
import re
import json
import html
from datetime import datetime, timezone, timedelta
from urllib.parse import quote

import feedparser
from openai import OpenAI


# =========================================================
# 기본 설정
# =========================================================

MODEL = "gpt-5.6-luna"

SEARCH_KEYWORDS = [
    "한국 경제",
    "미국 경제",
    "금리 환율",
    "국제유가 에너지",
    "반도체 AI",
    "조선 해운",
    "자동차 배터리",
    "기업 투자",
    "정부 경제정책",
    "글로벌 경제"
]

ARTICLES_PER_KEYWORD = 4
FINAL_NEWS_COUNT = 8

client = OpenAI(
    api_key=os.environ["OPENAI_API_KEY"]
)


# =========================================================
# Google News 기사 수집
# =========================================================

def get_news(keyword):

    encoded = quote(keyword)

    url = (
        "https://news.google.com/rss/search?"
        f"q={encoded}+when:1d"
        "&hl=ko"
        "&gl=KR"
        "&ceid=KR:ko"
    )

    feed = feedparser.parse(url)

    articles = []

    for entry in feed.entries[:ARTICLES_PER_KEYWORD]:

        title = entry.get(
            "title",
            ""
        ).strip()

        link = entry.get(
            "link",
            ""
        ).strip()

        summary = entry.get(
            "summary",
            ""
        ).strip()

        # HTML 태그 제거
        summary = re.sub(
            r"<[^>]+>",
            " ",
            summary
        )

        # &nbsp; &amp; 등의 HTML 문자 변환
        summary = html.unescape(summary)

        # 남아 있는 nbsp 제거
        summary = summary.replace(
            "\xa0",
            " "
        )

        summary = summary.replace(
            "&nbsp;",
            " "
        )

        # 공백 정리
        summary = re.sub(
            r"\s+",
            " ",
            summary
        ).strip()

        if not title or not link:
            continue

        articles.append({
            "title": title,
            "link": link,
            "summary": summary,
            "search_keyword": keyword
        })

    return articles


# =========================================================
# 뉴스 수집
# =========================================================

print("=" * 60)
print("STEP 1 - 뉴스 수집")
print("=" * 60)

all_articles = []

for keyword in SEARCH_KEYWORDS:

    try:

        articles = get_news(keyword)

        print(
            keyword,
            ":",
            len(articles),
            "개"
        )

        all_articles.extend(articles)

    except Exception as e:

        print(
            keyword,
            "수집 실패:",
            e
        )


print(
    "총 수집:",
    len(all_articles)
)


# =========================================================
# 중복 제거
# =========================================================

unique_articles = []
seen_titles = set()

for article in all_articles:

    normalized = re.sub(
        r"\s*-\s*[^-]+$",
        "",
        article["title"]
    )

    normalized = re.sub(
        r"[^가-힣a-zA-Z0-9]",
        "",
        normalized
    ).lower()

    if normalized in seen_titles:
        continue

    seen_titles.add(normalized)
    unique_articles.append(article)


# AI에 너무 많은 기사를 보내지 않도록 제한
unique_articles = unique_articles[:30]


print(
    "중복 제거 후 후보:",
    len(unique_articles)
)


# =========================================================
# AI에게 전달할 기사 목록
# =========================================================

article_text = ""

for index, article in enumerate(unique_articles):

    article_text += f"""
기사번호: {index}
제목: {article["title"]}
검색분야: {article["search_keyword"]}
기사내용: {article["summary"][:500]}

"""


# =========================================================
# AI 프롬프트
# =========================================================

prompt = f"""
당신은 경제와 산업 동향을 분석하는
데일리 뉴스 브리핑 AI입니다.

아래 기사 후보 중 오늘 알아야 할
가장 중요한 경제·산업 이슈를 선정하세요.

가능하면 정확히 8개를 선정하세요.
기사 후보가 부족할 때만 6~7개를 선정하세요.


[선정 원칙]

1. 같은 사건을 다룬 기사는 하나만 선정합니다.

2. 특정 주제에 지나치게 몰리지 않도록 합니다.

3. 가능하면 다음 분야를 다양하게 포함합니다.

- 거시경제
- 금융·증시
- 산업
- 기업
- 국제
- 정책·사회

4. 단순 사건보다 향후 경제,
산업 또는 기업 활동에 영향을 줄 수 있는
뉴스를 우선합니다.

5. 단순히 기사 제목이 자극적이라는 이유로
중요한 뉴스로 선정하지 않습니다.


[중요도 평가]

5점:
경제 또는 주요 산업의 방향에
큰 영향을 줄 가능성이 있는 핵심 이슈

4점:
시장, 기업 또는 산업에
의미 있는 영향을 줄 가능성이 높은 이슈

3점:
알아둘 가치가 있으나
영향 범위가 비교적 제한적인 이슈

2점:
참고 수준의 뉴스

1점:
경제·산업 관점에서 중요도가 낮은 뉴스


[각 뉴스별 작성 방법]

category:
가장 적절한 분야 하나를 선택합니다.

importance:
1~5의 숫자로 평가합니다.

importance_reason:
왜 중요한지 아주 짧게 작성합니다.

예:
"물가·금리 동시 영향"
"반도체 투자 확대 신호"
"글로벌 교역 영향"
"기업 실적 변동 가능성"


headline:
원문 기사 제목을 그대로 복사하지 말고
핵심 내용을 한눈에 이해할 수 있도록
짧게 다시 작성합니다.


points:
기사에서 알아야 할 핵심 내용을
서로 다른 3개의 짧은 문장으로 작성합니다.

각 문장은 구체적인 사실을 담아야 합니다.


keywords:
핵심 키워드 3개를 작성합니다.


watch:
이 뉴스가 앞으로 실제 경제 또는 산업 변화로
이어지는지를 판단하기 위해 추적해야 할
구체적인 지표, 가격, 일정 또는 변수를 작성합니다.

절대로 다음과 같은 모호한 표현을 사용하지 마세요.

"후속 보도를 확인하세요"
"관련 동향을 지켜봐야 합니다"
"상황을 주시해야 합니다"
"향후 변화에 주목해야 합니다"

대신 실제로 확인할 수 있는 변수를 제시하세요.


예시:

국제유가 뉴스
→ "WTI 가격, 중동 원유 공급 차질, 미국 CPI"

금리 뉴스
→ "다음 FOMC, 미국 CPI, 미 10년물 국채금리"

한국 금리 뉴스
→ "한국은행 금통위, 소비자물가, 원·달러 환율"

반도체 뉴스
→ "빅테크 CAPEX, HBM 수요, 반도체 기업 실적"

AI 투자 뉴스
→ "빅테크 AI 투자액, 데이터센터 CAPEX, 전력 수요"

조선 뉴스
→ "신규 선박 발주량, LNG선 선가, 조선사 수주잔고"

환율 뉴스
→ "원·달러 환율, 외국인 자금 흐름, 미국 금리"

증시 뉴스
→ "외국인 순매수, 기업 실적 전망, 시장금리"

기업 투자 뉴스
→ "실제 투자 집행액, 생산능력 증설, 향후 실적 가이던스"


[출력 형식]

반드시 JSON만 출력하세요.

JSON 앞이나 뒤에 설명을 작성하지 마세요.

형식:

{{
  "news": [
    {{
      "article_index": 0,
      "category": "거시경제",
      "importance": 5,
      "importance_reason": "물가·금리 동시 영향",
      "headline": "국제유가 100달러선 재돌파",
      "points": [
        "국제유가가 다시 100달러선을 넘어섰습니다",
        "에너지 가격 상승으로 물가 부담이 커지고 있습니다",
        "금리 정책에도 영향을 줄 가능성이 있습니다"
      ],
      "keywords": [
        "국제유가",
        "인플레이션",
        "금리"
      ],
      "watch": "WTI 가격, 중동 원유 공급 차질, 미국 CPI"
    }}
  ]
}}


[기사 후보]

{article_text}
"""


# =========================================================
# AI 실행
# =========================================================

print()
print("=" * 60)
print("STEP 2 - AI 분석")
print("=" * 60)

selected = []

try:

    response = client.responses.create(
        model=MODEL,
        input=prompt
    )

    raw_text = response.output_text.strip()

    raw_text = raw_text.replace(
        "```json",
        ""
    )

    raw_text = raw_text.replace(
        "```",
        ""
    )

    start = raw_text.find("{")
    end = raw_text.rfind("}")

    if start == -1 or end == -1:

        raise ValueError(
            "AI 응답에서 JSON을 찾지 못했습니다."
        )

    json_text = raw_text[
        start:end + 1
    ]

    data = json.loads(json_text)

    selected = data.get(
        "news",
        []
    )

    print(
        "AI 선정:",
        len(selected),
        "개"
    )

except Exception as e:

    print(
        "AI 분석 실패:",
        repr(e)
    )

    selected = []


# =========================================================
# 안전장치
#
# AI가 실패해도 사이트가 0 ISSUES가 되지 않도록 함
# =========================================================

used_indexes = set()

for item in selected:

    try:

        used_indexes.add(
            int(
                item.get(
                    "article_index"
                )
            )
        )

    except Exception:

        pass


if len(selected) < 6:

    print(
        "AI 결과 부족 → 기본 뉴스로 보충"
    )

    for index, article in enumerate(
        unique_articles
    ):

        if index in used_indexes:
            continue

        summary_text = (
            article["summary"][:120]
            if article["summary"]
            else
            "오늘 확인할 주요 경제·산업 이슈입니다."
        )

        selected.append({
            "article_index": index,
            "category": "주요뉴스",
            "importance": 3,
            "importance_reason":
                "오늘의 주요 경제·산업 뉴스",
            "headline":
                article["title"],
            "points": [
                summary_text
            ],
            "keywords": [
                article["search_keyword"]
            ],
            "watch":
                "AI 분석 결과를 생성하지 못했습니다."
        })

        used_indexes.add(index)

        if len(selected) >= FINAL_NEWS_COUNT:
            break


selected = selected[:FINAL_NEWS_COUNT]


print(
    "최종 선정:",
    len(selected),
    "개"
)


# =========================================================
# 카드 HTML 생성
# =========================================================

cards = ""

valid_card_count = 0

for item in selected:

    try:

        article_index = int(
            item.get(
                "article_index",
                -1
            )
        )

        if (
            article_index < 0
            or
            article_index >= len(unique_articles)
        ):
            continue

        article = unique_articles[
            article_index
        ]

    except Exception:

        continue


    valid_card_count += 1


    category = html.escape(
        str(
            item.get(
                "category",
                "주요뉴스"
            )
        )
    )


    headline = html.escape(
        str(
            item.get(
                "headline",
                article["title"]
            )
        )
    )


    reason = html.escape(
        str(
            item.get(
                "importance_reason",
                ""
            )
        )
    )


    watch = html.escape(
        str(
            item.get(
                "watch",
                ""
            )
        )
    )


    link = html.escape(
        article["link"]
    )


    # 중요도
    try:

        importance = int(
            item.get(
                "importance",
                3
            )
        )

    except Exception:

        importance = 3


    importance = max(
        1,
        min(
            importance,
            5
        )
    )


    stars = (
        "★" * importance
        +
        "☆" * (5 - importance)
    )


    # 키워드
    keywords = item.get(
        "keywords",
        []
    )

    if not isinstance(
        keywords,
        list
    ):

        keywords = []


    keyword_html = " ".join(
        "#"
        +
        html.escape(
            str(keyword)
        )

        for keyword in keywords[:3]
    )


    # 핵심 내용
    points = item.get(
        "points",
        []
    )

    if not isinstance(
        points,
        list
    ):

        points = []


    points_html = ""

    for point in points[:3]:

        clean_point = html.unescape(
            str(point)
        )

        clean_point = clean_point.replace(
            "\xa0",
            " "
        )

        clean_point = clean_point.replace(
            "&nbsp;",
            " "
        )

        clean_point = re.sub(
            r"\s+",
            " ",
            clean_point
        ).strip()

        points_html += (
            "<li>"
            +
            html.escape(clean_point)
            +
            "</li>"
        )


    cards += f"""
    <article class="card">

        <div class="card-inner">

            <div class="card-top">

                <span class="number">
                    {valid_card_count:02d}
                </span>

                <span class="category">
                    {category}
                </span>

            </div>

            <div class="importance-row">

                <span class="stars">
                    {stars}
                </span>

                <span class="reason">
                    {reason}
                </span>

            </div>

            <h2>
                {headline}
            </h2>

            <div class="keywords">
                {keyword_html}
            </div>

            <ul class="points">
                {points_html}
            </ul>

            <div class="watch">

                <div class="watch-label">
                    앞으로 볼 것
                </div>

                <div class="watch-content">
                    {watch}
                </div>

            </div>

            <a
                class="news-link"
                href="{link}"
                target="_blank"
                rel="noopener noreferrer"
            >
                원문 뉴스 보기 →
            </a>

        </div>

    </article>
    """


# =========================================================
# 한국 날짜
# =========================================================

KST = timezone(
    timedelta(hours=9)
)

today = datetime.now(
    KST
).strftime(
    "%Y.%m.%d"
)


# =========================================================
# 웹페이지 HTML
# =========================================================

page = f"""
<!DOCTYPE html>

<html lang="ko">

<head>

<meta charset="UTF-8">

<meta
    name="viewport"
    content="width=device-width, initial-scale=1.0"
>

<title>Today's Key Issues</title>

<style>

* {{
    box-sizing: border-box;
}}

body {{
    margin: 0;
    background: #f4f5f7;
    color: #151515;
    font-family:
        Arial,
        "Apple SD Gothic Neo",
        "Noto Sans KR",
        sans-serif;
}}

.container {{
    max-width: 1500px;
    margin: 0 auto;
    padding: 45px 30px 70px;
}}

.header {{
    margin-bottom: 32px;
}}

.header-label {{
    color: #777;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 2px;
    margin-bottom: 8px;
}}

.header h1 {{
    margin: 0;
    font-size: 42px;
    letter-spacing: -1px;
}}

.header-info {{
    margin-top: 12px;
    color: #777;
    font-size: 14px;
}}

.grid {{
    display: grid;
    grid-template-columns:
        repeat(4, minmax(0, 1fr));
    gap: 20px;
}}

.card {{
    background: white;
    border-radius: 18px;
    box-shadow:
        0 4px 16px
        rgba(0, 0, 0, 0.07);
    transition:
        transform 0.2s ease,
        box-shadow 0.2s ease;
}}

.card:hover {{
    transform: translateY(-4px);
    box-shadow:
        0 12px 28px
        rgba(0, 0, 0, 0.11);
}}

.card-inner {{
    padding: 22px;
    height: 100%;
    display: flex;
    flex-direction: column;
}}

.card-top {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 14px;
}}

.number {{
    color: #aaa;
    font-size: 12px;
    font-weight: 700;
}}

.category {{
    background: #f1f2f4;
    padding: 6px 10px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 700;
}}

.importance-row {{
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 14px;
}}

.stars {{
    font-size: 14px;
    white-space: nowrap;
}}

.reason {{
    color: #777;
    font-size: 12px;
    line-height: 1.3;
}}

.card h2 {{
    margin: 0 0 12px;
    font-size: 20px;
    line-height: 1.4;
    letter-spacing: -0.5px;
}}

.keywords {{
    color: #777;
    font-size: 12px;
    line-height: 1.5;
    margin-bottom: 16px;
}}

.points {{
    padding-left: 19px;
    margin: 0 0 18px;
}}

.points li {{
    color: #444;
    font-size: 14px;
    line-height: 1.5;
    margin-bottom: 7px;
}}

.watch {{
    background: #f6f7f8;
    padding: 13px;
    border-radius: 11px;
    margin-top: auto;
}}

.watch-label {{
    color: #777;
    font-size: 11px;
    font-weight: 700;
    margin-bottom: 5px;
}}

.watch-content {{
    font-size: 13px;
    line-height: 1.5;
}}

.news-link {{
    display: block;
    margin-top: 15px;
    color: #111;
    font-size: 12px;
    font-weight: 700;
    text-decoration: none;
}}

.news-link:hover {{
    text-decoration: underline;
}}

@media (max-width: 1100px) {{

    .grid {{
        grid-template-columns:
            repeat(2, minmax(0, 1fr));
    }}

}}

@media (max-width: 650px) {{

    .container {{
        padding: 28px 15px 50px;
    }}

    .header h1 {{
        font-size: 30px;
    }}

    .header-info {{
        line-height: 1.6;
    }}

    .grid {{
        grid-template-columns: 1fr;
    }}

    .card h2 {{
        font-size: 19px;
    }}

}}

</style>

</head>

<body>

<div class="container">

    <header class="header">

        <div class="header-label">
            DAILY AI BRIEFING
        </div>

        <h1>
            TODAY'S KEY ISSUES
        </h1>

        <div class="header-info">

            AI가 선별한 오늘의 경제·산업 핵심 이슈

            &nbsp; | &nbsp;

            {today}

            &nbsp; | &nbsp;

            {valid_card_count} ISSUES

        </div>

    </header>

    <main class="grid">
        {cards}
    </main>

</div>

</body>

</html>
"""


# =========================================================
# index.html 저장
# =========================================================

with open(
    "index.html",
    "w",
    encoding="utf-8"
) as file:

    file.write(page)


print()
print("=" * 60)
print("완료")
print("날짜:", today)
print("생성된 카드:", valid_card_count)
print("=" * 60)
