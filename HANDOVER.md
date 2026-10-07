# 개발 인수인계

## 프로젝트 개요

네이버페이 증권 모바일 종목 토론 게시판의 공개 게시글을 JSON API로 수집하는 Python 프로젝트입니다. 브라우저 자동화나 HTML 파싱은 사용하지 않습니다.

## 현재 기능

- 종목 코드별 게시글 조회
- `excludeNews` 및 `all` 필터 지원
- KRX 거래소 기본 지원
- offset 기반 페이지네이션, 게시글 중복 제거 및 최대 페이지 제한
- JSON 또는 CSV 파일 저장과 표준 출력 동시 제공
- 기본 저장 위치는 프로젝트의 `output/<종목코드>.<형식>`이며, 폴더가 없으면 자동 생성
- CSV 파일 컬럼 순서는 `article_id`, `created_at`, `title`, `content`이며, 종목코드는 CSV 파일에 저장하지 않음; CSV 표준 출력은 게시글별 읽기 쉬운 형식
- 대화형 실행에서는 저장 형식까지 입력하며 경로는 묻지 않음
- 연결 재사용, timeout, 요청 간격, 일시 오류 재시도

## 파일 구성

```text
.
├── DESIGN.md                       # 설계 원문
├── HANDOVER.md                     # 본 인수인계 문서
├── README.md                       # 설치 및 사용자 안내
├── requirements.txt                # Python 의존성
├── start.py                        # CLI 진입점
└── crawler/
    ├── __init__.py
    ├── config.py                   # API 주소, 파라미터, 경로, 필드 매핑
    └── naver_discussion.py         # 요청, 정규화, pagination, 중복 제거
```

## 환경 준비 및 실행

```bash
conda activate crawler
python -m pip install -r requirements.txt
python start.py --help
python start.py 066570 --max-pages 2
python start.py 066570 --format csv
python start.py 066570 --format json --output discussions.json
```

`--output`을 생략하면 `output/<종목코드>.<형식>`에 저장하고, 결과도 표준 출력에 표시합니다. `--output`을 지정하면 해당 경로에 저장하며 동일하게 표준 출력에도 표시합니다. CSV 표준 출력은 종목코드와 게시글 ID, 작성일, 제목, 내용을 게시글 카드로 출력하고, CSV 파일에는 종목코드 없이 `article_id`, `created_at`, `title`, `content` 열을 저장합니다. JSON은 파일과 표준 출력 모두 JSON 형식입니다.

Python 코드에서는 다음처럼 호출할 수 있습니다.

```python
from crawler import crawl_discussions

posts = crawl_discussions("066570", filter="excludeNews", max_pages=2)
```

## 실제 API 정보

현재 확인된 목록 endpoint:

```text
https://m.stock.naver.com/front-api/discussion/list
```

확인된 요청 파라미터:

| 의미 | 키 | 현재 설정 |
|---|---|---|
| 종목 코드 | `itemCode` | 함수 입력값 |
| 게시글 필터 | `filter` | `excludeNews` |
| 거래소 | `domesticStockExchange` | `KRX` |
| 게시판 종류 | `discussionType` | `domesticStock` |
| 페이지 크기 | `pageSize` | 20 |
| pagination cursor | `offset` | 최초 요청은 `-9223372036854775807` |

응답의 게시글 배열 경로는 `result.posts`, 다음 cursor는 `result.lastOffset`입니다. API는 페이지에서 돌아온 `lastOffset`을 다음 `offset`으로 받는 동작을 실제 요청 두 번으로 확인했습니다.

확인된 주요 게시글 필드: `id`, `title`, `contentSwReplaced`, `writer.nickname`, `writtenAt`, `recommendCount`, `notRecommendCount`. 현재 목록 응답에서 댓글 수 필드는 확인되지 않아 `comment_count`는 `None`일 수 있습니다.

## 설정과 변경 대응

API 관련 상수는 `crawler/config.py`의 `CrawlerConfig`에 모여 있습니다. endpoint 변경 시 `api_url`, 요청 키 변경 시 관련 `*_param` 필드, response 변경 시 JSON 경로와 `post_field_mapping`을 확인하십시오. 새 요청 형식은 브라우저 DevTools의 Network 탭에서 최신 토론 목록 요청을 확인한 뒤 실제 응답으로 검증해야 합니다.

API URL은 `NAVER_STOCK_DISCUSSION_API_URL` 환경변수로 덮어쓸 수 있습니다. 요청/응답의 다른 설정값은 `CrawlerConfig`를 생성해 `crawl_discussions(..., config=...)`으로 전달할 수 있습니다.

## 검증 이력

- `crawler` conda 환경에 `httpx 0.28.1` 설치
- `python -m compileall -q start.py crawler` 통과
- 실제 `066570` 게시판에서 2페이지, 6개 수집 확인
- CLI에서 `066570 --max-pages 1` 실행 시 20개 수집 및 JSON 파싱 확인
- 실제 `005930` 종목 2페이지 수집: 40개 게시글을 `output/005930.csv`에 저장하고 종목코드, 필수 컬럼 및 `article_id`/`title` 누락 여부 확인
- 기본 저장 경로 자동 선택, CSV 파일 생성, 표준 출력 동시 표시 검증

네이버의 비공개 내부 API는 예고 없이 변경될 수 있습니다. 네트워크 오류, HTTP 오류 또는 게시글이 비어 나오는 경우 우선 endpoint와 요청 파라미터, response 필드가 현재 브라우저 요청과 일치하는지 확인하십시오.
