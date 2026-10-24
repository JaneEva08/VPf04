"""run_prompts.py — прогон кейс-промптов из урока VPf04 на разных температурах.

Берёт JSON-промпты из папки prompts/, собирает из них системное сообщение
(роль, контекст, структура, формат, примеры), в качестве запроса отправляет
поле test_input и сохраняет ответы в results/.

Примеры:
    python run_prompts.py --dry-run          # проверить, что JSON читаются, без обращения к API
    python run_prompts.py                    # все промпты x температуры 0.1, 0.7, 1.0
    python run_prompts.py --only summary     # только один промпт (по prompt_id)
    python run_prompts.py --temps 0.7        # только одна температура
    python run_prompts.py --model gpt-6-astra --temps 0.7 --out-dir results_astra
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path


def build_system(p: dict) -> str:
    """Собирает системное сообщение из полей промпта."""
    parts = []
    if p.get("role"):
        parts.append(f"РОЛЬ:\n{p['role']}")
    if p.get("context"):
        parts.append(f"КОНТЕКСТ:\n{p['context']}")
    sections = (
        ("structure", "СТРУКТУРА ОТВЕТА"),
        ("format", "ФОРМАТ ВЫВОДА"),
        ("examples", "ПРИМЕРЫ ЗАПРОСОВ И ОЖИДАЕМЫХ РЕЗУЛЬТАТОВ"),
    )
    for key, title in sections:
        if p.get(key):
            parts.append(f"{title}:\n{json.dumps(p[key], ensure_ascii=False, indent=2)}")
    return "\n\n".join(parts)


def load_prompts(prompts_dir: Path, only: str | None) -> list[dict]:
    files = sorted(prompts_dir.glob("*.json"))
    if not files:
        sys.exit(f"В папке {prompts_dir} нет JSON-файлов. Положите туда три промпта из урока.")
    result = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            sys.exit(f"Файл {f.name} не читается как JSON: {e}")
        data["_file"] = f.name
        data.setdefault("prompt_id", f.stem)
        if only and only not in (data["prompt_id"], f.stem):
            continue
        result.append(data)
    if not result:
        sys.exit(f"Промпт «{only}» не найден. Доступные: {[f.stem for f in files]}")
    return result


def run_one(client, model: str, system: str, user: str, temperature: float):
    started = time.time()
    resp = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    elapsed = time.time() - started
    text = resp.choices[0].message.content or ""
    usage = getattr(resp, "usage", None)
    return (
        text,
        elapsed,
        getattr(usage, "prompt_tokens", None),
        getattr(usage, "completion_tokens", None),
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Прогон кейс-промптов на разных температурах")
    ap.add_argument("--prompts-dir", default="prompts", help="папка с JSON-промптами")
    ap.add_argument("--out-dir", default="results", help="куда сохранять ответы")
    ap.add_argument("--temps", nargs="+", type=float, default=[0.1, 0.7, 1.0])
    ap.add_argument("--model", help="модель (по умолчанию AI_MODEL из .env, иначе gpt-6-luna)")
    ap.add_argument("--only", help="prompt_id или имя файла без .json")
    ap.add_argument("--input", help="свой текст запроса вместо test_input")
    ap.add_argument("--dry-run", action="store_true", help="ничего не отправлять, только проверить сборку")
    args = ap.parse_args()

    prompts = load_prompts(Path(args.prompts_dir), args.only)

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    # Имена переменных как в .env.example; старые API_KEY / BASE_URL / MODEL тоже работают.
    # Приоритет модели: флаг --model, затем AI_MODEL, затем MODEL, затем gpt-6-luna.
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL") or os.getenv("BASE_URL")
    model = args.model or os.getenv("AI_MODEL") or os.getenv("MODEL") or "gpt-6-luna"

    if args.dry_run:
        for p in prompts:
            system = build_system(p)
            user = args.input or p.get("test_input", "")
            print(f"=== {p['_file']} (prompt_id={p['prompt_id']}) ===")
            print(f"system: {len(system)} знаков, запрос: {len(user)} знаков")
            print(f"запрос начинается так: {user[:120]!r}")
            if not user:
                print("ВНИМАНИЕ: в файле нет test_input, передайте --input")
        print("Dry-run завершён, к API не обращались.")
        return 0

    if not api_key:
        sys.exit("Не задан OPENAI_API_KEY. Создайте .env (см. .env.example) и впишите ключ.")

    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url=base_url or None, timeout=180, max_retries=1)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []

    for p in prompts:
        system = build_system(p)
        user = args.input or p.get("test_input", "")
        if not user:
            print(f"[пропуск] {p['_file']}: нет test_input, используйте --input")
            continue
        for t in args.temps:
            label = f"{p['prompt_id']} @ T={t}"
            print(f"-> {label} ...", flush=True)
            row = {"prompt": p["prompt_id"], "temperature": t, "model": model}
            try:
                text, sec, tin, tout = run_one(client, model, system, user, t)
                status = "ok" if text.strip() else "ПУСТОЙ ОТВЕТ"
                row.update(status=status, seconds=round(sec, 1), tokens_in=tin,
                           tokens_out=tout, chars=len(text))
                name = f"{p['prompt_id']}_t{str(t).replace('.', '_')}.md"
                header = (
                    f"<!-- prompt={p['prompt_id']} model={model} temperature={t} "
                    f"time={datetime.now():%Y-%m-%d %H:%M} -->\n\n"
                )
                (out_dir / name).write_text(header + text, encoding="utf-8")
                row["file"] = name
                print(f"   {status}, {row['seconds']} с, {len(text)} знаков -> {name}")
            except Exception as e:  # noqa: BLE001 — показываем любую ошибку API и идём дальше
                row.update(status=f"ОШИБКА: {type(e).__name__}: {str(e)[:120]}")
                print(f"   {row['status']}")
            rows.append(row)

    if rows:
        fields = ["prompt", "temperature", "model", "status", "seconds",
                  "tokens_in", "tokens_out", "chars", "file"]
        with open(out_dir / "summary.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
        lines = ["| Промпт | T | Статус | Время, с | Токены вх/исх | Знаков |",
                 "|---|---|---|---|---|---|"]
        for r in rows:
            lines.append(f"| {r['prompt']} | {r['temperature']} | {r['status']} | "
                         f"{r.get('seconds', '')} | {r.get('tokens_in', '')}/{r.get('tokens_out', '')} | "
                         f"{r.get('chars', '')} |")
        (out_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"\nСводка: {out_dir / 'summary.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
