from geostride.services.vibe_engine import VibeEngine
from geostride.models import VibeWeights


def test_vibe_engine_greenery():
    amenities = {
        "parks": [{"lat": 1.0, "lon": 1.0}],
        "water": [],
        "shops": [],
        "food": [],
        "lit_streets": [],
    }
    engine = VibeEngine(amenities)
    profile = engine.compute_point_vibe_profile(1.0, 1.0)
    assert profile.greenery > 0.8


def test_vibe_engine_blue_space():
    amenities = {
        "parks": [],
        "water": [{"lat": 2.0, "lon": 2.0}],
        "shops": [],
        "food": [],
        "lit_streets": [],
    }
    engine = VibeEngine(amenities)
    profile = engine.compute_point_vibe_profile(2.0, 2.0)
    assert profile.blue_space > 0.8


def test_vibe_engine_liveliness():
    amenities = {
        "parks": [],
        "water": [],
        "shops": [{"lat": 3.0, "lon": 3.0}],
        "food": [{"lat": 3.0, "lon": 3.0}],
        "lit_streets": [],
    }
    engine = VibeEngine(amenities)
    profile = engine.compute_point_vibe_profile(3.0, 3.0)
    assert profile.liveliness > 0.8


def test_vibe_engine_empty_amenities():
    engine = VibeEngine({})
    profile = engine.compute_point_vibe_profile(0.0, 0.0)
    assert profile.greenery == 0.0
    assert profile.blue_space == 0.0
    assert profile.liveliness == 0.0


def test_no_go_zone():
    engine = VibeEngine({})
    engine.add_no_go_zone(5.0, 5.0, radius_meters=200)
    assert engine.is_in_no_go_zone(5.001, 5.001)
    assert not engine.is_in_no_go_zone(6.0, 6.0)
