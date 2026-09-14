import os
import re
import json
import html
from datetime import datetime
from urllib.parse import quote

import feedparser
from openai import OpenAI


# ============================================================
# 설정
# ============================================================

SEARCH_KEYWORDS = [
    "기준금리",
    "한국 경제",
    "미국 경제",
    "조선",
    "LNG선",
    "선박 발주",
    "발전설비",
    "에너지",
    "유가",
    "설비투자",
]

ARTICLES_PER_KEYWORD = 3
TOP_NEWS_COUNT = 8

MODEL = "gpt-5.6-luna"

client = OpenAI(
    api_key=os.environ["OPENAI_API_KEY"]
)


# ============================================================
# Google News RSS 수집
# ============================================================

def get_google_news(keyword, max_articles=3):

    encoded_keyword = quote(keyword)

    rss_url = (
        f"https://news.google.com/rss/search?"
        f"q={encoded_keyword}"
        f"&hl=ko"
        f"&gl=KR"
        f"&ceid=KR:ko"
    )

    feed = feedparser.parse(rss_url)

    articles = []

    for entry in feed.entries[:max_articles]:

        title = entry.get("title", "").strip()
        link = entry.get("link", "").strip()
        summary = entry.get("summary", "").strip()
        published = entry.get("published", "").strip()

        summary = re.sub(
            r"<[^>]+>",
            "",
            summary
        )

        articles.append({
            "keyword": keyword,
            "title": title,
            "summary": summary,
            "link": link,
            "published": published,
        })

    return articles


# ============================================================
# JSON 정리
# ============================================================

def clean_json(text):

    text = text.strip()

    text = text.replace(
        "```json",
        ""
    )

    text = text.replace(
        "```",
        ""
    )

    return json.loads(
        text.strip()
    )


# ============================================================
# AI 1차 분석
# ============================================================

def analyze_article(article):

    prompt = f"""
다음 경제 또는 산업 뉴스를 분석하세요.

목표는 많은 뉴스 중 중요한 이슈를 선별하는 것입니다.

반드시 JSON 형식으로만 답하세요.

분야:
- 거시경제
- 금융·증시
- 산업
- 기업
- 국제
- 정책·사회

중요도 기준:
1 = 일반 정보
2 = 참고 정보
3 = 산업이나 시장에 일정한 영향
4 = 향후 중요한 영향 가능성이 높은 이슈
5 = 경제 또는 산업 흐름을 크게 바꿀 가능성이 있는 핵심 이슈

다음 형식으로 출력하세요.

{{
    "category": "분야",
    "summary": "핵심 내용을 2문장 이내로 요약",
    "importance": 1,
    "keywords": ["키워드1", "키워드2", "키워드3"],
    "why": "왜 중요한지 한 문장"
}}

기사 제목:
{article["title"]}

기사 내용:
{article["summary"]}
"""

    response = client.responses.create(
        model=MODEL,
        input=prompt
    )

    return clean_json(
        response.output_text
    )


# ============================================================
# 중요 뉴스 심층 분석
# ============================================================

def deep_analysis(article, first_result):

    prompt = f"""
다음 뉴스는 중요도가 높은 기사입니다.

앞으로 어떤 변화로 이어질 가능성이 있는지 분석하세요.

반드시 JSON 형식으로만 답하세요.

{{
    "impact": "관련 산업이나 시장에 미칠 영향",
    "watch": "앞으로 주목해야 할 변화 또는 지표",
    "short_term": "단기 전망",
    "long_term": "중장기 전망"
}}

기사 제목:
{article["title"]}

기사 내용:
{article["summary"]}

1차 분석:
{first_result}
"""

    response = client.responses.create(
        model=MODEL,
        input=prompt
    )

    return clean_json(
        response.output_text
    )


# ============================================================
# 기사 수집
# ============================================================

all_articles = []

for keyword in SEARCH_KEYWORDS:

    print("검색:", keyword)

    articles = get_google_news(
        keyword,
        ARTICLES_PER_KEYWORD
    )

    all_articles.extend(
        articles
    )


# ============================================================
# 중복 제거
# ============================================================

unique_articles = []
seen_titles = set()

for article in all_articles:

    if article["title"] in seen_titles:
        continue

    seen_titles.add(
        article["title"]
    )

    unique_articles.append(
        article
    )


# ============================================================
# AI 분석
# ============================================================

results = []

