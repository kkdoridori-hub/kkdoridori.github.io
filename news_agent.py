import os
import re
import json
import html
from datetime import datetime, timezone, timedelta
from urllib.parse import quote

import feedparser
from openai import OpenAI


# =========================================================
# 1. 기본 설정
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
# 2. Google News에서 기사 가져오기
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

        summary = re.sub(
            r"<[^>]+>",
            " ",
            summary
        )

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
# 3. 모든 뉴스 수집
# =========================================================

print("=" * 60)
print("STEP 1 - 뉴스 수집 시작")
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
    "총 수집 기사:",
    len(all_articles)
)


# =========================================================
# 4. 중복 제거
# =========================================================

unique_articles = []
seen = set()

for article in all_articles:

    title = article["title"]

    # 언론사 이름 제거
    normalized = re.sub(
        r"\s*-\s*[^-]+$",
        "",
        title
    )

    normalized = re.sub(
        r"[^가-힣a-zA-Z0-9]",
        "",
        normalized
    ).lower()

    if normalized in seen:
        continue

    seen.add(normalized)

    unique_articles.append(article)


# 너무 많은 기사를 AI에게 보내지 않음
unique_articles = unique_articles[:30]


print(
    "중복 제거 후 AI 후보:",
    len(unique_articles)
)


# =========================================================
# 5. AI에게 전달할 기사 목록 만들기
# =========================================================

article_text = ""

for i, article in enumerate(
    unique_articles
):

    article_text += f"""

기사번호: {i}
제목: {article["title"]}
검색분야: {article["search_keyword"]}
기사요약: {article["summary"][:500]}

"""


# =========================================================
# 6. AI가 오늘의 핵심 뉴스 선정
# =========================================================

prompt = f"""
당신은 경제 및 산업 뉴스 브리핑을 만드는 AI 에이전트입니다.

아래 뉴스 후보 가운데 오늘 알아둘 가치가 높은 핵심 이슈
최대 8개를 선정하세요.

가능하면 정확히 8개를 선정하세요.
후보가 부족한 경우에만 6~7개를 선정하세요.

중요한 규칙:

1. 같은 사건을 다룬 기사는 하나만 선정합니다.

2. 특정 분야에 뉴스가 지나치게 몰리지 않도록 합니다.

3. 가능하면 다음 분야가 골고루 포함되도록 합니다.
   거시경제
   금융·증시
   산업
   기업
   국제
   정책·사회

4. 단순 사건이나 연예 뉴스보다
   경제, 산업, 기업 활동에 영향을 미치는 뉴스를 우선합니다.

5. 중요도는 1~5점으로 평가합니다.

중요도 기준:

5점:
경제 또는 주요 산업의 방향에
큰 영향을 줄 가능성이 있는 핵심 이슈

4점:
시장, 기업, 산업에 의미 있는 영향을
줄 가능성이 높은 이슈

3점:
알아둘 가치가 있지만
영향 범위가 비교적 제한적인 이슈

2점:
참고 수준의 뉴스

1점:
중요도가 낮은 뉴스


각 뉴스는 반드시 다음 내용을 생성하세요.

headline:
원문 제목을 그대로 복사하지 말고
핵심을 짧게 압축한 제목

importance_reason:
왜 이 점수를 줬는지 아주 짧게 설명
예: "물가·금리 동시 영향"
예: "반도체 투자 확대 신호"

points:
기사의 핵심 내용을 3개로 나눠
짧은 문장으로 작성

keywords:
핵심 키워드 3개

watch:
앞으로 무엇을 지켜봐야 하는지 한 문장


반드시 아래 JSON 형식만 출력하세요.
JSON 이외의 설명은 절대 작성하지 마세요.

{{
  "news": [
    {{
      "article_index": 0,
      "category": "거시경제",
      "importance": 5,
      "importance_reason": "물가·금리 동시 영향",
      "headline": "국제유가 100달러선 재돌파",
      "points": [
        "국제유가가 다시 100달러선을 넘어섬",
        "에너지 가격 상승으로 물가 부담이 확대됨",
        "금리 인하 기대에도 영향을 줄 가능성이 있음"
      ],
      "keywords": [
        "국제유가",
        "인플레이션",
        "금리"
      ],
      "watch": "향후 국제유가와 물가 지표의 움직임"
    }}
  ]
}}


뉴스 후보:

{article_text}
"""


# =========================================================
# 7. AI 실행
# =========================================================

print()
print("=" * 60)
print("STEP 2 - AI 뉴스 선정 시작")
print("=" * 60)


selected = []


