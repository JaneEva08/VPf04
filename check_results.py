"""check_results.py — проверка сохранённых ответов: формат, объём, доля Summary от исходного текста.

Ничего не отправляет в API, читает только файлы из results/ и results_astra/.

Пример:
    python check_results.py results results_astra
    python check_results.py results --source-words 99
"""

import argparse
import json
import re
import sys
from pathlib import Path

# Слов в test_input Summary-промпта (считалось тем же способом, что и ответы).
SOURCE_WORDS = 99


def strip_header(text: str) -> str:
    """Убирает служебный HTML-комментарий с параметрами запуска в начале файла."""
    return re.sub(r"^<!--.*?-->\s*", "", text, flags=re.S)


def count_words(text: str) -> int:
    """Считает слова, а не знаки разметки (##, -, *)."""
    return len(re.findall(r"[\w][\w\-–]*", text))


def detect_format(body: str) -> str:
    try:
        json.loads(body)
        return "JSON"
    except json.JSONDecodeError:
        return "Markdown"


def parse_name(path: Path) -> tuple[str, str]:
    """summary_t0_7.md -> ('summary', '0.7')."""
    m = re.match(r"(?P<prompt>.+)_t(?P<t>\d+_\d+)\.md$", path.name)
    if not m:
        return path.stem, "?"
    return m["prompt"], m["t"].replace("_", ".")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Проверка сохранённых ответов моделей")
    ap.add_argument("dirs", nargs="+", help="папки с результатами, например results results_astra")
    ap.add_argument("--source-words", type=int, default=SOURCE_WORDS,
                    help="сколько слов в исходном тексте Summary (по умолчанию 99)")
    args = ap.parse_args(argv)

    found = False
    print(f"{'папка':<14}{'промпт':<16}{'T':<5}{'формат':<10}{'слов':>6}  доля от исходника (Summary)")
    for d in args.dirs:
        files = sorted(Path(d).glob("*_t*.md"))
        for f in files:
            found = True
            body = strip_header(f.read_text(encoding="utf-8"))
            prompt, temp = parse_name(f)
            words = count_words(body)
            share = f"{words / args.source_words:.0%}" if prompt == "summary" else ""
            print(f"{Path(d).name:<14}{prompt:<16}{temp:<5}{detect_format(body):<10}{words:>6}  {share}")
    if not found:
        print("Файлов *_t*.md не найдено. Проверьте путь к папке.", file=sys.stderr)
        return 1
    print(f"\nЛимит промпта Summary: 15–25% от исходных {args.source_words} слов "
          f"= {round(args.source_words * 0.15)}–{round(args.source_words * 0.25)} слов.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
