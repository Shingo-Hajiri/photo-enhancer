import os

from config import DEFAULT_CONFIG
from drive_client import get_credentials, build_service, ensure_folder_structure, DriveClient
from image_processor import enhance_image_bytes
from orchestrator import process_new_images, cleanup_old_processed
from logger_util import setup_logger, append_todo_notification


def main():
    config = DEFAULT_CONFIG
    logger = setup_logger(config.log_path)
    logger.info("photo-enhancer 実行開始")

    company_todos_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", ".company", "secretary", "todos"
    )

    try:
        creds = get_credentials(config.credentials_path, config.token_path)
        service = build_service(creds)
        drive_client = DriveClient(service)

        request_folder_id, processed_folder_id = ensure_folder_structure(
            service, config.root_folder_name, config.request_folder_name, config.processed_folder_name
        )

        processed_count, error_count = process_new_images(
            drive_client, request_folder_id, processed_folder_id, config, enhance_image_bytes, logger
        )
        deleted_count = cleanup_old_processed(
            drive_client, processed_folder_id, config.retention_days, logger
        )

        logger.info(f"完了: 加工{processed_count}件 / エラー{error_count}件 / 安全ネット削除{deleted_count}件")

        if error_count > 0:
            append_todo_notification(
                company_todos_dir,
                f"【photo-enhancer】画像加工でエラーが{error_count}件発生しました。ログ({config.log_path})を確認してください。",
            )
    except Exception as exc:
        logger.error(f"photo-enhancer 実行中に予期しないエラーが発生しました: {exc!r}", exc_info=True)
        append_todo_notification(
            company_todos_dir,
            f"【photo-enhancer】致命的なエラーで処理が停止しました({exc})。ログ({config.log_path})を確認してください。"
            "OAuthトークンの期限切れの場合は `python3 main.py` を手動実行して再認証してください。",
        )
        raise


if __name__ == "__main__":
    main()
