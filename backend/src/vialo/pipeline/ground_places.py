"""Ground origin and candidate stops against Places with split-freshness caching."""

from __future__ import annotations

import datetime as dt
import hashlib
import logging
import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any
from zoneinfo import ZoneInfo

from vialo.domain.opening_hours import derive_coverage_window, normalize_opening_hours
from vialo.domain.timezones import is_same_timezone, validate_local_time
from vialo.models.cache import (
    CacheDateHours,
    CacheProfile,
    CacheQueryResolution,
    CacheRegularHours,
)
from vialo.models.diagnostics import DiagnosticCode
from vialo.models.itinerary import GroundedStop, OpenInterval
from vialo.models.providers import (
    CandidateStop,
    GroundedPlace,
    Location,
    PhotoAttribution,
    PlacePhoto,
)
from vialo.services.place_cache import PlaceCacheRepository
from vialo.services.places_client import PlacesClient, PlacesSearchResult

logger = logging.getLogger(__name__)
PROFILE_TTL_SECONDS = 30 * 24 * 3600
REGULAR_HOURS_TTL_SECONDS = 7 * 24 * 3600
QUERY_RESOLUTION_TTL_SECONDS = 7 * 24 * 3600


def _query_hash(query: str, locality: str) -> str:
    payload = f"{query.casefold().strip()}|{locality.casefold().strip()}"
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


def _date_hours_expiry(requested_date: dt.date, tz_id: str) -> int:
    next_midnight = validate_local_time(dt.time(), requested_date + dt.timedelta(days=1), tz_id)
    return int((next_midnight + dt.timedelta(hours=6)).timestamp())


def _normalized_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).casefold()
    return " ".join(re.findall(r"[\w]+", normalized, flags=re.UNICODE))


def _select_unambiguous_result(
    query: str, locality: str, results: list[PlacesSearchResult]
) -> PlacesSearchResult | None:
    """Prefer exact/local results and reject close competing matches."""
    query_norm = _normalized_text(query)
    query_tokens = set(query_norm.split())
    locality_tokens = {token for token in _normalized_text(locality).split() if len(token) >= 3}
    ranked: list[tuple[tuple[int, int, float, float], PlacesSearchResult]] = []

    for result in results:
        if not result.place_id or not result.display_name:
            continue
        name_norm = _normalized_text(result.display_name)
        name_tokens = set(name_norm.split())
        exact = int(name_norm == query_norm)
        locality_match = int(
            bool(locality_tokens & set(_normalized_text(result.formatted_address).split()))
        )
        token_coverage = (
            len(query_tokens & name_tokens) / len(query_tokens) if query_tokens else 0.0
        )
        similarity = SequenceMatcher(None, query_norm, name_norm).ratio()
        ranked.append(((exact, locality_match, token_coverage, similarity), result))

    if not ranked:
        return None
    ranked.sort(key=lambda item: item[0], reverse=True)
    top_score, top = ranked[0]
    exact, locality_match, token_coverage, similarity = top_score
    strong_name = bool(exact or token_coverage >= 0.75 or similarity >= 0.78)
    if not strong_name:
        return None

    if len(ranked) > 1:
        second_score, _ = ranked[1]
        # Equal-quality top matches are ambiguous. A locality match or a clear name
        # score lead is required for a non-exact fuzzy resolution.
        if top_score == second_score:
            return None
        clear_lead = (token_coverage + similarity) - (second_score[2] + second_score[3]) >= 0.10
        if not exact and not locality_match and not clear_lead:
            return None

    return top


def _result_to_grounded_place(result: PlacesSearchResult) -> GroundedPlace:
    photos: list[PlacePhoto] = []
    for photo in result.photos:
        photos.append(
            PlacePhoto(
                name=photo.get("name", ""),
                width_px=photo.get("widthPx", 0),
                height_px=photo.get("heightPx", 0),
                author_attributions=[
                    PhotoAttribution(
                        display_name=value.get("displayName", ""),
                        uri=value.get("uri", ""),
                        photo_uri=value.get("photoUri"),
                    )
                    for value in photo.get("authorAttributions", [])
                ],
            )
        )
    return GroundedPlace(
        place_id=result.place_id,
        display_name=result.display_name,
        formatted_address=result.formatted_address,
        location=Location(latitude=result.latitude, longitude=result.longitude),
        primary_type=result.primary_type,
        time_zone_id=result.time_zone_id or "",
        photos=photos,
    )


