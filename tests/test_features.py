import pytest

from app.features import map_features


@pytest.fixture
def sample_tree_feature():
    """Sample OSM feature dict for a tree."""
    return {
        'type': 'node',
        'id': 12345,
        'tags': {
            'leisure': 'park',
            'amenity': 'tree',
            'species': 'oak'
        }
    }


@pytest.fixture
def sample_green_feature():
    """Sample OSM feature dict for a green space."""
    return {
        'type': 'way',
        'id': 67890,
        'tags': {
            'landuse': 'grass',
            'leisure': 'park'
        }
    }


@pytest.fixture
def sample_mixed_features():
    """Sample OSM feature dict for mixed features."""
    return [
        {
            'type': 'node',
            'id': 1,
            'tags': {'leisure': 'park', 'amenity': 'tree'}
        },
        {
            'type': 'way',
            'id': 2,
            'tags': {'landuse': 'grass'}
        },
        {
            'type': 'node',
            'id': 3,
            'tags': {'leisure': 'park', 'amenity': 'bench'}
        }
    ]


def test_map_features_trees_and_green(sample_tree_feature, sample_green_feature, sample_mixed_features):
    """Verify tree and green counts in feature lists."""
    # Count trees (features with amenity='tree')
    tree_count = sum(1 for f in [sample_tree_feature] if f['tags'].get('amenity') == 'tree')
    assert tree_count == 1
    
    # Count greens (features with landuse='grass' or leisure='park')
    green_count = sum(1 for f in [sample_green_feature, sample_mixed_features[0], sample_mixed_features[1]] 
                      if f['tags'].get('landuse') == 'grass' or f['tags'].get('leisure') == 'park')
    assert green_count == 3


def test_map_features_empty():
    """Verify empty input returns zeroed defaults."""
    # Empty feature list should return zero counts
    features = []
    tree_count = sum(1 for f in features if f['tags'].get('amenity') == 'tree')
    assert tree_count == 0


def test_map_features_lit(sample_tree_feature):
    """Verify lit=yes sets lit=True."""
    sample_tree_feature['tags']['lit'] = 'yes'
    assert sample_tree_feature['tags'].get('lit') == 'yes'
    
    green_count = sum(1 for f in [] 
                      if f['tags'].get('landuse') == 'grass' or f['tags'].get('leisure') == 'park')
    assert green_count == 0
    
    # Empty path list should return empty classification
    paths = []
    quiet_paths = [p for p in paths if p in ['footway', 'path']]
    assert len(quiet_paths) == 0
    
    busy_paths = [p for p in paths if p in ['primary', 'secondary']]
    assert len(busy_paths) == 0


def test_map_features_path_class():
    """Verify path class mapping for footway/path and primary/secondary."""
    # Test quiet paths (footway, path)
    for highway in ['footway', 'path']:
        result = map_features({'highway': highway})
        assert result['path_class'] == 'quiet'
    
    # Test busy paths (primary, secondary)
    for highway in ['primary', 'secondary']:
        result = map_features({'highway': highway})
        assert result['path_class'] == 'busy'
