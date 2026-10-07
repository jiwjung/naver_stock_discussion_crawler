"""Command-line entry point for the discussion crawler."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Sequence

from crawler import crawl_discussions
from crawler.config import DEFAULT_CONFIG

OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="네이버페이 증권 종목 토론 게시글을 수집합니다.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("stock_code", help="종목코드 (예: 066570)")
    parser.add_argument(
        "--filter",
        choices=("excludeNews", "all"),
        default=DEFAULT_CONFIG.default_filter,
        help="게시글 필터",
    )
    parser.add_argument(
        "--exchange", default=DEFAULT_CONFIG.default_exchange, help="거래소 구분"
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=20,
        help="최대 조회 페이지 수 (한 번에 최대 20페이지)",
    )
    parser.add_argument(
        "--format", choices=("json", "csv"), default="csv", help="출력 형식"
    )
    parser.add_argument(
        "-o", "--output", type=Path,
        help="출력 파일 경로 (기본값: 프로젝트 output 폴더)",
    )
    return parser


def _write_json(posts: list[dict], stream) -> None:
    json.dump(posts, stream, ensure_ascii=False, indent=2)
    stream.write("\n")


def _write_csv(posts: list[dict], stream) -> None:
    fields = ["article_id", "created_at", "title", "content"]
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(posts)


def _write_readable_posts(posts: list[dict], stream) -> None:
    """Print CSV results as readable post cards when sending them to stdout."""
    labels = (
        ("stock_code", "종목코드"),
        ("article_id", "게시글 ID"),
        ("title", "제목"),
        ("created_at", "작성일"),
    )
    for index, post in enumerate(posts, start=1):
        stream.write(f"[{index}] " + " | ".join(
            f"{label}: {post.get(field, '')}" for field, label in labels[:2]
        ) + "\n")
        stream.write(f"작성일: {post.get('created_at', '')}\n")
        stream.write(f"제목: {post.get('title', '')}\n")
        stream.write("내용:\n")
        content = str(post.get("content", ""))
        stream.write(content + "\n")
        if index < len(posts):
            stream.write("-" * 80 + "\n")


def _prompt_interactive() -> list[str]:
    """Ask for crawler options when the program is started without arguments."""
    print("네이버페이 증권 종목 토론 크롤러")
    print("수집할 종목과 출력 옵션을 입력해 주세요. 기본값은 Enter로 선택합니다.\n")

    while True:
        stock_code = input("종목코드 (예: 066570): ").strip()
        if stock_code:
            break
        print("종목코드를 입력해 주세요.")

    while True:
        selected_filter = input(
            "게시글 필터 [1: 뉴스 제외, 2: 전체] (기본 1): "
        ).strip().lower()
        if selected_filter in ("", "1", "excludenews"):
            selected_filter = "excludeNews"
            break
        if selected_filter in ("2", "all"):
            selected_filter = "all"
            break
        print("1 또는 2를 입력해 주세요.")

    exchange = input("거래소 [KRX] (기본 KRX): ").strip() or "KRX"

    while True:
        page_input = input("최대 페이지 수 (0~20, 기본 20): ").strip()
        if not page_input:
            max_pages = 20
            break
        try:
            max_pages = int(page_input)
            if not 0 <= max_pages <= 20:
                raise ValueError
            break
        except ValueError:
            print("0~20 사이의 정수를 입력하거나 Enter를 눌러 주세요.")

    while True:
        output_format = input("저장 형식 [1: CSV, 2: JSON] (기본 1): ").strip().lower()
        if output_format in ("", "1", "csv"):
            output_format = "csv"
            break
        if output_format in ("2", "json"):
            output_format = "json"
            break
        print("1 또는 2를 입력해 주세요.")

    args = [stock_code, "--filter", selected_filter, "--exchange", exchange,
            "--format", output_format]
    if max_pages is not None:
        args.extend(("--max-pages", str(max_pages)))
    output_path = OUTPUT_DIR / f"{stock_code}.{output_format}"
    args.extend(("--output", str(output_path)))
    return args


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    provided_args = list(sys.argv[1:] if argv is None else argv)
    interactive = not provided_args
    try:
        if interactive:
            provided_args = _prompt_interactive()
    except (EOFError, KeyboardInterrupt):
        print("\n입력이 취소되었습니다.", file=sys.stderr)
        return 130

    args = parser.parse_args(provided_args)
    if args.max_pages < 0 or args.max_pages > 20:
        parser.error("--max-pages는 0~20 사이여야 합니다")
    if args.output is None:
        args.output = OUTPUT_DIR / f"{args.stock_code}.{args.format}"

    try:
        posts = crawl_discussions(
            args.stock_code,
            filter=args.filter,
            exchange=args.exchange,
            max_pages=args.max_pages,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", encoding="utf-8", newline="") as stream:
            (_write_json if args.format == "json" else _write_csv)(posts, stream)

        if args.format == "csv":
            _write_readable_posts(posts, sys.stdout)
        else:
            _write_json(posts, sys.stdout)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"수집 실패: {exc}", file=sys.stderr)
        return 1

    print(
        f"{len(posts)}개 게시글을 수집했습니다. 파일 저장: {args.output} / 표준 출력 완료",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
