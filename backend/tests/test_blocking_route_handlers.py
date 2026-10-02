import inspect

from api.codex import routes as codex_routes
from api.hermes import routes as hermes_routes
from api.platform_brain import routes as platform_brain_routes


def test_blocking_route_handlers_are_sync_for_fastapi_threadpool():
    blocking_handlers = [
        codex_routes.get_codex_status,
        codex_routes.start_device_login,
        codex_routes.start_codex_run,
        codex_routes.cancel_codex_run,
        hermes_routes.list_drafts,
        hermes_routes.create_draft,
        hermes_routes.get_draft,
        hermes_routes.validate_draft,
        hermes_routes.apply_draft,
        hermes_routes.reject_draft,
        hermes_routes.validate_workflow_payload,
        hermes_routes.list_hermes_tools,
        platform_brain_routes.get_platform_brain_status,
        platform_brain_routes.reindex_platform_brain,
        platform_brain_routes.query_platform_brain,
        platform_brain_routes.query_platform_brain_get,
    ]

    assert [handler.__name__ for handler in blocking_handlers if inspect.iscoroutinefunction(handler)] == []


def test_codex_sse_handler_remains_async():
    assert inspect.iscoroutinefunction(codex_routes.get_codex_run_events)
