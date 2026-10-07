# Naver Pay Stock Discussion Crawler Design

## 1. 목표

네이버페이 증권 모바일 종목 토론 페이지의 게시물을 수집한다.

대상 페이지 예시:

```text
https://m.stock.naver.com/domestic/stock/066570/discussion
?domesticStockExchange=KRX
&filter=excludeNews
```

HTML을 직접 파싱하지 않고, 페이지가 내부적으로 호출하는 JSON API를 직접 호출하는 방식으로 구현한다.

---

## 2. 기본 원칙

- 입력값은 `종목코드(stock_code)`를 기준으로 한다.
- 게시글 목록은 내부 JSON API에서 수집한다.
- `filter=excludeNews`를 기본값으로 사용한다.
- 무한 스크롤을 고려하여 pagination을 지원한다.
- API endpoint 및 pagination 키는 변경 가능성이 있으므로 설정값으로 분리한다.
- HTTP 클라이언트는 `httpx`를 사용한다.
- 브라우저 자동화(Selenium/Playwright)는 기본 구현에 사용하지 않는다.

---

## 3. 입력

크롤러 외부 인터페이스는 다음 값을 받는다.

| 항목 | 기본값 | 설명 |
|---|---:|---|
| `stock_code` | 필수 | 종목코드 |
| `filter` | `excludeNews` | 게시글 필터 |
| `exchange` | `KRX` | 거래소 구분 |
| `max_pages` | `None` | 최대 조회 페이지 수 |

지원 필터:

```text
excludeNews
all
```

외부에서는 가능하면 하나의 함수 호출만으로 게시글을 가져올 수 있도록 한다.

```python
posts = crawl_discussions("066570")
```

---

## 4. API 호출 구조

현재 페이지는 초기 HTML에 게시글 목록을 직접 포함하지 않고, 클라이언트에서 별도 JSON API를 호출하여 게시글을 렌더링한다.

크롤러 동작 흐름:

```text
stock_code
    ↓
discussion list API 호출
    ↓
JSON 응답
    ↓
게시글 normalize
    ↓
pagination 값 추출
    ↓
다음 요청
    ↓
종료 조건까지 반복
```

실제 endpoint는 브라우저 DevTools의 `Network > Fetch/XHR`에서 확인한 값을 사용한다.

API 경로는 코드 여러 곳에 하드코딩하지 않고 설정값으로 관리한다.

---

## 5. 요청 파라미터

현재 페이지에서 확인된 주요 개념 파라미터:

```text
stockCode
filter
domesticStockExchange
pagination
```

pagination 관련 실제 키는 DevTools에서 확정해야 한다.

가능한 형태:

```text
cursor
lastArticleId
rsno
page
offset
```

요청 파라미터 조립 로직과 pagination 로직은 분리한다.

---

## 6. Pagination 설계

페이지가 무한 스크롤 방식이므로 반복 조회 구조로 구현한다.

기본 흐름:

```text
cursor 없음
    ↓
첫 페이지 요청
    ↓
게시글 추출
    ↓
next cursor 추출
    ↓
다음 페이지 요청
    ↓
반복
```

pagination 방식이 변경되더라도 전체 크롤러를 수정하지 않도록 다음 책임을 별도 함수로 분리한다.

```text
extract_next_cursor(response)
```

---

## 7. 게시글 데이터 모델

내부 API 응답은 아래 공통 구조로 정규화한다.

| 필드 | 설명 |
|---|---|
| `article_id` | 게시글 고유 ID |
| `stock_code` | 종목코드 |
| `title` | 제목 |
| `content` | 본문 |
| `author` | 작성자 |
| `created_at` | 작성일시 |
| `comment_count` | 댓글 수 |
| `like_count` | 추천 수 |
| `dislike_count` | 비추천 수 |

실제 JSON key 이름은 API 응답 확인 후 mapping 한다.

CSV 파일 출력은 게시글 데이터 중 `stock_code`를 제외하고 `article_id`,
`created_at`, `title`, `content` 열을 저장한다. 종목 코드는 조회 입력 및
게시글 내부 데이터에는 유지되지만 CSV 행에는 반복 기록하지 않는다.

---

