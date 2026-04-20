from fastapi.testclient import TestClient

from app.main import create_app


API_PREFIX = "/api/v1/researchers"


def _assert_success_payload(response) -> dict:
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert "data" in payload
    return payload


def _assert_list_response_container(data: dict) -> None:
    assert isinstance(data, dict)
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)
    assert isinstance(data["total"], int)


def _extract_researcher_id(item: dict) -> str | None:
    identifier = item.get("researcher_id") or item.get("id")
    if isinstance(identifier, str) and identifier:
        return identifier
    return None


def test_researchers_market_list_and_search_params_contract() -> None:
    client = TestClient(create_app())

    market_data = _assert_success_payload(client.get(f"{API_PREFIX}/market"))["data"]
    _assert_list_response_container(market_data)

    search_data = _assert_success_payload(
        client.get(
            f"{API_PREFIX}/market",
            params={
                "q": "技术",
                "style": "技术分析",
                "level": "LV.2",
                "sort_by": "hired_count",
                "page": 1,
                "page_size": 10,
            },
        )
    )["data"]
    _assert_list_response_container(search_data)


def test_researchers_market_detail_contract() -> None:
    client = TestClient(create_app())

    market_items = _assert_success_payload(client.get(f"{API_PREFIX}/market"))["data"]["items"]
    assert market_items, "market 列表为空，无法校验详情接口"
    researcher_id = _extract_researcher_id(market_items[0])
    assert researcher_id is not None

    detail_data = _assert_success_payload(client.get(f"{API_PREFIX}/market/{researcher_id}"))["data"]
    assert isinstance(detail_data, dict)
    assert _extract_researcher_id(detail_data) is not None


def test_researchers_mine_list_contract() -> None:
    client = TestClient(create_app())

    mine_data = _assert_success_payload(client.get(f"{API_PREFIX}/mine"))["data"]
    _assert_list_response_container(mine_data)


def test_researchers_duplicate_publish_unpublish_status_flow() -> None:
    client = TestClient(create_app())

    mine_items = _assert_success_payload(client.get(f"{API_PREFIX}/mine"))["data"]["items"]
    if mine_items:
        source_id = _extract_researcher_id(mine_items[0])
    else:
        created_data = _assert_success_payload(
            client.post(
                f"{API_PREFIX}",
                json={
                    "name": "状态流测试研究员",
                    "title": "状态流测试",
                    "style": "均衡",
                    "description": "用于测试 duplicate/publish/unpublish",
                    "prompt": "你是测试研究员",
                },
            )
        )["data"]
        source_id = _extract_researcher_id(created_data)

    assert source_id is not None

    duplicated_data = _assert_success_payload(client.post(f"{API_PREFIX}/{source_id}/duplicate"))["data"]
    duplicated_id = _extract_researcher_id(duplicated_data)
    assert duplicated_id is not None

    before_detail = _assert_success_payload(client.get(f"{API_PREFIX}/{duplicated_id}"))["data"]
    before_visibility = before_detail.get("visibility")
    before_version = before_detail.get("published_version")

    publish_record = _assert_success_payload(client.post(f"{API_PREFIX}/{duplicated_id}/publish"))["data"]
    published_detail = _assert_success_payload(client.get(f"{API_PREFIX}/{duplicated_id}"))["data"]
    published_visibility = published_detail.get("visibility")
    published_version = published_detail.get("published_version")

    unpublish_record = _assert_success_payload(client.post(f"{API_PREFIX}/{duplicated_id}/unpublish"))["data"]
    unpublished_detail = _assert_success_payload(client.get(f"{API_PREFIX}/{duplicated_id}"))["data"]
    unpublished_visibility = unpublished_detail.get("visibility")
    unpublished_version = unpublished_detail.get("published_version")

    # 以可见性和发布版本验证状态流转：draft/private -> public -> private
    assert published_visibility == "public"
    assert unpublished_visibility == "private"
    assert published_version is not None
    # 下架后保留最后发布版本，便于回显。
    assert unpublished_version == published_version
    if before_visibility is not None:
        assert before_visibility != published_visibility or before_version != published_version
    assert publish_record.get("status") == "published"
    assert unpublish_record.get("status") == "unpublished"


def test_researchers_options_endpoints_contract() -> None:
    client = TestClient(create_app())

    for url in (
        f"{API_PREFIX}/options/skills",
        f"{API_PREFIX}/options/knowledge-bases",
        f"{API_PREFIX}/options/mcp-servers",
    ):
        data = _assert_success_payload(client.get(url))["data"]
        _assert_list_response_container(data)


def test_researcher_create_supports_editor_extended_fields() -> None:
    client = TestClient(create_app())
    payload = {
        "name": "扩展字段创建测试",
        "title": "扩展字段标题",
        "style": "事件驱动",
        "description": "用于校验创建时扩展字段可保存",
        "prompt": "你是一个可配置的研究员",
        "visibility": "private",
        "skills": ["skill_event_drive"],
        "knowledge_bases": ["kb_market_daily"],
        "mcp_servers": ["mcp_financial_news"],
        "self_drive_tasks": ["盘前检查", "收盘复盘"],
    }

    data = _assert_success_payload(client.post(f"{API_PREFIX}", json=payload))["data"]
    assert data["visibility"] == "private"
    assert data["skills"] == ["skill_event_drive"]
    assert data["knowledge_bases"] == ["kb_market_daily"]
    assert data["mcp_servers"] == ["mcp_financial_news"]
    assert data["self_drive_tasks"] == ["盘前检查", "收盘复盘"]


def test_researcher_patch_supports_editor_extended_fields() -> None:
    client = TestClient(create_app())
    created = _assert_success_payload(
        client.post(
            f"{API_PREFIX}",
            json={
                "name": "扩展字段更新测试",
            },
        )
    )["data"]
    researcher_id = _extract_researcher_id(created)
    assert researcher_id is not None

    patched = _assert_success_payload(
        client.patch(
            f"{API_PREFIX}/{researcher_id}",
            json={
                "visibility": "public",
                "skills": ["skill_tech_analysis"],
                "knowledge_bases": ["kb_chip_data"],
                "mcp_servers": ["mcp_fund_flow"],
                "self_drive_tasks": ["盘中观察量能", "尾盘检查风控"],
            },
        )
    )["data"]
    assert patched["visibility"] == "public"
    assert patched["skills"] == ["skill_tech_analysis"]
    assert patched["knowledge_bases"] == ["kb_chip_data"]
    assert patched["mcp_servers"] == ["mcp_fund_flow"]
    assert patched["self_drive_tasks"] == ["盘中观察量能", "尾盘检查风控"]


def test_researcher_create_rejects_self_drive_tasks_over_limit() -> None:
    client = TestClient(create_app())
    response = client.post(
        f"{API_PREFIX}",
        json={
            "name": "超限校验测试",
            "self_drive_tasks": [f"任务{i}" for i in range(11)],
        },
    )
    assert response.status_code == 422


def test_researchers_test_chat_contract() -> None:
    client = TestClient(create_app())

    market_items = _assert_success_payload(client.get(f"{API_PREFIX}/market"))["data"]["items"]
    assert market_items, "market 列表为空，无法校验 test-chat 接口"
    researcher_id = _extract_researcher_id(market_items[0])
    assert researcher_id is not None

    payload = _assert_success_payload(
        client.post(
            f"{API_PREFIX}/{researcher_id}/test-chat",
            json={
                "question": "请给出一段测试回复",
            },
        )
    )
    assert isinstance(payload["data"], dict)
