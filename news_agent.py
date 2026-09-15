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

FINAL_COUNT = 8
PER_QUERY = 4


# =========================================================
# 뉴스 분야
# 경제에 몰리지 않도록 분야별로 따로 수집
# =========================================================

TOPICS = {

    "경제·금융": [
        "한국 경제 금융",
        "미국 경제 금리 환율"
    ],

    "산업": [
        "조선 해운 에너지 산업",
        "자동차 배터리 산업"
    ],

    "기업": [
        "기업 투자 실적 M&A",
        "한국 기업 글로벌 투자"
    ],

    "AI·기술": [
        "AI 데이터센터 반도체",
        "인공지능 빅테크 기술"
    ],

    "국제": [
        "글로벌 국제 정세 무역",
        "미국 중국 관세 무역"
    ],

    "사회·문화": [
        "한국 사회 문화 트렌드",
        "콘텐츠 소비 문화 트렌드"
    ],

    "정책": [
        "정부 산업 정책 규제",
        "정부 기업 경제 정책"
    ]
}


client = OpenAI(
    api_key=os.environ["OPENAI_API_KEY"]
)


# =========================================================
# 뉴스 가져오기
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

    for entry in feed.entries[:PER_QUERY]:

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

        # HTML 제거
        summary = re.sub(
            r"<[^>]+>",
            " ",
            summary
        )

        summary = html.unescape(
            summary
        )

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
            "topic": topic

        })

    return articles


# =========================================================
# 뉴스 수집
# =========================================================

print("=" * 60)
print("뉴스 수집 시작")
print("=" * 60)

all_articles = []


for topic, queries in TOPICS.items():

    count = 0

    for query in queries:

        try:

            news = get_news(
                query,
                topic
            )

            all_articles.extend(
                news
            )

            count += len(news)

        except Exception as e:

            print(
                topic,
                "수집 오류:",
                e
            )

    print(
        topic,
        count,
        "개"
    )


# =========================================================
# 중복 제거
# =========================================================

unique = []
seen = set()


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

    if normalized in seen:
        continue

    seen.add(normalized)
    unique.append(article)


# =========================================================
# 분야별 후보 균등하게 만들기
# =========================================================

candidates = []

counts = {}


for article in unique:

    topic = article["topic"]

    current = counts.get(
        topic,
        0
    )

    # 분야별 후보 최대 4개
    if current >= 4:
        continue

    candidates.append(article)

    counts[topic] = current + 1


candidates = candidates[:28]


print(
    "AI 후보:",
    len(candidates)
)


# =========================================================
# AI에게 기사 전달
# =========================================================

article_text = ""


for i, article in enumerate(
    candidates
):

    article_text += f"""

기사번호: {i}

분야:
{article["topic"]}

제목:
{article["title"]}

내용:
{article["summary"][:500]}

"""


# =========================================================
# AI 분석
# =========================================================

