import os
import re
import json
import html
from datetime import datetime
from urllib.parse import quote

import feedparser
from openai import OpenAI


# ============================================================
# 1. 기본 설정
# ============================================================

SEARCH_KEYWORDS = [
    "한국 경제",
    "미국 경제",
    "기준금리",
    "환율",
    "국제유가",
    "조선업",
    "LNG선",
    "선박 발주",
    "발전설비",
    "에너지 산업",
    "반도체",
    "AI 산업",
    "설비투자",
    "중국 경제",
]

# 검색어 하나당 가져올 기사 수
ARTICLES_PER_KEYWORD = 5

# 최종 화면에 보여줄 기사 수
TOP_NEWS_COUNT = 8

MODEL = "gpt-5.6-luna"

client = OpenAI(
    api_key=os.environ["OPENAI_API_KEY"]
)


# ============================================================
# 2. Google News RSS에서 뉴스 수집
# ============================================================

def get_google_news(keyword, max_articles=5):

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

        # HTML 태그 제거
        summary = re.sub(
            r"<[^>]+>",
            "",
            summary
        )

        articles.append({
            "search_keyword": keyword,
            "title": title,
            "summary": summary,
            "link": link,
            "published": published,
        })

    return articles


# ============================================================
# 3. AI 응답 JSON 정리
# ============================================================

def clean_json(text):

    text = text.strip()

    text = text.replace("```json", "")
    text = text.replace("```", "")
    text = text.strip()

    return json.loads(text)


# ============================================================
# 4. 기사 1차 분석
# ============================================================

def analyze_article(article):

    prompt = f"""
다음 경제 또는 산업 뉴스를 분석하세요.

목표는 많은 뉴스 중 오늘 알아야 할 핵심 이슈를
짧고 명확하게 선별하는 것입니다.

반드시 JSON 형식으로만 답하세요.
코드 블록은 사용하지 마세요.

분야는 다음 중 하나만 선택하세요.

- 거시경제
- 금융·증시
- 산업
- 기업
- 국제
- 정책·사회

중요도 기준:

1점 = 일반적인 정보
2점 = 참고할 만한 정보
3점 = 시장이나 산업에 일정한 영향
4점 = 향후 중요한 변화로 이어질 가능성이 높은 이슈
5점 = 경제 또는 산업 흐름에 큰 영향을 줄 수 있는 핵심 이슈

다음 형식을 정확히 지키세요.

{{
    "category": "분야",
    "importance": 1,
    "importance_reason": "왜 중요한지 15자 내외로 짧게",
    "headline": "기사 핵심을 한눈에 알 수 있는 짧은 제목",
    "points": [
        "핵심 내용 1",
        "핵심 내용 2",
        "핵심 내용 3"
    ],
    "keywords": [
        "키워드1",
        "키워드2",
        "키워드3"
    ],
    "watch": "앞으로 주목해야 할 변화나 지표를 한 문장으로"
}}

주의:
- points는 긴 문장이 아니라 한눈에 읽을 수 있는 짧은 문장으로 작성
- headline은 원래 기사 제목을 그대로 복사하지 말고 핵심 의미만 압축
- importance_reason은 아주 짧게 작성
- 같은 표현을 반복하지 말 것

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
# 5. 중요 뉴스 심층 분석
# ============================================================

def deep_analysis(article, first_result):

    prompt = f"""
다음 뉴스는 중요한 경제 또는 산업 이슈입니다.

앞으로 어떤 변화로 이어질 수 있는지 간략하게 분석하세요.

반드시 JSON 형식으로만 답하세요.

