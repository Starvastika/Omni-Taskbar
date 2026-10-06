import json
import logging
import traceback
import unicodedata
from typing import Any

from PyQt6.QtCore import QObject, QTimer, QUrl, pyqtSignal
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

logger = logging.getLogger("open_meteo")

HEADER = (b"User-Agent", b"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0")
CACHE_CONTROL = (b"Cache-Control", b"no-cache")

# Open-Meteo API base URLs
FORECAST_BASE_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODING_BASE_URL = "https://geocoding-api.open-meteo.com/v1/search"

# Hourly variables to request
HOURLY_VARS = "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m,precipitation_probability,rain,snowfall"

# Daily variables to request
DAILY_VARS = (
    "weather_code,temperature_2m_max,temperature_2m_min,"
    "apparent_temperature_max,apparent_temperature_min,"
    "precipitation_sum,precipitation_probability_max,"
    "wind_speed_10m_max,wind_direction_10m_dominant,"
    "sunrise,sunset,uv_index_max"
)

# Current weather variables to request
CURRENT_VARS = (
    "temperature_2m,relative_humidity_2m,apparent_temperature,"
    "weather_code,wind_speed_10m,wind_direction_10m,"
    "is_day,precipitation,pressure_msl,cloud_cover"
)

# Search fields
REGION_FIELDS = ("admin3", "admin2", "admin1", "country", "country_code")


class OpenMeteoDataFetcher(QObject):
    """Fetches weather forecast data from the Open-Meteo API."""

    finished = pyqtSignal(dict)

    def __init__(
        self,
        parent: QObject,
        latitude: float,
        longitude: float,
        timeout: int,
        units: str = "metric",
        forecast_days: int = 7,
    ):
        super().__init__(parent)
        self.started = False
        self._active_reply = None
        self._last_failure = None
        self._manager = QNetworkAccessManager(self)
        self._manager.finished.connect(self._handle_response)

        self._fetch_timer = QTimer(self)
        self._fetch_timer.timeout.connect(self.make_request)
        self._timeout = timeout

        # Build the forecast URL
        temp_unit = "fahrenheit" if units == "imperial" else "celsius"
        wind_unit = "mph" if units == "imperial" else "kmh"

        self._url = QUrl(
            f"{FORECAST_BASE_URL}"
            f"?latitude={latitude}&longitude={longitude}"
            f"&hourly={HOURLY_VARS}"
            f"&daily={DAILY_VARS}"
            f"&current={CURRENT_VARS}"
            f"&timezone=auto"
            f"&forecast_days={forecast_days}"
            f"&temperature_unit={temp_unit}"
            f"&wind_speed_unit={wind_unit}"
        )

    def start(self, delayed: bool = False):
        self.started = True
        if not delayed:
            QTimer.singleShot(200, self.make_request)
        self._fetch_timer.start(self._timeout)

    def stop(self):
        self.started = False
        self._fetch_timer.stop()
        if self._active_reply is not None:
            self._active_reply.abort()
            self._active_reply = None

    def make_request(self):
        if not self.started or self._active_reply is not None:
            return
        request = QNetworkRequest(self._url)
        request.setTransferTimeout(15000)
        request.setRawHeader(*HEADER)
        request.setRawHeader(*CACHE_CONTROL)
        self._active_reply = self._manager.get(request)

    def _handle_response(self, reply: QNetworkReply):
        if self._active_reply is reply:
            self._active_reply = None
        try:
            if not self.started or reply.error() == QNetworkReply.NetworkError.OperationCanceledError:
                return
            status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            if reply.error() != QNetworkReply.NetworkError.NoError:
                raise ValueError(f"HTTP {status}: {reply.error().name}")
            data = json.loads(reply.readAll().data().decode())
            if not isinstance(data, dict) or not data.get("current") or not data.get("hourly") or not data.get("daily"):
                raise ValueError("Missing current/hourly/daily forecast data")
            if self._last_failure is not None:
                logger.info("Open-Meteo connection recovered; forecast refreshed")
            self._last_failure = None
            self.finished.emit(data)
        except (ValueError, TypeError, KeyError) as e:
            failure = str(e)
            if failure != self._last_failure:
                logger.warning("Open-Meteo unavailable (%s); retaining the last forecast and retrying with backoff", failure)
                self._last_failure = failure
            self.finished.emit({})
        finally:
            reply.deleteLater()


def fold(value: str) -> str:
    """Lowercase and strip accents for accent-insensitive matching."""
    stripped = unicodedata.normalize("NFKD", value)
    return "".join(c for c in stripped if not unicodedata.combining(c)).casefold()



class GeocodingFetcher(QObject):
    results_ready = pyqtSignal(list)

    def __init__(self, parent: QObject):
        super().__init__(parent)
        self._manager = QNetworkAccessManager(self)
        self._manager.finished.connect(self._handle_response)
        self._generation = 0
        self._pending = None

    def cancel_search(self):
        self._generation += 1
        if self._pending is not None:
            self._pending.abort()
            self._pending = None

    def search(self, query: str, count: int = 100):
        self.cancel_search()
        query = query.strip()
        if len(query) < 2:
            self.results_ready.emit([])
            return
        parts = [p.strip() for p in query.split(",") if p.strip()]
        if len(parts) > 1:
            attempts = [(parts[0], parts[1:])]
        else:
            words = query.split()
            attempts = [(query, [])] + [(" ".join(words[:i]), [" ".join(words[i:])])
                                      for i in range(len(words)-1, 0, -1)]
        self._request(attempts, max(1, min(count, 100)), self._generation)

    def _request(self, attempts, count, generation):
        name, regions = attempts[0]
        encoded = QUrl.toPercentEncoding(name).data().decode()
        url = QUrl(f"{GEOCODING_BASE_URL}?name={encoded}&count={count}&language=en&format=json")
        request = QNetworkRequest(url)
        request.setTransferTimeout(15000)
        request.setAttribute(QNetworkRequest.Attribute.User, [generation, attempts, count])
        request.setRawHeader(*HEADER)
        request.setRawHeader(*CACHE_CONTROL)
        self._pending = self._manager.get(request)

    def _handle_response(self, reply: QNetworkReply):
        try:
            generation, attempts, count = reply.request().attribute(QNetworkRequest.Attribute.User)
            if generation != self._generation:
                return
            self._pending = None
            if reply.error() != QNetworkReply.NetworkError.NoError:
                if reply.error() != QNetworkReply.NetworkError.OperationCanceledError:
                    logger.warning("Geocoding search failed: %s", reply.error().name)
                self.results_ready.emit([])
                return
            results = json.loads(reply.readAll().data().decode()).get("results", [])
            name, regions = attempts[0]
            if regions:
                results = [r for r in results if all(
                    any(fold(r.get(f) or "").startswith(fold(region)) for f in REGION_FIELDS)
                    for region in regions)]
            if not results and len(attempts) > 1:
                self._request(attempts[1:], count, generation)
                return
            # Alias hits such as Austin (formerly Waterloo) should not precede
            # exact city-name matches. Keep all results and prefer population.
            results.sort(key=lambda r: (fold(r.get("name", "")) != fold(name),
                                        -(r.get("population") or 0)))
            self.results_ready.emit(results)
        except (ValueError, TypeError, KeyError) as e:
            logger.warning("Geocoding invalid response: %s", e)
            self.results_ready.emit([])
        finally:
            reply.deleteLater()
