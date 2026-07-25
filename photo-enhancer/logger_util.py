import os
from datetime import date


def setup_logger(log_path: str):
    import logging

    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    logger = logging.getLogger("photo_enhancer")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    return logger


def append_todo_notification(todos_dir: str, message: str, today: date = None) -> None:
    today = today or date.today()
    os.makedirs(todos_dir, exist_ok=True)
    todo_path = os.path.join(todos_dir, f"{today.isoformat()}.md")
    if not os.path.exists(todo_path):
        with open(todo_path, "w", encoding="utf-8") as f:
            f.write(f'---\ndate: "{today.isoformat()}"\ntype: daily\n---\n\n# {today.isoformat()}\n\n## メモ・振り返り\n- {message}\n')
        return
    with open(todo_path, "a", encoding="utf-8") as f:
        f.write(f"- {message}\n")
