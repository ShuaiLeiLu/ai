from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import create_app


API_PREFIX = "/api/v1"


def _assert_success_payload(response, expected_status: int = 200) -> dict:
    assert response.status_code == expected_status
    payload = response.json()
    assert payload["success"] is True
    assert "data" in payload
    return payload


def _assert_error_payload(response, expected_status: int) -> dict:
    assert response.status_code == expected_status
    payload = response.json()
    if expected_status == 422 and "success" not in payload:
        assert "detail" in payload
        return payload
    assert payload["success"] is False
    assert payload["data"] is None
    assert "detail" in payload
    return payload


def _assert_list_response_container(data: dict) -> None:
    assert isinstance(data, dict)
    assert isinstance(data.get("items"), list)
    assert isinstance(data.get("total"), int)


def test_documents_list_supports_doc_type_and_pagination() -> None:
    client = TestClient(create_app())

    base_data = _assert_success_payload(client.get(f"{API_PREFIX}/documents"))["data"]
    _assert_list_response_container(base_data)
    base_items = base_data["items"]
    base_ids = [item["document_id"] for item in base_items]

    market_data = _assert_success_payload(
        client.get(f"{API_PREFIX}/documents", params={"doc_type": "market"})
    )["data"]
    _assert_list_response_container(market_data)
    assert all(item["document_type"] == "market" for item in market_data["items"])

    limited_data = _assert_success_payload(client.get(f"{API_PREFIX}/documents", params={"limit": 1}))["data"]
    _assert_list_response_container(limited_data)
    assert limited_data["total"] == base_data["total"]
    assert [item["document_id"] for item in limited_data["items"]] == base_ids[:1]

    page1_data = _assert_success_payload(
        client.get(f"{API_PREFIX}/documents", params={"page": 1, "page_size": 1})
    )["data"]
    page2_data = _assert_success_payload(
        client.get(f"{API_PREFIX}/documents", params={"page": 2, "page_size": 1})
    )["data"]
    assert [item["document_id"] for item in page1_data["items"]] == base_ids[:1]
    assert [item["document_id"] for item in page2_data["items"]] == base_ids[1:2]


def test_documents_detail_404_and_invalid_pagination_param() -> None:
    client = TestClient(create_app())

    missing_payload = _assert_error_payload(
        client.get(f"{API_PREFIX}/documents/not-exists-doc"),
        expected_status=404,
    )
    assert missing_payload["detail"] == "文档不存在"

    _assert_error_payload(
        client.get(f"{API_PREFIX}/documents", params={"page": 0, "page_size": 1}),
        expected_status=422,
    )


def test_community_list_supports_q_filter_and_create_visible_in_desc_order() -> None:
    client = TestClient(create_app())

    keyword = f"excerpt-{uuid4().hex[:8]}"
    create_payload = _assert_success_payload(
        client.post(
            f"{API_PREFIX}/community/posts",
            json={
                "title": f"pytest-community-{uuid4().hex[:6]}",
                "content": f"这是用于摘要搜索的关键字 {keyword}，并补充一些正文内容。",
                "tags": ["pytest"],
            },
        )
    )["data"]
    created_post_id = create_payload["post_id"]

    list_after_create = _assert_success_payload(client.get(f"{API_PREFIX}/community/posts"))["data"]
    _assert_list_response_container(list_after_create)
    assert list_after_create["items"], "社区帖子列表为空，无法校验倒序"
    assert list_after_create["items"][0]["post_id"] == created_post_id

    by_excerpt_data = _assert_success_payload(
        client.get(f"{API_PREFIX}/community/posts", params={"q": keyword})
    )["data"]
    _assert_list_response_container(by_excerpt_data)
    assert by_excerpt_data["items"], "q 过滤后应至少包含刚创建的帖子"
    assert any(item["post_id"] == created_post_id for item in by_excerpt_data["items"])
    for item in by_excerpt_data["items"]:
        searchable = f"{item['title']} {item['excerpt']}".lower()
        assert keyword.lower() in searchable


def test_community_detail_404() -> None:
    client = TestClient(create_app())

    payload = _assert_error_payload(
        client.get(f"{API_PREFIX}/community/posts/not-exists-post"),
        expected_status=404,
    )
    assert payload["detail"] == "帖子不存在"


def test_notes_folders_order_is_stable_and_notes_support_filter_and_desc_order() -> None:
    client = TestClient(create_app())

    folders_first = _assert_success_payload(client.get(f"{API_PREFIX}/notes/folders"))["data"]
    folders_second = _assert_success_payload(client.get(f"{API_PREFIX}/notes/folders"))["data"]
    _assert_list_response_container(folders_first)
    _assert_list_response_container(folders_second)

    folder_order_first = [item["folder_id"] for item in folders_first["items"]]
    folder_order_second = [item["folder_id"] for item in folders_second["items"]]
    assert folder_order_first == folder_order_second

    folder_id = "f_watchlist"
    first_note = _assert_success_payload(
        client.post(
            f"{API_PREFIX}/notes",
            json={
                "folder_id": folder_id,
                "title": f"pytest-note-a-{uuid4().hex[:6]}",
                "content_markdown": "A",
            },
        )
    )["data"]
    second_note = _assert_success_payload(
        client.post(
            f"{API_PREFIX}/notes",
            json={
                "folder_id": folder_id,
                "title": f"pytest-note-b-{uuid4().hex[:6]}",
                "content_markdown": "B",
            },
        )
    )["data"]

    filtered_data = _assert_success_payload(
        client.get(f"{API_PREFIX}/notes", params={"folder_id": folder_id})
    )["data"]
    _assert_list_response_container(filtered_data)
    assert all(item["folder_id"] == folder_id for item in filtered_data["items"])

    note_ids = [item["note_id"] for item in filtered_data["items"]]
    assert second_note["note_id"] in note_ids
    assert first_note["note_id"] in note_ids
    assert note_ids.index(second_note["note_id"]) < note_ids.index(first_note["note_id"])

    updated_at_values = [datetime.fromisoformat(item["updated_at"]) for item in filtered_data["items"]]
    assert updated_at_values == sorted(updated_at_values, reverse=True)


def test_notes_upsert_rejects_nonexistent_folder_with_404() -> None:
    client = TestClient(create_app())

    create_error = _assert_error_payload(
        client.post(
            f"{API_PREFIX}/notes",
            json={
                "folder_id": "folder-not-found",
                "title": "invalid-folder-create",
                "content_markdown": "test",
            },
        ),
        expected_status=404,
    )
    assert create_error["detail"] == "文件夹不存在"

    valid_note = _assert_success_payload(
        client.post(
            f"{API_PREFIX}/notes",
            json={
                "folder_id": "f_root",
                "title": f"pytest-note-valid-{uuid4().hex[:6]}",
                "content_markdown": "ok",
            },
        )
    )["data"]
    update_error = _assert_error_payload(
        client.put(
            f"{API_PREFIX}/notes/{valid_note['note_id']}",
            json={
                "folder_id": "folder-not-found",
                "title": "invalid-folder-update",
                "content_markdown": "test",
            },
        ),
        expected_status=404,
    )
    assert update_error["detail"] == "文件夹不存在"