{{
    "impact": "관련 산업이나 시장에 미칠 영향 한 문장",
    "short_term": "단기적으로 예상되는 변화 한 문장",
    "long_term": "중장기적으로 예상되는 변화 한 문장"
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
# 6. 뉴스 수집
# ============================================================

print("=" * 60)
print("AI NEWS AGENT START")
print("=" * 60)

all_articles = []

for keyword in SEARCH_KEYWORDS:

    print("검색 중:", keyword)

    articles = get_google_news(
        keyword,
        ARTICLES_PER_KEYWORD
    )

    all_articles.extend(articles)


print()
print("수집 기사 수:", len(all_articles))


# ============================================================
# 7. 정확히 같은 제목 중복 제거
# ============================================================

unique_articles = []
seen_titles = set()

for article in all_articles:

    clean_title = (
        article["title"]
        .lower()
        .strip()
    )

    if clean_title in seen_titles:
        continue

    seen_titles.add(clean_title)

    unique_articles.append(article)


print(
    "중복 제거 후:",
    len(unique_articles)
)


# ============================================================
# 8. AI 분석
# ============================================================

results = []

for i, article in enumerate(
    unique_articles,
    start=1
):

    print()
    print(
        f"[{i}/{len(unique_articles)}]",
        article["title"][:60]
    )

    try:

        first = analyze_article(article)

    except Exception as e:

        print(
            "1차 분석 실패:",
            e
        )

        continue


    try:

        importance = int(
            first.get(
                "importance",
                0
            )
        )

    except:

        importance = 0


    deep = {}

    # 중요도 4 이상이면 추가 분석
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

        "search_keyword":
            article["search_keyword"],

        "title":
            article["title"],

        "link":
            article["link"],

        "published":
            article["published"],

        "category":
            first.get(
                "category",
                "기타"
            ),

        "importance":
            importance,

        "importance_reason":
            first.get(
                "importance_reason",
                ""
            ),

        "headline":
            first.get(
                "headline",
                article["title"]
            ),

        "points":
            first.get(
                "points",
                []
            ),

        "keywords":
            first.get(
                "keywords",
                []
            ),

        "watch":
            first.get(
                "watch",
                ""
            ),

        "impact":
            deep.get(
                "impact",
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
# 9. 중요도 높은 순으로 정렬
# ============================================================

results = sorted(
    results,
    key=lambda x: x["importance"],
    reverse=True
)


# ============================================================
# 10. 주제 다양성을 고려해 TOP 8 선정
# ============================================================

top_news = []

used_main_keywords = set()
used_categories_count = {}


for item in results:

    keywords = item.get(
        "keywords",
        []
    )

    if not isinstance(keywords, list):
        keywords = []


    # 첫 번째 키워드를 대표 키워드로 사용
    if len(keywords) > 0:

        main_keyword = str(
            keywords[0]
        ).strip().lower()

    else:

        main_keyword = (
            item["search_keyword"]
            .strip()
            .lower()
        )


    category = item.get(
        "category",
        "기타"
    )


    # 같은 대표 키워드는 우선 제외
    if main_keyword in used_main_keywords:
        continue


    # 한 분야가 지나치게 많아지는 것도 방지
    category_count = used_categories_count.get(
        category,
        0
    )

    if category_count >= 2:
        continue


    top_news.append(item)

    used_main_keywords.add(
        main_keyword
    )

    used_categories_count[
        category
    ] = category_count + 1


    if len(top_news) >= TOP_NEWS_COUNT:
        break


# ============================================================
# 11. 다양성 필터 때문에 6개 미만이면 다시 채우기
# ============================================================

if len(top_news) < 6:

    for item in results:

        if item in top_news:
            continue

        top_news.append(item)

        if len(top_news) >= 6:
            break


# 그래도 8개까지 채울 수 있으면 채우기
if len(top_news) < TOP_NEWS_COUNT:

    for item in results:

        if item in top_news:
            continue

        top_news.append(item)

        if len(top_news) >= TOP_NEWS_COUNT:
            break


print()
print(
    "최종 선정 뉴스:",
    len(top_news)
)


# ============================================================
# 12. HTML 카드 생성
# ============================================================

cards = ""

for number, item in enumerate(
    top_news,
    start=1
):

    category = html.escape(
        str(
            item.get(
                "category",
                ""
            )
        )
    )

    headline = html.escape(
        str(
            item.get(
                "headline",
                ""
            )
        )
    )

    original_title = html.escape(
        str(
            item.get(
                "title",
                ""
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
        str(
            item.get(
                "link",
                "#"
            )
        )
    )

    importance = item.get(
        "importance",
        0
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


    keyword_text = " ".join(
        "#" + html.escape(str(k))
        for k in keywords[:4]
    )


    # 핵심 포인트
    points = item.get(
        "points",
        []
    )

    if not isinstance(
        points,
        list
    ):

        points = []


    point_html = ""

    for point in points[:3]:

        point_html += (
            "<li>"
            + html.escape(str(point))
            + "</li>"
        )


    # 중요도 별
    stars = "★" * importance
    empty_stars = "☆" * (
        5 - importance
    )


    cards += f"""
    <article class="card">

        <a
            class="card-link"
            href="{link}"
            target="_blank"
            rel="noopener noreferrer"
        >

            <div class="card-top">

                <span class="number">
                    {number:02d}
                </span>

                <span class="category">
                    {category}
                </span>

            </div>


            <div class="importance-row">

                <span class="importance">
                    {stars}{empty_stars}
                </span>

                <span class="importance-reason">
                    {reason}
                </span>

            </div>


            <h2>
                {headline}
            </h2>


            <div class="keywords">
                {keyword_text}
            </div>


            <ul class="points">
                {point_html}
            </ul>


            <div class="watch">

                <div class="watch-title">
                    앞으로 볼 것
                </div>

                <div class="watch-text">
                    {watch}
                </div>

            </div>


            <div class="original-title">
                원문 | {original_title}
            </div>


            <div class="more">
                원문 뉴스 보기 →
            </div>

        </a>

    </article>
    """


# ============================================================
# 13. 전체 웹페이지
# ============================================================

today = datetime.now().strftime(
    "%Y.%m.%d"
)


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
    font-family:
        Arial,
        "Apple SD Gothic Neo",
        "Noto Sans KR",
        sans-serif;
    color: #171717;
}}

.container {{
    max-width: 1450px;
    margin: auto;
    padding: 45px 25px 70px;
}}


/* =============================
   HEADER
============================= */

.header {{
    margin-bottom: 32px;
}}

.header-small {{
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 2px;
    color: #777;
    margin-bottom: 8px;
}}

.header h1 {{
    margin: 0;
    font-size: 42px;
    letter-spacing: -1.5px;
}}

.header p {{
    margin: 10px 0 0;
    color: #777;
    font-size: 15px;
}}


/* =============================
   GRID
============================= */

.grid {{
    display: grid;
    grid-template-columns:
        repeat(4, minmax(0, 1fr));
    gap: 20px;
}}


/* =============================
   CARD
============================= */

.card {{
    background: white;
    border-radius: 18px;
    overflow: hidden;
    box-shadow:
        0 4px 15px
        rgba(0, 0, 0, 0.07);
    transition:
        transform 0.2s ease,
        box-shadow 0.2s ease;
}}

.card:hover {{
    transform:
        translateY(-5px);

    box-shadow:
        0 12px 28px
        rgba(0, 0, 0, 0.12);
}}

.card-link {{
    display: block;
    height: 100%;
    padding: 22px;
    text-decoration: none;
    color: inherit;
}}


/* =============================
   TOP
============================= */

.card-top {{
    display: flex;
    align-items: center;
    justify-content:
        space-between;
    margin-bottom: 14px;
}}

.number {{
    font-size: 12px;
    font-weight: 700;
    color: #aaa;
}}

.category {{
    font-size: 12px;
    font-weight: 700;
    background: #f2f3f5;
    padding: 6px 9px;
    border-radius: 20px;
}}


/* =============================
   IMPORTANCE
============================= */

.importance-row {{
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 15px;
}}

.importance {{
    font-size: 14px;
    letter-spacing: 1px;
}}

.importance-reason {{
    font-size: 12px;
    color: #777;
}}


/* =============================
   HEADLINE
============================= */

.card h2 {{
    margin:
        0 0 13px;
    font-size: 21px;
    line-height: 1.38;
    letter-spacing: -0.5px;
}}


/* =============================
   KEYWORDS
============================= */

.keywords {{
    font-size: 12px;
    color: #777;
    margin-bottom: 17px;
    line-height: 1.6;
}}


/* =============================
   BULLETS
============================= */

.points {{
    padding-left: 19px;
    margin:
        0 0 18px;
}}

.points li {{
    margin-bottom: 7px;
    font-size: 14px;
    line-height: 1.5;
    color: #444;
}}


/* =============================
   WATCH
============================= */

.watch {{
    padding: 13px 14px;
    background: #f6f7f8;
    border-radius: 11px;
    margin-top: 15px;
}}

.watch-title {{
    font-size: 11px;
    font-weight: 700;
    color: #777;
    margin-bottom: 5px;
}}

.watch-text {{
    font-size: 13px;
    line-height: 1.5;
}}


/* =============================
   ORIGINAL TITLE
============================= */

.original-title {{
    margin-top: 17px;
    padding-top: 14px;
    border-top: 1px solid #eee;
    font-size: 11px;
    line-height: 1.5;
    color: #999;
}}


.more {{
    margin-top: 12px;
    font-size: 12px;
    font-weight: 700;
}}


/* =============================
   TABLET
============================= */

@media
(max-width: 1100px) {{

    .grid {{
        grid-template-columns:
            repeat(2, minmax(0, 1fr));
    }}

}}


/* =============================
   MOBILE
============================= */

@media
(max-width: 650px) {{

    .container {{
        padding:
            28px 15px 50px;
    }}

    .header h1 {{
        font-size: 31px;
    }}

    .grid {{
        grid-template-columns:
            1fr;
    }}

    .card h2 {{
        font-size: 20px;
    }}

}}

</style>

</head>


<body>

<div class="container">

    <header class="header">

        <div class="header-small">
            DAILY AI BRIEFING
        </div>

        <h1>
            TODAY'S KEY ISSUES
        </h1>

        <p>
            AI가 선별한 오늘의 경제·산업 핵심 이슈
            &nbsp; | &nbsp;
            {today}
            &nbsp; | &nbsp;
            {len(top_news)} ISSUES
        </p>

    </header>


    <main class="grid">

        {cards}

    </main>

</div>

</body>

</html>
"""


# ============================================================
# 14. index.html 저장
# ============================================================

with open(
    "index.html",
    "w",
    encoding="utf-8"
) as f:

    f.write(page)


print()
print("=" * 60)
print("index.html 생성 완료")
print("오늘의 이슈:", len(top_news), "개")
print("=" * 60)
