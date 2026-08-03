from logger_util import setup_logger, append_todo_notification


def test_setup_logger_writes_to_file(tmp_path):
    log_path = tmp_path / "app.log"
    logger = setup_logger(str(log_path))
    logger.info("テストメッセージ")
    for handler in logger.handlers:
        handler.flush()
    assert log_path.exists()
    assert "テストメッセージ" in log_path.read_text(encoding="utf-8")


def test_append_todo_notification_creates_file_when_missing(tmp_path):
    from datetime import date

    todos_dir = tmp_path / "todos"
    append_todo_notification(str(todos_dir), "エラーが発生しました", today=date(2026, 7, 25))
    todo_file = todos_dir / "2026-07-25.md"
    assert todo_file.exists()
    assert "エラーが発生しました" in todo_file.read_text(encoding="utf-8")


def test_append_todo_notification_appends_to_existing_file(tmp_path):
    from datetime import date

    todos_dir = tmp_path / "todos"
    todos_dir.mkdir()
    todo_file = todos_dir / "2026-07-25.md"
    todo_file.write_text("# 既存の内容\n- [ ] 既存タスク\n", encoding="utf-8")

    append_todo_notification(str(todos_dir), "エラーが発生しました", today=date(2026, 7, 25))

    content = todo_file.read_text(encoding="utf-8")
    assert "既存タスク" in content
    assert "エラーが発生しました" in content