def _profile_to_place(profile: CacheProfile) -> GroundedPlace:
    return GroundedPlace(
        place_id=profile.place_id,
        display_name=profile.display_name,
        formatted_address=profile.formatted_address,
        location=profile.location,
        primary_type=profile.primary_type,
        time_zone_id=profile.time_zone_id,
        photos=profile.photos,
    )


def _place_to_cache_profile(place: GroundedPlace, now: dt.datetime) -> CacheProfile:
    return CacheProfile(
        place_id=place.place_id,
        display_name=place.display_name,
        formatted_address=place.formatted_address,
        location=place.location,
        primary_type=place.primary_type,
        time_zone_id=place.time_zone_id,
        photos=place.photos,
        fetched_at=now,
        expires_at=int(now.timestamp()) + PROFILE_TTL_SECONDS,
    )


class GroundingDiagnostic:
    def __init__(self, candidate_index: int, name: str, code: DiagnosticCode, detail: str) -> None:
        self.candidate_index = candidate_index
        self.name = name
        self.code = code
        self.detail = detail


def _diagnostic(candidate: CandidateStop, code: DiagnosticCode, detail: str) -> GroundingDiagnostic:
    return GroundingDiagnostic(candidate.candidate_index, candidate.name, code, detail)


def _read_cached_place(
    cache: PlaceCacheRepository | None, query_hash: str
) -> tuple[GroundedPlace | None, str | None]:
    if cache is None:
        return None, None
    try:
        place_id = cache.get_query_resolution(query_hash)
        if place_id is None:
            return None, None
        profile = cache.get_profile(place_id)
        return (_profile_to_place(profile), place_id) if profile is not None else (None, place_id)
    except Exception:
        logger.debug("Place cache read failed", exc_info=True)
        return None, None


def _write_profile_cache(
    cache: PlaceCacheRepository | None,
    query_hash: str,
    place: GroundedPlace,
    now: dt.datetime,
) -> None:
    if cache is None:
        return
    try:
        cache.put_query_resolution(
            CacheQueryResolution(
                query_hash=query_hash,
                place_id=place.place_id,
                fetched_at=now,
                expires_at=int(now.timestamp()) + QUERY_RESOLUTION_TTL_SECONDS,
            )
        )
        cache.put_profile(_place_to_cache_profile(place, now))
    except Exception:
        logger.debug("Place cache write failed", exc_info=True)


def ground_origin(
    origin_query: str,
    locality: str,
    client: PlacesClient,
    cache: PlaceCacheRepository | None = None,
) -> GroundedPlace | None:
    """Resolve the independent fixed origin, rejecting ambiguous results."""
    query_hash = _query_hash(origin_query, locality)
    cached, _ = _read_cached_place(cache, query_hash)
    if cached is not None and cached.time_zone_id:
        return cached

    selected = _select_unambiguous_result(
        origin_query, locality, client.search_text(origin_query, locality)
    )
    if selected is None or not selected.time_zone_id:
        return None
    place = _result_to_grounded_place(selected)
    _write_profile_cache(cache, query_hash, place, dt.datetime.now(dt.UTC))
    return place


