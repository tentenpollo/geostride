from geostride.services.cost_functions import CostFunctionEngine, EdgeVibeScores


def test_quality_score_full_greenery_match():
    engine = CostFunctionEngine({})
    scores = EdgeVibeScores(
        greenery=1.0, blue_space=0.0, quietness=0.5,
        liveliness=0.0, lighting=1.0, walkability=0.8,
    )
    weights = {"greenery": 1.0, "safety_check": 0.5}
    quality = engine.compute_quality_score(scores, weights)
    assert quality == 1.0


def test_quality_score_no_match():
    engine = CostFunctionEngine({})
    scores = EdgeVibeScores(
        greenery=0.0, blue_space=0.0, quietness=0.0,
        liveliness=0.0, lighting=0.0, walkability=0.0,
    )
    weights = {"greenery": 1.0, "safety_check": 0.5}
    quality = engine.compute_quality_score(scores, weights)
    assert quality == 0.0


def test_generative_cost_max_quality():
    engine = CostFunctionEngine({})
    base_cost = 100
    cost = engine.compute_generative_cost(base_cost, quality_score=1.0, smoothing=0.6)
    assert cost == 40.0


def test_generative_cost_zero_quality():
    engine = CostFunctionEngine({})
    base_cost = 100
    cost = engine.compute_generative_cost(base_cost, quality_score=0.0, smoothing=0.6)
    assert cost == 100.0


def test_generative_cost_zero_smoothing():
    engine = CostFunctionEngine({})
    base_cost = 100
    cost = engine.compute_generative_cost(base_cost, quality_score=1.0, smoothing=0.0)
    assert cost == 100.0


def test_quality_score_partial_match():
    engine = CostFunctionEngine({})
    scores = EdgeVibeScores(
        greenery=0.5, blue_space=0.3, quietness=0.7,
        liveliness=0.2, lighting=0.9, walkability=0.6,
    )
    weights = {"greenery": 0.8, "safety_check": 0.6, "introvert_mode": 0.4}
    quality = engine.compute_quality_score(scores, weights)
    assert 0.0 < quality < 1.0


def test_cost_decreases_with_higher_quality():
    engine = CostFunctionEngine({})
    low_quality_cost = engine.compute_generative_cost(100, quality_score=0.2, smoothing=0.6)
    high_quality_cost = engine.compute_generative_cost(100, quality_score=0.8, smoothing=0.6)
    assert high_quality_cost < low_quality_cost
