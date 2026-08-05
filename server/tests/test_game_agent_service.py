from app.game_agent_service import OllamaGameAgent


def test_game_decision_filters_unsafe_actions() -> None:
    agent = OllamaGameAgent(model="test")
    decision = agent._parse({
        "say": "Let's explore.",
        "actions": [{"type": "move", "direction": "north"}, {"type": "run_shell"}],
        "confidence": 2,
        "needs_input": False,
    })
    assert decision.say == "Let's explore."
    assert [action["type"] for action in decision.actions] == ["move"]
    assert decision.confidence == 1.0