for index, article in enumerate(
    unique_articles,
    start=1
):

    print(
        f"{index}/{len(unique_articles)}",
        article["title"][:60]
    )

    try:

        first = analyze_article(
            article
        )

    except Exception as e:

        print(
            "분석 실패:",
            e
        )

        continue


    importance = int(
        first.get(
            "importance",
            0
        )
    )


    deep = {}

    if importance >= 4:

        try:

            deep = deep_analysis(
                article,
                first
            )

        except Exception as e:

            print(
                "심층 분석 실패:",
                e
            )


    results.append({
        **article,

        "category":
            first.get(
                "category",
                ""
            ),

        "ai_summary":
            first.get(
                "summary",
                ""
            ),

        "importance":
            importance,

        "keywords":
            first.get(
                "keywords",
                []
            ),

        "why":
            first.get(
                "why",
                ""
            ),

        "impact":
            deep.get(
                "impact",
                ""
            ),

        "watch":
            deep.get(
                "watch",
                ""
            ),

        "short_term":
            deep.get(
                "short_term",
                ""
            ),

        "long_term":
            deep.get(
                "long_term",
                ""
            ),
    })


# ============================================================
# 중요도 높은 TOP 8
# ============================================================

results = sorted(
    results,
    key=lambda x: x["importance"],
    reverse=True
)

top_news = results[
    :TOP_NEWS_COUNT
]


# ============================================================
# HTML 생성
# ============================================================

today = datetime.now().strftime(
    "%Y.%m.%d"
)


cards = ""

for item in top_news:

    title = html.escape(
        item["title"]
    )

    category = html.escape(
        item["category"]
    )

    summary = html.escape(
        item["ai_summary"]
    )

    link = html.escape(
        item["link"]
    )

    importance = item["importance"]

    keyword_text = " ".join(
        "#" + html.escape(str(k))
        for k in item["keywords"][:4]
    )

    cards += f"""
    <a class="card"
       href="{link}"
       target="_blank">

        <div class="top">

            <span class="category">
                {category}
            </span>

            <span class="score">
                중요도 {importance}
            </span>

        </div>

        <h2>
            {title}
        </h2>

        <div class="keywords">
            {keyword_text}
        </div>

        <p>
            {summary}
        </p>

        <div class="more">
            원문 뉴스 보기 →
        </div>

    </a>
    """


page = f"""
<!DOCTYPE html>

<html lang="ko">

<head>

<meta charset="UTF-8">

<meta name="viewport"
      content="width=device-width,
               initial-scale=1.0">

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
    font-family:
        Arial,
        "Noto Sans KR",
        sans-serif;
    color: #171717;
}}

.container {{
    max-width: 1400px;
    margin: auto;
    padding: 45px 25px;
}}

.header {{
    margin-bottom: 30px;
}}

.header h1 {{
    font-size: 38px;
    margin: 0 0 8px 0;
}}

.header p {{
    margin: 0;
    color: #777;
}}

.grid {{
    display: grid;
    grid-template-columns:
        repeat(4, 1fr);
    gap: 20px;
}}

.card {{
    display: block;
    background: white;
    border-radius: 18px;
    padding: 22px;
    min-height: 310px;
    text-decoration: none;
    color: inherit;
    box-shadow:
        0 4px 14px
        rgba(0,0,0,0.07);
    transition: 0.2s;
}}

.card:hover {{
    transform:
        translateY(-5px);
    box-shadow:
        0 10px 28px
        rgba(0,0,0,0.13);
}}

.top {{
    display: flex;
    justify-content:
        space-between;
    align-items: center;
    margin-bottom: 18px;
}}

.category {{
    font-size: 13px;
    font-weight: bold;
    color: #666;
}}

.score {{
    font-size: 12px;
    padding: 5px 9px;
    background: #f1f2f4;
    border-radius: 10px;
}}

.card h2 {{
    font-size: 20px;
    line-height: 1.4;
    margin-bottom: 15px;
}}

.keywords {{
    font-size: 13px;
    color: #666;
    margin-bottom: 16px;
}}

.card p {{
    font-size: 14px;
    line-height: 1.7;
    color: #555;
}}

.more {{
    margin-top: 20px;
    font-size: 13px;
    font-weight: bold;
}}

@media
(max-width: 1000px) {{

    .grid {{
        grid-template-columns:
            repeat(2, 1fr);
    }}

}}

@media
(max-width: 600px) {{

    .container {{
        padding: 25px 15px;
    }}

    .grid {{
        grid-template-columns:
            1fr;
    }}

    .header h1 {{
        font-size: 28px;
    }}

}}

</style>

</head>


<body>

<div class="container">

    <div class="header">

        <h1>
            Today's Key Issues
        </h1>

        <p>
            AI가 선정한 오늘의 주요 경제·산업 이슈 |
            {today}
        </p>

    </div>


    <div class="grid">

        {cards}

    </div>

</div>

</body>

</html>
"""


# ============================================================
# index.html 생성
# ============================================================

with open(
    "index.html",
    "w",
    encoding="utf-8"
) as f:

    f.write(
        page
    )


print(
    "index.html 생성 완료"
)
