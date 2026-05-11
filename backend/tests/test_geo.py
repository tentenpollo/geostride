import math

from geostride.utils.geo import haversine_distance


def test_haversine_distance():
    # Same point should be 0
    assert haversine_distance(0.0, 0.0, 0.0, 0.0) == 0.0
    
    # 1 degree of latitude is roughly 111km
    dist = haversine_distance(0.0, 0.0, 1.0, 0.0)
    assert math.isclose(dist, 111195, rel_tol=0.01)
    
    # Coordinates in NY
    # Central Park: 40.7812, -73.9665
    # Times Square: 40.7580, -73.9855
    dist2 = haversine_distance(40.7812, -73.9665, 40.7580, -73.9855)
    assert math.isclose(dist2, 3020, rel_tol=0.05)
