from __future__ import annotations

import json
from pathlib import Path

from blocklist import Blocklist


def test_load_missing_file_is_empty(tmp_path: Path) -> None:
    bl = Blocklist(tmp_path / "missing.json")
    bl.load()
    assert bl.get(1234) == set()
    assert bl.is_blocked(1234, "makerworld") is False


def test_set_get_is_blocked_roundtrip(tmp_path: Path) -> None:
    bl = Blocklist(tmp_path / "b.json")
    bl.set(42, {"makerworld", "aliexpress"})
    assert bl.get(42) == {"makerworld", "aliexpress"}
    assert bl.is_blocked(42, "makerworld") is True
    assert bl.is_blocked(42, "yahoo_auction") is False
    assert bl.is_blocked(99, "makerworld") is False


def test_get_returns_copy(tmp_path: Path) -> None:
    bl = Blocklist(tmp_path / "b.json")
    bl.set(1, {"makerworld"})
    got = bl.get(1)
    got.add("aliexpress")
    # 外部から変更しても内部状態は変わらない
    assert bl.get(1) == {"makerworld"}


def test_set_empty_removes_guild(tmp_path: Path) -> None:
    path = tmp_path / "b.json"
    bl = Blocklist(path)
    bl.set(7, {"makerworld"})
    bl.set(7, set())
    bl.save()

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert "7" not in raw


def test_save_and_reload(tmp_path: Path) -> None:
    path = tmp_path / "b.json"
    bl = Blocklist(path)
    bl.set(100, {"makerworld"})
    bl.set(200, {"aliexpress", "yahoo_auction"})
    bl.save()

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw == {
        "100": ["makerworld"],
        "200": ["aliexpress", "yahoo_auction"],
    }

    bl2 = Blocklist(path)
    bl2.load()
    assert bl2.get(100) == {"makerworld"}
    assert bl2.get(200) == {"aliexpress", "yahoo_auction"}


def test_save_creates_parent_dir(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "dir" / "b.json"
    bl = Blocklist(path)
    bl.set(1, {"makerworld"})
    bl.save()
    assert path.exists()


def test_save_is_atomic_via_tmp_rename(tmp_path: Path) -> None:
    path = tmp_path / "b.json"
    bl = Blocklist(path)
    bl.set(1, {"makerworld"})
    bl.save()
    # tmp ファイルが残っていないこと
    assert not path.with_suffix(path.suffix + ".tmp").exists()
    # 通常の JSON として読める
    assert json.loads(path.read_text(encoding="utf-8")) == {"1": ["makerworld"]}


def test_load_invalid_json_falls_back_to_empty(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("not json {{{", encoding="utf-8")
    bl = Blocklist(path)
    bl.load()
    assert bl.get(1) == set()


def test_load_non_object_falls_back_to_empty(tmp_path: Path) -> None:
    path = tmp_path / "arr.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    bl = Blocklist(path)
    bl.load()
    assert bl.get(1) == set()


def test_load_skips_invalid_entries(tmp_path: Path) -> None:
    path = tmp_path / "mixed.json"
    path.write_text(
        json.dumps(
            {
                "1": ["makerworld"],
                "not-an-int": ["should-be-skipped"],
                "2": "not-a-list",
                "3": ["aliexpress", "yahoo_auction"],
            }
        ),
        encoding="utf-8",
    )
    bl = Blocklist(path)
    bl.load()
    assert bl.get(1) == {"makerworld"}
    assert bl.get(2) == set()
    assert bl.get(3) == {"aliexpress", "yahoo_auction"}
