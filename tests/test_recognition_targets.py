from core.recognition_targets import enabled_targets, search_presets, targets_prompt
from core.sorter_engine import _parse_classify_response


def test_enabled_targets_feed_prompt_and_search():
    config = {
        "recognition_targets_enabled": True,
        "recognition_targets": [
            {"name": "红色产品", "type": "物品", "description": "红色包装", "enabled": True},
            {"name": "忽略项", "type": "场景", "description": "不应出现", "enabled": False},
        ],
    }

    targets = enabled_targets(config)

    assert [item["name"] for item in targets] == ["红色产品"]
    assert "红色产品（物品）：红色包装" in targets_prompt(targets)
    assert search_presets(config) == [{"name": "红色产品", "query": "红色包装"}]


def test_global_switch_disables_targets():
    config = {
        "recognition_targets_enabled": False,
        "recognition_targets": [{"name": "产品", "enabled": True}],
    }

    assert enabled_targets(config) == []
    assert search_presets(config) == []


def test_classification_response_keeps_matching_custom_targets():
    desc, persons, places = _parse_classify_response(
        "SCENE: 办公室\nDESC: 桌上有红色包装\nTARGETS: 红色产品,不存在",
        [], [], False, False,
        [{"name": "红色产品"}],
    )

    assert "识别目标:红色产品" in desc
    assert persons == []
    assert places == []
