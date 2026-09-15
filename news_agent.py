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

FINAL_NEWS_COUNT = 8
ARTICLES_PER_TOPIC = 4


# 다양한 분야에서 뉴스 후보 수집
TOPICS = {

    "경제·금융": [
        "한국 경제 금융",
        "미국 경제 금리 환율"
    ],

    "산업": [
        "조선 해운 에너지 산업",
        "자동차 배터리 산업",
        "반도체 산업"
    ],

    "기업": [
        "기업 투자 실적 M&A",
        "한국 기업 해외투자"
    ],

    "AI·기술": [
        "AI 데이터센터 반도체",
        "인공지능 빅테크 기술"
    ],

    "국제": [
        "글로벌 경제 국제정세",
        "미국 중국 무역 관세"
    ],

    "사회·문화": [
        "한국 사회 문화 트렌드",
        "콘텐츠 엔터테인먼트 소비 트렌드"
    ],

    "정책": [
        "정부 산업 정책 규제",
        "경제 정책 기업 정책"
    ]
}


client = OpenAI(
    api_key=os.environ["OPENAI_API_KEY"]
)


# =========================================================
# Google News 수집
# =========================================================

def get_news(query, topic):

    encoded = quote(query)

    url = (
        "https://news.google.com/rss/search?"
        f"q={encoded}+when:1d"
        "&hl=ko"
        "&gl=KR"
        "&ceid=KR:ko"
    )

    feed = feedparser.parse(url)

    articles = []

    for entry in feed.entries[:ARTICLES_PER_TOPIC]:

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

        # HTML 특수문자 변환
        summary = html.unescape(summary)

        summary = summary.replace(
            "\xa0",
            " "
        )

        summary = summary.replace(
            "&nbsp;",
            " "
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
            "source_topic": topic

        })

    return articles


# =========================================================
# 뉴스 수집
# =========================================================

print("=" * 60)
print("STEP 1 - 다양한 분야 뉴스 수집")
print("=" * 60)

all_articles = []


for topic, queries in TOPICS.items():

    topic_count = 0

    for query in queries:

        try:

            articles = get_news(
                query,
                topic
            )

            all_articles.extend(
                articles
            )

            topic_count += len(
                articles
            )

        except Exception as e:

            print(
                topic,
                "수집 오류:",
                e
            )

    print(
        topic,
        ":",
        topic_count,
        "개"
    )


print(
    "전체:",
    len(all_articles),
    "개"
)


# =========================================================
# 제목 중복 제거
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

    seen_titles.add(
        normalized
    )

    unique_articles.append(
        article
    )


print(
    "중복 제거:",
    len(unique_articles),
    "개"
)


# =========================================================
# 분야별 후보 균등 추출
# =========================================================

balanced_candidates = []

topic_candidate_count = {}


for article in unique_articles:

    topic = article[
        "source_topic"
    ]

    current = topic_candidate_count.get(
        topic,
        0
    )

    # 한 분야가 AI 후보를 독점하지 않게
    # 분야별 최대 4개
    if current >= 4:
        continue

    balanced_candidates.append(
        article
    )

    topic_candidate_count[
        topic
    ] = current + 1


# 최대 28개
balanced_candidates = (
    balanced_candidates[:28]
)


print(
    "AI 분석 후보:",
    len(balanced_candidates),
    "개"
)


# =========================================================
# AI 전달용 기사 목록
# =========================================================

article_text = ""


for index, article in enumerate(
    balanced_candidates
):

    article_text += f"""

기사번호: {index}

사전분류:
{article["source_topic"]}

기사제목:
{article["title"]}

기사내용:
{article["summary"][:450]}

"""


# =========================================================
# AI 분석 프롬프트
# =========================================================

