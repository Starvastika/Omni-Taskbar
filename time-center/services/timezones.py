"""Retain the small immutable IANA zone objects used by saved cities.

ZoneInfo's eight-entry strong cache thrashes when a timeline uses more zones;
its weak cache cannot retain these short-lived conversion objects on its own.
Transitions are still evaluated for each actual datetime, including DST folds.
"""
from functools import lru_cache
from zoneinfo import ZoneInfo

@lru_cache(maxsize=1024)
def zone(name):
    return ZoneInfo(name)
