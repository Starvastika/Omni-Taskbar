"""Advanced dataset retention, freshness and presentation at the unit boundary."""
import time
from services.analysis import model_view, ensemble_view, history_view, previous_runs_view
from services.presentation import rows, metrics, LABELS
from services.units import convert

TTL = {'marine': 3600, 'models': 3600, 'ensemble': 3600, 'runs': 3600, 'history': 86400}
PRESENTATION_PREFS = {'temperature', 'wind', 'pressure', 'precipitation', 'visibility', 'distance', 'hour24', 'dateFormat'}

def retain(previous, incoming):
    # Retain the original endpoint, period and acquisition time, never relabel
    # an old response as the newly requested dataset or a successful refresh.
    if incoming.get('data') is None and previous.get('data') is not None:
        return {**previous, 'stale': True, 'cache': True,
                'error': incoming.get('error') or 'Refresh unavailable; last useful dataset retained'}
    return incoming

def freshness(kind, bundle, now=None):
    now = time.time() if now is None else now
    saved = bundle.get('saved', 0)
    return {'saved': saved, 'age': f'{int(max(0, now-saved)//60)} min old' if saved else 'Not loaded',
            'stale': bool(bundle.get('stale', True)) or now-saved > TTL[kind],
            'error': bundle.get('error', ''), 'endpoint': bundle.get('source', '')}

def present(kind, bundle, loc, prefs):
    data = bundle.get('data') or {}
    if not isinstance(data, dict):
        raise ValueError('Expected one location dataset object')
    result = {**freshness(kind, bundle), 'loading': False}
    if kind == 'marine':
        result.update({'rows': rows(data, 'hourly', loc, prefs),
                       'metrics': metrics(data, loc, prefs, 'Open-Meteo marine model'),
                       'series': [{'key': key, 'label': LABELS.get(key, key),
                                   'unit': convert(0, unit, prefs, key)[1]}
                                  for key, unit in data.get('hourly_units', {}).items() if key != 'time']})
        result['supported'] = bool(result['metrics'])
    elif kind == 'models':
        result.update(model_view(data, loc, prefs))
    elif kind == 'ensemble':
        result.update(ensemble_view(data, loc, prefs))
    elif kind == 'runs':
        result.update(previous_runs_view(data, loc, prefs))
    elif kind == 'history':
        result.update(history_view(data, loc, prefs))
        result.update(bundle.get('period', {}))
    result['metadata'] = {'endpoint': bundle.get('source', ''), 'cacheTime': bundle.get('saved', 0),
                          'units': data.get('hourly_units', {}),
                          'processingMilliseconds': data.get('generationtime_ms'),
                          'modelRunTime': 'Not supplied; processing duration is not run initialization'}
    return result