def ground_places(
    candidates: list[CandidateStop],
    locality: str,
    client: PlacesClient,
    requested_date: dt.date,
    cache: PlaceCacheRepository | None = None,
    origin_tz: str | None = None,
) -> tuple[list[GroundedStop], list[GroundingDiagnostic]]:
    """Resolve candidates, hours, timezone, duplicates, and cache freshness."""
    grounded: list[GroundedStop] = []
    diagnostics: list[GroundingDiagnostic] = []
    seen: dict[str, tuple[int, int]] = {}
    now = dt.datetime.now(dt.UTC)

    for candidate in candidates:
        query_hash = _query_hash(candidate.name, locality)
        place, cached_place_id = _read_cached_place(cache, query_hash)
        cached_date: CacheDateHours | None = None
        cached_regular: CacheRegularHours | None = None

        if cache is not None and cached_place_id is not None:
            try:
                cached_date = cache.get_date_hours(cached_place_id, requested_date.isoformat())
                cached_regular = cache.get_regular_hours(cached_place_id)
            except Exception:
                logger.debug("Hours cache read failed", exc_info=True)

        inside_current_window = False
        if place is not None and place.time_zone_id:
            fetch_date = now.astimezone(ZoneInfo(place.time_zone_id)).date()
            start, end = derive_coverage_window(fetch_date)
            inside_current_window = start <= requested_date <= end

        needs_live = (
            place is None
            or (inside_current_window and cached_date is None)
            or (not inside_current_window and cached_regular is None)
        )
        live_result: PlacesSearchResult | None = None

        if needs_live:
            live_result = _select_unambiguous_result(
                candidate.name, locality, client.search_text(candidate.name, locality)
            )
            if live_result is None:
                diagnostics.append(
                    _diagnostic(
                        candidate,
                        DiagnosticCode.PLACE_NOT_FOUND,
                        f"Could not resolve {candidate.name} unambiguously in {locality}",
                    )
                )
                continue
            if not live_result.time_zone_id:
                diagnostics.append(
                    _diagnostic(candidate, DiagnosticCode.PLACE_NOT_FOUND, "Place has no timezone")
                )
                continue
            place = _result_to_grounded_place(live_result)
            _write_profile_cache(cache, query_hash, place, now)
            fetch_date = now.astimezone(ZoneInfo(place.time_zone_id)).date()
            start, end = derive_coverage_window(fetch_date)
            inside_current_window = start <= requested_date <= end

        if place is None:
            diagnostics.append(
                _diagnostic(candidate, DiagnosticCode.PLACE_NOT_FOUND, "Place profile unavailable")
            )
            continue
        if origin_tz is not None and not is_same_timezone(place.time_zone_id, origin_tz):
            diagnostics.append(
                _diagnostic(
                    candidate,
                    DiagnosticCode.OUTSIDE_LOCALITY,
                    f"{candidate.name} is outside the origin timezone",
                )
            )
            continue

        existing = seen.get(place.place_id)
        if existing is not None and (candidate.priority, candidate.candidate_index) >= existing:
            diagnostics.append(
                _diagnostic(
                    candidate,
                    DiagnosticCode.DUPLICATE_PLACE,
                    f"Duplicate Place ID; kept candidate {existing[1]}",
                )
            )
            continue
        if existing is not None:
            grounded = [stop for stop in grounded if stop.place.place_id != place.place_id]
            diagnostics.append(
                GroundingDiagnostic(
                    existing[1],
                    candidate.name,
                    DiagnosticCode.DUPLICATE_PLACE,
                    f"Superseded by higher-priority candidate {candidate.candidate_index}",
                )
            )
        seen[place.place_id] = (candidate.priority, candidate.candidate_index)

        current_hours: dict[str, Any] | None
        regular_hours: dict[str, Any] | None
        if live_result is not None:
            current_hours = live_result.current_opening_hours
            regular_hours = live_result.regular_opening_hours
            if cache is not None:
                try:
                    if regular_hours is not None:
                        cache.put_regular_hours(
                            CacheRegularHours(
                                place_id=place.place_id,
                                periods=regular_hours.get("periods", []),
                                fetched_at=now,
                                expires_at=int(now.timestamp()) + REGULAR_HOURS_TTL_SECONDS,
                            )
                        )
                    if current_hours is not None and inside_current_window:
                        cache.put_date_hours(
                            CacheDateHours(
                                place_id=place.place_id,
                                date=requested_date.isoformat(),
                                periods=current_hours.get("periods", []),
                                source="current",
                                fetched_at=now,
                                expires_at=_date_hours_expiry(requested_date, place.time_zone_id),
                            )
                        )
                except Exception:
                    logger.debug("Hours cache write failed", exc_info=True)
        else:
            current_hours = {"periods": cached_date.periods} if cached_date is not None else None
            regular_hours = (
                {"periods": cached_regular.periods} if cached_regular is not None else None
            )

        hours = normalize_opening_hours(
            current_hours=current_hours,
            regular_hours=regular_hours,
            requested_date=requested_date,
            tz_id=place.time_zone_id,
            fetch_instant=now,
        )
        if isinstance(hours, DiagnosticCode):
            details = {
                DiagnosticCode.CLOSED_ON_DATE: f"{candidate.name} is closed on {requested_date}",
                DiagnosticCode.HOURS_UNAVAILABLE: (
                    f"Opening hours are unavailable for {candidate.name}"
                ),
                DiagnosticCode.LOCAL_TIME_AMBIGUOUS: (
                    f"Opening hours for {candidate.name} cross an ambiguous local time"
                ),
            }
            diagnostics.append(_diagnostic(candidate, hours, details.get(hours, hours.value)))
            continue

        intervals: list[OpenInterval] = hours
        grounded.append(
            GroundedStop(
                candidate_index=candidate.candidate_index,
                name=candidate.name,
                category=candidate.category,
                priority=candidate.priority,
                visit_duration_minutes=candidate.visit_duration_minutes,
                duration_source=candidate.duration_source,
                place=place,
                hours_source="current" if inside_current_window else "regular",
                open_intervals=intervals,
            )
        )

    grounded.sort(key=lambda stop: stop.candidate_index)
    return grounded, diagnostics