try:

    response = client.responses.create(
        model=MODEL,
        input=prompt
    )

    text = response.output_text.strip()

    text = text.replace(
        "```json",
        ""
    )

    text = text.replace(
        "```",
        ""
    )

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1:
        raise ValueError(
            "AI 응답에서 JSON을 찾지 못했습니다."
        )

    data = json.loads(
        text[start:end + 1]
    )

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
        e
    )

    selected = []


# =========================================================
# 8. 안전장치
#
# AI가 실패하거나 6개 미만을 반환해도
# 사이트가 0 ISSUES가 되지 않도록 함
# =========================================================

used_indexes = set()

for item in selected:

    try:

        used_indexes.add(
            int(item["article_index"])
        )

    except:
        pass


if len(selected) < 6:

    print(
        "AI 선정 뉴스 부족 → 기본 뉴스로 보충"
    )

    for i, article in enumerate(
        unique_articles
    ):

        if i in used_indexes:
            continue

        selected.append({
            "article_index": i,
            "category": "주요뉴스",
            "importance": 3,
            "importance_reason":
                "오늘의 주요 경제·산업 뉴스",
            "headline":
                article["title"],
            "points": [
                article["summary"][:90]
                if article["summary"]
                else "오늘 확인할 주요 경제·산업 이슈"
            ],
            "keywords": [
                article["search_keyword"]
            ],
            "watch":
                "관련 후속 보도를 확인하세요."
        })

        used_indexes.add(i)

        if len(selected) >= 8:
            break


selected = selected[:FINAL_NEWS_COUNT]


print(
    "최종 뉴스:",
    len(selected),
    "개"
)


# =========================================================
# 9. 카드 만들기
# =========================================================

cards = ""


for number, item in enumerate(
    selected,
    start=1
):

    try:

        article_index = int(
            item.get(
                "article_index",
                0
            )
        )

        article = unique_articles[
            article_index
        ]

    except:

        continue


    headline = html.escape(
        str(
            item.get(
                "headline",
                article["title"]
            )
        )
    )

    category = html.escape(
        str(
            item.get(
                "category",
                "주요뉴스"
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


    # 중요도 숫자 정리
    try:

        importance = int(
            item.get(
                "importance",
                3
            )
        )

    except:

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

        for keyword
        in keywords[:3]

    )


    # 핵심 요약
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

        points_html += (
            "<li>"
            +
            html.escape(
                str(point)
            )
            +
            "</li>"
        )


    cards += f"""

    <article class="card">

        <div class="card-inner">

            <div class="card-top">

                <span class="number">
                    {number:02d}
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
# 10. 한국 날짜
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
# 11. 웹페이지 만들기
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

<title>
Today's Key Issues
</title>


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


/* HEADER */

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


/* GRID */

.grid {{
    display: grid;

    grid-template-columns:
        repeat(
            4,
            minmax(0, 1fr)
        );

    gap: 20px;
}}


/* CARD */

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
    transform:
        translateY(-4px);

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


/* CARD TOP */

.card-top {{
    display: flex;

    justify-content:
        space-between;

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

    padding:
        6px 10px;

    border-radius: 20px;

    font-size: 12px;
    font-weight: 700;
}}


/* IMPORTANCE */

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


/* TITLE */

.card h2 {{
    margin:
        0 0 12px;

    font-size: 20px;
    line-height: 1.4;

    letter-spacing:
        -0.5px;
}}


/* KEYWORDS */

.keywords {{
    color: #777;

    font-size: 12px;
    line-height: 1.5;

    margin-bottom: 16px;
}}


/* POINTS */

.points {{
    padding-left: 19px;

    margin:
        0 0 18px;
}}


.points li {{
    color: #444;

    font-size: 14px;
    line-height: 1.5;

    margin-bottom: 7px;
}}


/* WATCH */

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


/* LINK */

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


/* TABLET */

@media
(max-width: 1100px) {{

    .grid {{
        grid-template-columns:
            repeat(
                2,
                minmax(0, 1fr)
            );
    }}

}}


/* MOBILE */

@media
(max-width: 650px) {{

    .container {{
        padding:
            28px 15px 50px;
    }}


    .header h1 {{
        font-size: 30px;
    }}


    .header-info {{
        line-height: 1.6;
    }}


    .grid {{
        grid-template-columns:
            1fr;
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

            {len(selected)} ISSUES

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
# 12. index.html 저장
# =========================================================

with open(
    "index.html",
    "w",
    encoding="utf-8"
) as file:

    file.write(page)


print()
print("=" * 60)
print("완료!")
print("날짜:", today)
print("생성된 카드:", len(selected))
print("=" * 60)