## 8. 중복 처리

게시글의 숫자형 `articleId`를 우선 고유 식별자로 사용한다.

권장 키:

```text
article_id
```

보수적으로 관리할 경우:

```text
(stock_code, article_id)
```

이미 처리한 게시글 ID는 다시 저장하지 않는다.

---

## 9. HTTP 처리

HTTP 클라이언트는 `httpx.Client`를 사용한다.

권장 설정:

```text
- Session 유지
- timeout 설정
- 공통 headers 설정
- redirect 허용 여부 명시
- 연결 재사용
```

권장 헤더:

```text
User-Agent
Referer
```

`Referer`는 해당 종목의 discussion 페이지를 사용한다.

로그인 쿠키나 인증정보가 필요하지 않은 공개 목록 조회를 기본 대상으로 한다.

비동기 수집이 필요해질 경우 구조를 크게 바꾸지 않고 `httpx.AsyncClient`로 전환할 수 있도록 한다.

---

## 10. 요청 제한

과도한 요청을 피하기 위해 요청 사이에 간격을 둔다.

권장 간격:

```text
0.5 ~ 1.5초
```

HTTP 오류 발생 시 무한 재시도하지 않는다.

권장 재시도:

```text
최대 3회
1초 → 2초 → 4초
```

429 또는 일시적 5xx 응답은 재시도 대상으로 보고, 반복 실패 시 수집을 중단하거나 해당 요청을 기록한다.

---

## 11. 종료 조건

다음 중 하나를 만족하면 수집을 종료한다.

```text
- 게시글 목록이 비어 있음
- next cursor가 없음
- 이전 cursor와 동일한 cursor 반환
- 이미 처리한 게시글만 반환
- max_pages 도달
- 연속 요청 실패
```

cursor 중복 검사를 포함하여 무한루프를 방지한다.

---

## 12. 모듈 구조

간결하게 유지하기 위해 다음 정도로 구성한다.

```text
crawler/
├─ naver_discussion.py
└─ config.py
```

### config.py

관리 항목:

```text
API URL
기본 filter
기본 exchange
timeout
retry
request interval
pagination key
JSON path
field mapping
```

### naver_discussion.py

주요 책임:

```text
crawl_discussions()
fetch_page()
extract_posts()
extract_next_cursor()
normalize_post()
```

---

## 13. 실제 API 확인 시 필요한 항목

브라우저 DevTools에서 다음 두 요청만 확보하면 구현에 필요한 구조를 대부분 확정할 수 있다.

```text
1. 토론 페이지 최초 로딩 시 발생하는 게시글 목록 XHR
2. 아래로 스크롤하여 다음 목록을 불러올 때 발생하는 XHR
```

두 요청을 비교하여 다음 값을 확정한다.

```text
- 실제 API endpoint
- HTTP method
- stock code 파라미터명
- filter 전달 방식
- exchange 전달 여부
- 페이지 크기
- pagination key
- next cursor 위치
- 게시글 배열 JSON 경로
- article ID key
- 제목/본문/작성자/작성시간 key
- 추천/비추천/댓글 수 key
```

---

## 14. 변경 대응

네이버페이 증권 내부 API는 공식 공개 API가 아니므로 변경 가능성이 있다.

따라서 다음 항목은 반드시 설정 또는 mapping 영역으로 분리한다.

```text
API_URL
POST_LIST_JSON_PATH
PAGINATION_KEY
NEXT_CURSOR_JSON_PATH
POST_FIELD_MAPPING
```

API 응답 구조가 바뀌면 크롤링 전체 로직을 수정하지 않고 설정 및 mapping 부분만 변경하도록 한다.

---

## 15. 최종 흐름

```text
crawl_discussions("066570")
        ↓
httpx로 API 요청
        ↓
게시글 JSON 추출
        ↓
공통 데이터 구조로 normalize
        ↓
article_id 기준 중복 제거
        ↓
next cursor 추출
        ↓
다음 API 요청
        ↓
종료 조건까지 반복
        ↓
게시글 목록 반환
```

이 구조를 기준으로 구현하며, 실제 endpoint와 JSON key는 DevTools에서 최신 요청을 확인한 뒤 확정한다.
