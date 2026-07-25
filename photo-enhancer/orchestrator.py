import os

from drive_client import filter_files_older_than


def process_new_images(drive_client, request_folder_id, processed_folder_id, config, enhance_fn, logger):
    files = drive_client.list_image_files(request_folder_id)
    processed_count = 0
    error_count = 0
    for file in files:
        file_id = file["id"]
        name = file["name"]
        try:
            content = drive_client.download_file(file_id)
            enhanced_bytes = enhance_fn(content, config)
            new_name = os.path.splitext(name)[0] + ".jpg"
            drive_client.upload_file(processed_folder_id, new_name, enhanced_bytes)
            drive_client.delete_file(file_id)
            processed_count += 1
        except Exception as exc:
            error_count += 1
            logger.error(f"加工失敗: {name} ({exc})")
    return processed_count, error_count


def cleanup_old_processed(drive_client, processed_folder_id, retention_days, logger, now=None):
    files = drive_client.list_image_files(processed_folder_id)
    old_files = filter_files_older_than(files, retention_days, now)
    deleted_count = 0
    for file in old_files:
        drive_client.delete_file(file["id"])
        deleted_count += 1
    if deleted_count:
        logger.info(f"安全ネット削除: {deleted_count}件")
    return deleted_count