prompt = f"""
당신은 오늘의 주요 뉴스 가운데
사람들이 알아둘 가치가 높은 이슈를 선별하는
뉴스 분석 AI입니다.

아래 기사 후보 중 정확히 8개를 선정하세요.


[선정 규칙]

경제 뉴스에 치우치지 마세요.

경제·금융은 최대 2개만 선정하세요.

최종 8개에는 반드시 최소 4개 이상의
서로 다른 분야가 포함되어야 합니다.

가능하면 다음 분야를 다양하게 선정하세요.

경제·금융
산업
기업
AI·기술
국제
사회·문화
정책


같은 사건을 다룬 기사는
하나만 선정하세요.

단순 연예인 사생활이나 단순 사건사고보다

산업 변화
기업 활동
기술 변화
사회 변화
문화·소비 트렌드
국제 정세
정책 변화

등 향후 영향을 생각해볼 수 있는
뉴스를 우선하세요.


[각 뉴스 작성 방법]


headline

원문 제목을 그대로 사용하지 말고
핵심 내용을 쉽게 이해할 수 있는
짧은 제목으로 작성하세요.


points

뉴스의 핵심 사실을
3개의 짧은 문장으로 작성하세요.


why_important

가장 중요합니다.

이 뉴스가 왜 중요한지를
일반인이 이해할 수 있도록
2~3문장으로 설명하세요.

기사 내용을 다시 요약하는 것이 아니라

"이 일이 일어나면 무엇이 변하고,
그 변화가 한국 경제·산업·기업 또는
우리 생활에 어떤 영향을 줄 수 있는가"

를 설명하세요.


예시:

미국 금리 인상

미국 금리가 오르면 달러 자산의 매력이 높아져
원·달러 환율 상승과 외국인 자금 유출 압력이
커질 수 있습니다. 이는 국내 증시뿐 아니라
한국은행의 금리 결정에도 영향을 줄 수 있습니다.


국제유가 상승

국제유가가 오르면 기업의 운송비와 생산비가
높아지고 소비자물가에도 상승 압력이 생깁니다.
에너지 수입 의존도가 높은 한국에는
무역수지 측면에서도 부담이 될 수 있습니다.


AI 데이터센터 투자

AI 데이터센터 투자가 확대되면
반도체뿐 아니라 전력설비, 발전기,
냉각장치 등의 수요도 함께 늘어날 수 있습니다.
관련 기업의 투자와 수주 기회로 이어질 수 있습니다.


문화 콘텐츠 해외 흥행

한국 콘텐츠의 해외 소비가 늘어나면
콘텐츠 제작사뿐 아니라 플랫폼, 광고,
관광과 소비재 산업에도 파급효과가 나타날 수 있습니다.


keywords

핵심 키워드 3개를 작성하세요.


category

아래 중 하나만 사용하세요.

경제·금융
산업
기업
AI·기술
국제
사회·문화
정책


[출력]

JSON만 출력하세요.

{{
    "news": [

        {{
            "article_index": 0,

            "category":
            "AI·기술",

            "headline":
            "AI 데이터센터 투자 확대",

            "points": [
                "AI 인프라 투자가 확대되고 있습니다",
                "데이터센터 건설 수요가 증가하고 있습니다",
                "반도체와 전력설비 수요도 늘어날 전망입니다"
            ],

            "why_important":
            "AI 데이터센터 투자가 확대되면 반도체뿐 아니라 전력설비와 발전기, 냉각장치 등의 수요도 함께 늘어날 수 있습니다. 관련 산업의 투자와 신규 수주 기회로 이어질 수 있다는 점에서 중요합니다.",

            "keywords": [
                "AI",
                "데이터센터",
                "반도체"
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

selected = []


try:

    print(
        "AI 분석 시작"
    )

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
            "JSON을 찾을 수 없습니다."
        )

    data = json.loads(
        raw[start:end + 1]
    )

    selected = data.get(
        "news",
        []
    )

    print(
        "AI 선정:",
        len(selected)
    )


except Exception as e:

    print(
        "AI 분석 오류:",
        repr(e)
    )

    selected = []


# =========================================================
# AI 실패 시 분야별로 골고루 보충
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


# 분야별 기본 중요 이유
DEFAULT_REASON = {

    "경제·금융":
    "금리와 환율, 금융시장의 변화는 기업의 자금조달 비용과 가계의 소비·투자에 영향을 줄 수 있습니다.",

    "산업":
    "산업 환경의 변화는 기업의 생산과 투자, 수주 및 공급망 변화로 이어질 수 있습니다.",

    "기업":
    "기업의 투자와 실적 변화는 고용과 설비투자뿐 아니라 관련 협력업체와 산업 전체에 영향을 줄 수 있습니다.",

    "AI·기술":
    "새로운 기술의 확산은 기업의 투자 방향과 생산성, 관련 산업의 수요 구조를 바꿀 수 있습니다.",

    "국제":
    "국제 정세와 무역 환경의 변화는 수출입과 환율, 글로벌 공급망을 통해 한국 기업에도 영향을 줄 수 있습니다.",

    "사회·문화":
    "사회와 소비 트렌드의 변화는 사람들이 돈을 쓰는 방식과 기업의 상품·서비스 전략을 바꿀 수 있습니다.",

    "정책":
    "정부 정책과 규제의 변화는 기업의 투자 판단과 비용, 시장 경쟁 환경에 직접적인 영향을 줄 수 있습니다."

}


# AI 결과가 부족하면 분야가 골고루 들어가게 추가
if len(selected) < FINAL_COUNT:

    selected_topics = {}


    for item in selected:

        topic = item.get(
            "category",
            ""
        )

        selected_topics[topic] = (
            selected_topics.get(
                topic,
                0
            )
            + 1
        )


    # 먼저 분야별 하나씩 채움
    for index, article in enumerate(
        candidates
    ):

        if len(selected) >= FINAL_COUNT:
            break

        if index in used_indexes:
            continue

        topic = article["topic"]

        # 경제는 최대 2개
        if (
            topic == "경제·금융"
            and
            selected_topics.get(
                topic,
                0
            ) >= 2
        ):
            continue

        # 다른 분야는 우선 1개씩
        if (
            topic != "경제·금융"
            and
            selected_topics.get(
                topic,
                0
            ) >= 1
        ):
            continue


        selected.append({

            "article_index":
            index,

            "category":
            topic,

            "headline":
            article["title"],

            "points": [
                article["summary"][:140]
                if article["summary"]
                else article["title"]
            ],

            "why_important":
            DEFAULT_REASON.get(
                topic,
                "오늘 알아둘 가치가 있는 주요 이슈입니다."
            ),

            "keywords": [
                topic
            ]

        })


        used_indexes.add(index)

        selected_topics[topic] = (
            selected_topics.get(
                topic,
                0
            )
            + 1
        )


# 아직 8개가 안 됐으면 추가
if len(selected) < FINAL_COUNT:

    for index, article in enumerate(
        candidates
    ):

        if len(selected) >= FINAL_COUNT:
            break

        if index in used_indexes:
            continue

        topic = article["topic"]

        if (
            topic == "경제·금융"
            and
            selected_topics.get(
                topic,
                0
            ) >= 2
        ):
            continue


        selected.append({

            "article_index":
            index,

            "category":
            topic,

            "headline":
            article["title"],

            "points": [
                article["summary"][:140]
                if article["summary"]
                else article["title"]
            ],

            "why_important":
            DEFAULT_REASON.get(
                topic,
                "오늘 알아둘 가치가 있는 주요 이슈입니다."
            ),

            "keywords": [
                topic
            ]

        })


        used_indexes.add(index)

        selected_topics[topic] = (
            selected_topics.get(
                topic,
                0
            )
            + 1
        )


selected = selected[:FINAL_COUNT]


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
            article_index >= len(candidates)
        ):

            continue


        article = candidates[
            article_index
        ]


    except Exception:

        continue


    valid_count += 1


    category = html.escape(
        str(
            item.get(
                "category",
                article["topic"]
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


    why = html.escape(
        str(
            item.get(
                "why_important",
                DEFAULT_REASON.get(
                    article["topic"],
                    ""
                )
            )
        )
    )


    link = html.escape(
        article["link"]
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


            <h2>
                {headline}
            </h2>


            <div class="keywords">
                {keyword_html}
            </div>


            <ul class="points">
                {points_html}
            </ul>


            <div class="why-box">

                <div class="why-title">
                    왜 중요한가
                </div>

                <div class="why-text">
                    {why}
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
# 페이지 생성
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


/* 전체 화면 회색 */

body {{

    margin: 0;

    background: #e9eaec;

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

    padding:
        45px 30px 70px;

}}


/* 상단 */

.header {{

    margin-bottom: 32px;

}}


.header-label {{

    color: #737373;

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

    color: #686868;

    font-size: 14px;

}}


/* 카드 배치 */

.grid {{

    display: grid;

    grid-template-columns:
        repeat(
            4,
            minmax(0, 1fr)
        );

    gap: 20px;

}}


/* 카드 */

.card {{

    background: #ffffff;

    border-radius: 18px;

    box-shadow:
        0 5px 18px
        rgba(0,0,0,0.08);

}}


.card-inner {{

    height: 100%;

    padding: 22px;

    display: flex;

    flex-direction: column;

}}


.card-top {{

    display: flex;

    justify-content:
        space-between;

    align-items: center;

    margin-bottom: 20px;

}}


.number {{

    color: #aaa;

    font-size: 12px;

    font-weight: 700;

}}


.category {{

    background: #f0f1f2;

    padding:
        6px 10px;

    border-radius: 20px;

    font-size: 12px;

    font-weight: 700;

}}


/* 제목 */

.card h2 {{

    margin:
        0 0 12px;

    font-size: 20px;

    line-height: 1.4;

    letter-spacing: -0.5px;

}}


/* 키워드 */

.keywords {{

    color: #777;

    font-size: 12px;

    line-height: 1.5;

    margin-bottom: 17px;

}}


/* 핵심 요약 */

.points {{

    padding-left: 19px;

    margin:
        0 0 20px;

}}


.points li {{

    color: #444;

    font-size: 14px;

    line-height: 1.55;

    margin-bottom: 7px;

}}


/* 왜 중요한가 */

.why-box {{

    background: #f3f4f5;

    border-radius: 11px;

    padding: 14px;

    margin-top: auto;

}}


.why-title {{

    color: #666;

    font-size: 11px;

    font-weight: 700;

    margin-bottom: 7px;

}}


.why-text {{

    color: #222;

    font-size: 13px;

    line-height: 1.6;

}}


/* 링크 */

.news-link {{

    display: block;

    margin-top: 16px;

    color: #111;

    font-size: 12px;

    font-weight: 700;

    text-decoration: none;

}}


.news-link:hover {{

    text-decoration: underline;

}}


/* 태블릿 */

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


/* 모바일 */

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

        AI가 선별한 오늘의 핵심 이슈

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
# index.html 생성
# =========================================================

with open(
    "index.html",
    "w",
    encoding="utf-8"
) as file:

    file.write(page)


print()
print("=" * 60)
print("사이트 생성 완료")
print("날짜:", today)
print("뉴스:", valid_count)
print("=" * 60)
