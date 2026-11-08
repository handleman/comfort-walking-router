def map_features(features):
    """
    Map OSM tags into a feature dict.

    Args:
        features (dict): Dictionary of OSM tags with keys like 'natural', 'landuse',
                         'highway', 'lit'.

    Returns:
        dict: Feature dict with keys 'trees', 'green', 'lit', 'path_class'.
    """
    highway = features.get('highway', '').lower()
    
    # Map path classes based on highway tag
    if highway in ('footway', 'path'):
        path_class = 'quiet'
    elif highway in ('primary', 'secondary'):
        path_class = 'busy'
    else:
        path_class = highway
    
    result = {
        'trees': features.get('natural') == 'tree' or features.get('landuse') == 'forest',
        'green': features.get('natural') in ('tree', 'wood', 'grass', 'scrub') or \
                 features.get('landuse') in ('park', 'residential', 'commercial'),
        'lit': features.get('lit') == 'yes',
        'path_class': path_class,
    }
    return result