prompt = f"""
당신은 매일 주요 이슈를 선별하고
경제·산업적 의미를 설명하는
뉴스 분석 AI입니다.

아래 기사 후보 중
오늘 알아둘 가치가 가장 높은
뉴스 8개를 선정하세요.


=========================
가장 중요한 선정 규칙
=========================

1.
같은 사건 또는 사실상 같은 내용의 기사는
반드시 하나만 선정하세요.

2.
경제 뉴스만 많이 선정하지 마세요.

경제·금융 분야는
최대 2개까지만 선정하세요.

3.
최종 8개 뉴스에는
최소 4개 이상의 서로 다른 분야가
포함되어야 합니다.

4.
가능하면 다음 분야를 골고루 포함하세요.

경제·금융
산업
기업
AI·기술
국제
사회·문화
정책

5.
단순 사건사고나 연예인의 사생활보다는
사회 변화, 소비 트렌드, 산업 변화,
기업 활동 등에 의미가 있는 뉴스를
우선 선정하세요.

6.
단순히 제목이 자극적인 기사는
선정하지 마세요.

7.
오늘 이후 경제·산업·기업 또는
사람들의 생활에 영향을 줄 가능성이
큰 뉴스를 우선하세요.


=========================
각 뉴스 분석 방법
=========================

category:

다음 중 하나만 사용하세요.

경제·금융
산업
기업
AI·기술
국제
사회·문화
정책


importance:

1~5점으로 평가하세요.

5:
경제·산업·사회 흐름에
매우 큰 영향을 줄 수 있음

4:
시장 또는 산업에
의미 있는 영향을 줄 가능성이 높음

3:
알아둘 가치가 있는 주요 이슈

2:
참고 수준

1:
중요도가 낮음


importance_reason:

중요도 점수를 준 이유를
15자 안팎으로 짧게 작성하세요.

예:

금리·환율 동시 영향

반도체 투자 확대 신호

글로벌 공급망 영향

소비 트렌드 변화

기업 실적 영향


headline:

원문 제목을 그대로 복사하지 말고
뉴스의 핵심을 이해할 수 있는
짧은 제목으로 다시 작성하세요.


points:

기사에서 알아야 할 핵심 사실을
3개로 작성하세요.

각 항목은 짧고 구체적으로 작성하세요.


why_important:

이 뉴스가 왜 중요한지를
일반인도 이해할 수 있도록
2문장 이내로 설명하세요.

단순히

"중요한 이슈입니다"
"영향을 미칠 수 있습니다"

라고 끝내지 마세요.

반드시

원인
→ 변화
→ 한국 경제·산업·기업·생활에 미치는 영향

의 관계를 설명하세요.


예시 1:

미국 기준금리가 상승했다면

"미국 금리가 오르면 달러 자산의 매력이 높아져
원·달러 환율과 외국인 자금 흐름에 영향을 줄 수 있습니다.
이는 국내 증시와 한국은행의 금리 결정에도 부담으로 작용할 수 있습니다."


예시 2:

국제유가가 급등했다면

"유가 상승은 기업의 운송·생산비용을 높이고
소비자물가 상승으로 이어질 수 있습니다.
한국처럼 에너지 수입 의존도가 높은 국가에는
무역수지와 물가 측면에서 부담이 될 수 있습니다."


예시 3:

AI 데이터센터 투자가 확대됐다면

"데이터센터 투자가 늘면
반도체와 전력설비, 발전기, 냉각장치 등의
수요가 함께 증가할 수 있습니다.
관련 산업의 신규 수주와 설비투자로
연결될 가능성이 있다는 점에서 중요합니다."


keywords:

핵심 키워드 3개를 작성하세요.


=========================
출력
=========================

반드시 JSON만 출력하세요.

{{
  "news": [
    {{
      "article_index": 0,
      "category": "경제·금융",
      "importance": 5,
      "importance_reason": "금리·환율 동시 영향",
      "headline": "미국 기준금리 추가 인상",
      "points": [
        "미국 기준금리가 추가 인상됐습니다",
        "국채금리와 달러가 함께 강세를 보였습니다",
        "글로벌 금융시장의 금리 부담이 커졌습니다"
      ],
      "why_important": "미국 금리가 오르면 달러 자산의 매력이 높아져 원·달러 환율과 외국인 자금 흐름에 영향을 줄 수 있습니다. 이는 국내 증시와 한국은행의 금리 결정에도 부담으로 작용할 수 있습니다.",
      "keywords": [
        "미국금리",
        "환율",
        "한국은행"
      ]
    }}
  ]
}}


기사 후보:

{article_text}
"""


# =========================================================
# AI 실행
# =========================================================

print()
print("=" * 60)
print("STEP 2 - AI 핵심 이슈 분석")
print("=" * 60)


