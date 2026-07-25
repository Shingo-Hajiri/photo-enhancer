import main as main_module


def test_main_runs_pipeline_and_reports_counts(monkeypatch):
    calls = []

    monkeypatch.setattr(main_module, "get_credentials", lambda *a, **k: "creds")
    monkeypatch.setattr(main_module, "build_service", lambda creds: "service")
    monkeypatch.setattr(
        main_module, "ensure_folder_structure",
        lambda service, root, req, proc: ("request-id", "processed-id"),
    )

    def fake_process_new_images(drive_client, request_id, processed_id, config, enhance_fn, logger):
        calls.append(("process", request_id, processed_id))
        return 2, 0

    def fake_cleanup(drive_client, processed_id, retention_days, logger):
        calls.append(("cleanup", processed_id, retention_days))
        return 1

    monkeypatch.setattr(main_module, "process_new_images", fake_process_new_images)
    monkeypatch.setattr(main_module, "cleanup_old_processed", fake_cleanup)

    notified = []
    monkeypatch.setattr(
        main_module, "append_todo_notification",
        lambda todos_dir, message: notified.append(message),
    )

    main_module.main()

    assert ("process", "request-id", "processed-id") in calls
    assert ("cleanup", "processed-id", main_module.DEFAULT_CONFIG.retention_days) in calls
    assert notified == []


def test_main_notifies_todo_on_errors(monkeypatch):
    monkeypatch.setattr(main_module, "get_credentials", lambda *a, **k: "creds")
    monkeypatch.setattr(main_module, "build_service", lambda creds: "service")
    monkeypatch.setattr(
        main_module, "ensure_folder_structure",
        lambda service, root, req, proc: ("request-id", "processed-id"),
    )
    monkeypatch.setattr(main_module, "process_new_images", lambda *a, **k: (1, 2))
    monkeypatch.setattr(main_module, "cleanup_old_processed", lambda *a, **k: 0)

    notified = []
    monkeypatch.setattr(
        main_module, "append_todo_notification",
        lambda todos_dir, message: notified.append(message),
    )

    main_module.main()

    assert len(notified) == 1
    assert "エラー" in notified[0]
