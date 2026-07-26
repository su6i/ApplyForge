"""
test_apply_tracker.py — apply_tracker package contract tests (post wo-applyforge-0007 move).

Runnable two ways (pytest is optional in this repo):
    .venv/bin/python tests/test_apply_tracker.py     # plain-python self-runner
    pytest tests/test_apply_tracker.py               # if pytest is installed

Covers pure-logic modules only (tracker, db, service, sources) with tmp
directories — no real vault, no Gmail credentials, no network.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow running directly (python tests/test_apply_tracker.py) from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.apply_tracker import db, tracker, service, sources


# ── tracker.py ────────────────────────────────────────────────────────────────

def test_parse_deadline_dd_mm_yyyy():
    assert tracker._parse_deadline("07/06/2026") == "2026-06-07"


def test_parse_deadline_iso():
    assert tracker._parse_deadline("2026-06-07") == "2026-06-07"


def test_parse_deadline_month_year_fr():
    assert tracker._parse_deadline("Juillet 2026") == "2026-07-01"


def test_parse_deadline_day_month_year_fr():
    assert tracker._parse_deadline("le 9 juin 2026") == "2026-06-09"


def test_parse_deadline_unparseable_returns_none():
    assert tracker._parse_deadline("En continu") is None


def test_days_left_none_when_no_deadline():
    assert tracker.days_left(None) is None


def test_days_left_computes_delta():
    from datetime import date, timedelta
    future = (date.today() + timedelta(days=10)).isoformat()
    assert tracker.days_left(future) == 10


def test_parse_position_md_extracts_table_fields(tmp_path):
    md = tmp_path / "FR_test_position.md"
    md.write_text(
        "# Great AI Position\n\n"
        "| **Deadline** | 07/06/2026 |\n"
        "| **Fit** | 8/10 |\n"
        "| **Institution** | Inria the posting's city |\n"
        "| **Pays** | France |\n"
    )
    info = tracker.parse_position_md(md)
    assert info["title"] == "Great AI Position"
    assert info["deadline"] == "2026-06-07"
    assert info["fit"] == "8/10"
    assert info["institution"] == "Inria the posting's city"
    assert info["country"] == "France"


def test_load_save_tracking_roundtrip(tmp_path):
    tracker.save_tracking(tmp_path, {"pos1": {"status": "found"}})
    assert tracker.load_tracking(tmp_path) == {"pos1": {"status": "found"}}


def test_update_entry_sets_status(tmp_path):
    entry = tracker.update_entry(tmp_path, "pos1", status="sent", sent_date="2026-07-01")
    assert entry["status"] == "sent"
    assert tracker.load_tracking(tmp_path)["pos1"]["status"] == "sent"


def test_init_tracking_scans_found_dir(tmp_path):
    track_dir = tmp_path / "found" / "ai_general"
    track_dir.mkdir(parents=True)
    (track_dir / "FR_pos1.md").write_text("# Position One\n\n| **Deadline** | 2026-08-01 |\n")
    count = tracker.init_tracking(tmp_path, "ai_general")
    assert count == 1
    data = tracker.load_tracking(track_dir)
    assert data["FR_pos1"]["status"] == "found"
    assert data["FR_pos1"]["deadline"] == "2026-08-01"


# ── db.py ─────────────────────────────────────────────────────────────────────

def test_upsert_and_query_roundtrip(tmp_path):
    conn = db.get_db(tmp_path)
    db.upsert(conn, {"id": "pos1", "title": "AI Engineer", "institution": "Inria the posting's city",
                      "deadline": "2026-08-01", "fit": "8/10", "track": "ai_general"}, "phd")
    rows = db.query(conn, kind="phd")
    assert len(rows) == 1
    assert rows[0]["id"] == "pos1"
    assert rows[0]["country"] == "France"
    assert rows[0]["fit_score"] == 8.0


def test_upsert_preserves_status_on_resync(tmp_path):
    conn = db.get_db(tmp_path)
    db.upsert(conn, {"id": "pos1", "title": "AI Engineer", "track": "ai_general"}, "phd")
    db.update_status(conn, "pos1", "phd", "sent", sent_date="2026-07-01")

    # Re-sync with a fresh scrape (status defaults to "found") must NOT clobber "sent"
    db.upsert(conn, {"id": "pos1", "title": "AI Engineer v2", "track": "ai_general"}, "phd")
    row = db.find_position(conn, "pos1", "phd")
    assert row["status"] == "sent"
    assert row["title"] == "AI Engineer v2"


def test_update_status_returns_false_for_missing_row(tmp_path):
    conn = db.get_db(tmp_path)
    assert db.update_status(conn, "nope", "phd", "sent") is False


def test_query_pending_only_excludes_terminal_statuses(tmp_path):
    conn = db.get_db(tmp_path)
    db.upsert(conn, {"id": "p1", "track": "t"}, "phd")
    db.upsert(conn, {"id": "p2", "track": "t"}, "phd")
    db.update_status(conn, "p2", "phd", "sent")
    pending = db.query(conn, kind="phd", pending_only=True)
    assert {r["id"] for r in pending} == {"p1"}


def test_stats_counts_by_status(tmp_path):
    conn = db.get_db(tmp_path)
    db.upsert(conn, {"id": "p1", "track": "t"}, "phd")
    db.upsert(conn, {"id": "p2", "track": "t"}, "phd")
    db.update_status(conn, "p2", "phd", "sent")
    s = db.stats(conn, "phd")
    assert s["total"] == 2
    assert s["by_status"]["sent"] == 1
    assert s["by_status"]["found"] == 1


def test_migrate_from_json(tmp_path):
    found = tmp_path / "PhD-Search" / "found" / "ai_general"
    found.mkdir(parents=True)
    tracker.save_tracking(found, {"pos1": {"status": "found", "title": "AI Position"}})
    conn = db.get_db(tmp_path)
    count = db.migrate_from_json(tmp_path, conn)
    assert count == 1
    assert db.find_position(conn, "pos1", "phd") is not None


# ── service.py ────────────────────────────────────────────────────────────────

def test_get_positions_enriches_with_days_left(tmp_path):
    from datetime import date, timedelta
    future = (date.today() + timedelta(days=5)).isoformat()
    conn = db.get_db(tmp_path)
    db.upsert(conn, {"id": "p1", "track": "t", "deadline": future}, "phd")
    rows = service.get_positions(tmp_path, "phd")
    assert rows[0]["days_left"] == 5


def test_get_stats_covers_both_kinds(tmp_path):
    conn = db.get_db(tmp_path)
    db.upsert(conn, {"id": "p1", "track": "t"}, "phd")
    db.upsert(conn, {"id": "p2", "track": "t"}, "job")
    stats = service.get_stats(tmp_path)
    assert stats["phd"]["total"] == 1
    assert stats["job"]["total"] == 1


def test_mark_sent_updates_db_and_json(tmp_path):
    conn = db.get_db(tmp_path)
    db.upsert(conn, {"id": "p1", "track": "ai_general"}, "phd")
    track_dir = tmp_path / "PhD-Search" / "found" / "ai_general"
    track_dir.mkdir(parents=True)
    tracker.save_tracking(track_dir, {"p1": {"status": "found"}})

    ok = service.mark_sent(tmp_path, "p1", "phd", sent_date="2026-07-06")
    assert ok is True
    assert db.find_position(conn, "p1", "phd")["status"] == "sent"
    assert tracker.load_tracking(track_dir)["p1"]["status"] == "sent"


# ── sources.py ────────────────────────────────────────────────────────────────

def test_add_source_inserts_before_gmail_section(tmp_path):
    src = tmp_path / "sources.md"
    src.write_text("existing | http://x.com | desc\n\n# ── GMAIL NEWSLETTERS ──\n")
    sources.add_source(src, "NewSite", "http://new.example", "test source")
    text = src.read_text()
    assert text.index("NewSite") < text.index("GMAIL NEWSLETTERS")


def test_add_source_priority_insert(tmp_path):
    src = tmp_path / "sources.md"
    src.write_text("first | http://a.com | \nsecond | http://b.com | \n")
    sources.add_source(src, "Inserted", "http://c.com", "", priority=2)
    lines = [l for l in src.read_text().splitlines() if l.strip()]
    assert lines[1].startswith("Inserted")


if __name__ == "__main__":
    # Plain-python self-runner: discover and run all test_* functions.
    import tempfile
    import traceback

    tests = [(name, obj) for name, obj in list(globals().items())
              if name.startswith("test_") and callable(obj)]
    passed = failed = 0
    for name, fn in tests:
        try:
            if fn.__code__.co_argcount:
                with tempfile.TemporaryDirectory() as d:
                    fn(Path(d))
            else:
                fn()
            passed += 1
        except Exception:
            failed += 1
            print(f"FAIL {name}")
            traceback.print_exc()
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
