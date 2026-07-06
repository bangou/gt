import json

from gto import get_gto_strategy


def test_normal_query_returns_check_bet_strategy():
    payload = {
        "table_size": 9,
        "position": "BTN",
        "effective_stack_bb": 100,
        "my_hand": ["Ah", "Kh"],
        "board": ["Qh", "7d", "2c"],
        "pot_size_bb": 5.5,
        "current_bet_to_call_bb": 0,
        "actions_history": [
            {"street": "preflop", "actions": ["raise_2.5bb", "call"]},
            {"street": "flop", "actions": ["hero_to_act"]},
        ],
        "players_remaining": 2,
        "options": ["check", "bet"],
        "raise_sizes_allowed": [1.8, 3.5],
    }

    response = json.loads(get_gto_strategy(json.dumps(payload)))

    assert response["status"] == "success"
    assert response["strategy"]["check"] > 0
    assert response["strategy"]["bet"] > 0
    assert len(response["strategy"]["bet_sizes"]) > 0
    assert response["range_info"]["recommended_action"] in {"check", "bet"}


def test_unsupported_spot_returns_error():
    payload = {
        "table_size": 9,
        "position": "UTG",
        "effective_stack_bb": 100,
        "my_hand": ["As", "Ad"],
        "board": ["Kh", "Qh", "Jh", "Th", "9h"],
        "pot_size_bb": 20,
        "current_bet_to_call_bb": 0,
        "actions_history": [{"street": "river", "actions": ["hero_to_act"]}],
        "players_remaining": 2,
        "options": ["check", "bet"],
    }

    response = json.loads(get_gto_strategy(json.dumps(payload)))

    assert response["status"] == "error"
    assert response["message"] == "No strategy found for the normalized situation"


def test_missing_optional_fields_use_defaults():
    payload = {
        "position": "BTN",
        "my_hand": ["Ah", "Kh"],
        "pot_size_bb": 1.5,
        "current_bet_to_call_bb": 0,
    }

    response = json.loads(get_gto_strategy(json.dumps(payload)))

    assert response["status"] == "success"
    assert response["debug"]["normalized_request"]["table_size"] == 9
    assert response["debug"]["normalized_request"]["effective_stack_bb"] == 100
    assert response["debug"]["normalized_request"]["board"] == []
    assert response["debug"]["normalized_request"]["actions_history"] == []
    assert response["debug"]["warnings"]
    assert response["debug"]["matched_table_id"] == "preflop_9max_btn_rfi_aks_100"
