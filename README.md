# VPf04 — тестирование кейс-промптов

Домашнее задание курса «Профессия вайб-кодер», модуль 7, урок VPf04 «Кейсы промптов». Скрипт прогоняет три промпта из урока (Summary, Code Structure, Task Planning) на разных температурах и сохраняет ответы в файлы. Отчёт — в [HOMEWORK.md](HOMEWORK.md).

## Пример результата

| Промпт | Модель | T | Формат | Слов |
|---|---|---|---|---|
| summary | gpt-6-luna | 0.7 | Markdown | 142 |
| code_structure | gpt-6-luna | 0.7 | JSON | 1433 |
| task_planning | gpt-6-luna | 1.0 | JSON | 1878 |
| task_planning | gpt-6-astra | 0.7 | Markdown | 1849 |

## Запуск

```powershell
python -m pip install -r requirements.txt
copy .env.example .env        # впишите OPENAI_API_KEY
# положите рядом три JSON-промпта из урока (в репозитории их нет: материалы курса)
python run_prompts.py --prompts-dir . --dry-run
python run_prompts.py --prompts-dir .
python check_results.py results results_astra
python -m pytest -q
```

## Структура

| Путь | Что это |
|---|---|
| `run_prompts.py` | прогон промптов по температурам, сохранение ответов и сводки |
| `check_results.py` | проверка сохранённых ответов: формат, объём, доля Summary от исходника |
| `test_run_prompts.py` | тесты (без обращения к API) |
| `results/`, `results_astra/` | ответы моделей и `summary.md` / `summary.csv` |
| `docs/screenshots/` | скриншоты запуска |
| `HOMEWORK.md` | отчёт для куратора |
