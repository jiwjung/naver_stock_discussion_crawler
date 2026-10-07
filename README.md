# 네이버페이 증권 종목 토론 크롤러

종목코드를 지정해 네이버페이 증권 모바일 종목 토론 게시판의 공개 게시글을 수집합니다. 페이지 HTML을 파싱하지 않고 내부 JSON API를 호출합니다.

## 사용법

인자 없이 실행하면 종목코드와 필터, 페이지 수, 출력 형식을 차례로 입력하는 대화형 메뉴가 표시됩니다. 

기본값을 사용하려면 Enter를 누르세요. 

결과는 프로젝트 내 `output` 폴더에 종목코드와 형식에 맞는 파일명으로 저장되며, 동시에 표준 출력에도 표시됩니다.

```bash
python -m pip install -r requirements.txt  // 의존성 설치
python start.py
```

기본 CSV 형식으로 파일에 저장하고 표준 출력에도 표시:

```bash
python start.py 066570
```

페이지 수를 제한하거나 뉴스 게시글을 포함:

```bash
python start.py 066570 --max-pages 3
python start.py 066570 --filter all --exchange KRX --max-pages 2
```

CSV 파일로 저장 (기본 형식):

```bash
python start.py 066570 --format csv --output discussions.csv
```

JSON 형식이 필요한 경우:

```bash
python start.py 066570 --format json --output discussions.json
```

옵션 전체는 다음 명령으로 확인할 수 있습니다.

```bash
python start.py --help
```

| 옵션 | 기본값 | 설명 |
|---|---|---|
| `stock_code` | 필수 | 종목코드 (예: `066570`) |
| `--filter` | `excludeNews` | `excludeNews` 또는 `all` |
| `--exchange` | `KRX` | 거래소 구분 |
| `--max-pages` | 제한 없음 | 조회할 최대 페이지 수 |
| `--format` | `csv` | 출력 형식 (`csv`, `json`) |
| `-o`, `--output` | `output/<종목코드>.<형식>` | 결과 파일 경로 |

수집 결과에는 `stock_code`, `article_id`, `created_at`, `title`, `content` 필드가 포함됩니다. 

CSV가 기본 형식이며 파일에는 `stock_code`를 제외한 `article_id`, `created_at`, `title`, `content` 열로 저장됩니다. 

표준 출력에서는 CSV 결과를 읽기 쉬운 게시글별 형식으로 표시합니다. JSON은 `--format json`으로 선택할 수 있으며, 파일에는 JSON으로 저장되고 표준 출력에도 JSON으로 표시됩니다. 

수집 건수와 오류 메시지는 표준 오류로 출력됩니다.

## Python에서 사용

```python
from crawler import crawl_discussions

posts = crawl_discussions("066570", max_pages=2)
print(posts[0] if posts else "게시물이 없습니다")
```

## 참고

네이버 토론 목록 API는 공식 공개 API가 아니며 변경될 수 있습니다. 

API 주소와 요청 파라미터, JSON 응답 경로 및 필드 매핑은 `crawler/config.py`에서 관리합니다. 
