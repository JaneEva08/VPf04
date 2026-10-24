"""Тесты вспомогательных скриптов. API не нужен: запрос к модели подменяется заглушкой."""

import json
import sys
from pathlib import Path

import pytest

import check_results
import run_prompts

PROMPT = {
    "prompt_id": "demo",
    "role": "Ты редактор.",
    "context": "Резюмируй текст.",
    "structure": {"output_format": "Резюме"},
    "format": {"length": "15-25%"},
    "examples": {"example_1": {"input": "a", "expected_output": "b"}},
    "test_input": "Искусственный интеллект проникает во все сферы жизни.",
}


@pytest.fixture
def prompts_dir(tmp_path: Path) -> Path:
    d = tmp_path / "prompts"
    d.mkdir()
    (d / "01_demo.json").write_text(json.dumps(PROMPT, ensure_ascii=False), encoding="utf-8")
    return d


def test_build_system_contains_all_parts():
    system = run_prompts.build_system(PROMPT)
    for part in ("Ты редактор.", "Резюмируй текст.", "15-25%", "expected_output"):
        assert part in system


def test_load_prompts_filters_by_only(prompts_dir: Path):
    assert len(run_prompts.load_prompts(prompts_dir, None)) == 1
    assert run_prompts.load_prompts(prompts_dir, "demo")[0]["prompt_id"] == "demo"
    with pytest.raises(SystemExit):
        run_prompts.load_prompts(prompts_dir, "нет_такого")


def test_load_prompts_empty_dir_exits(tmp_path: Path):
    with pytest.raises(SystemExit):
        run_prompts.load_prompts(tmp_path, None)


def test_dry_run_does_not_call_api(prompts_dir: Path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["run_prompts.py", "--prompts-dir", str(prompts_dir), "--dry-run"])
    assert run_prompts.main() == 0
    assert "к API не обращались" in capsys.readouterr().out


def test_full_run_writes_results_and_summary(prompts_dir: Path, tmp_path: Path, monkeypatch):
    out = tmp_path / "out"
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(run_prompts, "run_one", lambda *a, **k: ("## Резюме\nтекст", 0.1, 10, 5))
    monkeypatch.setattr(sys, "argv", ["run_prompts.py", "--prompts-dir", str(prompts_dir),
                                      "--out-dir", str(out), "--temps", "0.1", "1.0", "--model", "test-model"])
    assert run_prompts.main() == 0
    assert (out / "demo_t0_1.md").exists() and (out / "demo_t1_0.md").exists()
    assert "test-model" in (out / "summary.csv").read_text(encoding="utf-8-sig")


def test_missing_key_exits(prompts_dir: Path, monkeypatch):
    for name in ("OPENAI_API_KEY", "API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(sys, "argv", ["run_prompts.py", "--prompts-dir", str(prompts_dir)])
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
    with pytest.raises(SystemExit):
        run_prompts.main()


def test_check_results_counts_words_and_format(tmp_path: Path, capsys):
    (tmp_path / "summary_t0_7.md").write_text(
        "<!-- prompt=summary -->\n\n## Заголовок\n- один два три\n", encoding="utf-8")
    (tmp_path / "code_structure_t0_1.md").write_text('{"a": "b"}', encoding="utf-8")
    assert check_results.main([str(tmp_path), "--source-words", "10"]) == 0
    out = capsys.readouterr().out
    assert "Markdown" in out and "JSON" in out
    assert "40%" in out  # 4 слова из 10 (Заголовок, один, два, три)


def test_check_results_no_files(tmp_path: Path):
    assert check_results.main([str(tmp_path)]) == 1