selected = []


try:

    response = client.responses.create(
        model=MODEL,
        input=prompt
    )

    raw = response.output_text.strip()

    raw = raw.replace(
        "```json",
        ""
    )

    raw = raw.replace(
        "```",
        ""
    )

    start = raw.find("{")
    end = raw.rfind("}")

    if start == -1 or end == -1:

        raise ValueError(
            "JSON 응답을 찾지 못했습니다."
        )

    data = json.loads(
        raw[start:end + 1]
    )

    selected = data.get(
        "news",
        []
    )

    print(
        "AI 분석 성공:",
        len(selected),
        "개"
    )


except Exception as e:

    print(
        "AI 분석 오류:",
        repr(e)
    )

    selected = []


# =========================================================
# AI가 8개 미만 반환했을 때 보충
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


if len(selected) < FINAL_NEWS_COUNT:

    for index, article in enumerate(
        balanced_candidates
    ):

        if index in used_indexes:
            continue

        selected.append({

            "article_index":
                index,

            "category":
                article["source_topic"],

            "importance":
                3,

            "importance_reason":
                "오늘의 주요 이슈",

            "headline":
                article["title"],

            "points": [
                article["summary"][:130]
                if article["summary"]
                else article["title"]
            ],

            "why_important":
                "오늘 주요 이슈로 선정된 뉴스입니다.",

            "keywords": [
                article["source_topic"]
            ]

        })

        used_indexes.add(index)

        if len(selected) >= FINAL_NEWS_COUNT:
            break


selected = selected[
    :FINAL_NEWS_COUNT
]


# =========================================================
# 카드 생성
# =========================================================

cards = ""

valid_count = 0


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
            article_index >= len(
                balanced_candidates
            )
        ):
            continue

        article = balanced_candidates[
            article_index
        ]

    except Exception:

        continue


    valid_count += 1


    category = html.escape(
        str(
            item.get(
                "category",
                article["source_topic"]
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


    why_important = html.escape(
        str(
            item.get(
                "why_important",
                ""
            )
        )
    )


    link = html.escape(
        article["link"]
    )


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
            html.escape(
                clean_point
            )
            +
            "</li>"
        )


    cards += f"""

    <article class="card">

        <div class="card-inner">

            <div class="card-top">

                <span class="number">
                    {valid_count:02d}
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


            <div class="why">

                <div class="why-title">
                    왜 중요한가
                </div>

                <div class="why-text">
                    {why_important}
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
# HTML 페이지
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
        repeat(
            4,
            minmax(0, 1fr)
        );

    gap: 20px;
}}


.card {{
    background: white;
    border-radius: 18px;

    box-shadow:
        0 4px 16px
        rgba(0,0,0,0.07);

    transition:
        transform 0.2s ease,
        box-shadow 0.2s ease;
}}


.card:hover {{
    transform: translateY(-4px);

    box-shadow:
        0 12px 28px
        rgba(0,0,0,0.11);
}}


.card-inner {{
    padding: 22px;

    height: 100%;

    display: flex;
    flex-direction: column;
}}


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

    margin:
        0 0 18px;
}}


.points li {{
    color: #444;

    font-size: 14px;
    line-height: 1.5;

    margin-bottom: 7px;
}}


.why {{
    background: #f6f7f8;

    border-radius: 11px;

    padding: 14px;

    margin-top: auto;
}}


.why-title {{
    font-size: 11px;

    color: #777;

    font-weight: 700;

    margin-bottom: 6px;
}}


.why-text {{
    font-size: 13px;
    line-height: 1.55;
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


@media
(max-width: 1100px) {{

    .grid {{
        grid-template-columns:
            repeat(
                2,
                minmax(0,1fr)
            );
    }}

}}


@media
(max-width: 650px) {{

    .container {{
        padding:
            28px 15px 50px;
    }}


    .header h1 {{
        font-size: 30px;
    }}


    .grid {{
        grid-template-columns:
            1fr;
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

        AI가 선별한 오늘의 주요 이슈

        &nbsp; | &nbsp;

        {today}

        &nbsp; | &nbsp;

        {valid_count} ISSUES

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
print("카드:", valid_count)
print("=" * 60)
