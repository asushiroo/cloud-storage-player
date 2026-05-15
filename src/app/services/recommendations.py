from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from app.core.config import Settings
from app.models.library import Video
from app.models.watching import RecommendationShelf, TagPreference, VideoWatchSession
from app.repositories.videos import (
    get_video,
    list_videos,
    update_video_analytics,
)
from app.repositories.watching import (
    create_watch_session,
    get_watch_session,
    list_all_watch_sessions,
    list_tag_preferences,
    list_video_watch_sessions,
    update_watch_session,
    upsert_tag_preference,
)

PRIMARY_TAG_WEIGHT = 0.35
SECONDARY_TAG_WEIGHT = 0.65
DEFAULT_HIGHLIGHT_BUCKET_COUNT = 20
VALID_PLAY_THRESHOLD_RATIO = 0.10
CONTINUE_WATCH_MIN_PROGRESS = 0.02
CONTINUE_WATCH_MAX_PROGRESS = 0.95


@dataclass(slots=True)
class WatchHeartbeatResult:
    session_token: str
    video: Video


@dataclass(slots=True)
class SimilarVideoMatch:
    video: Video
    similarity_score: float


def record_watch_heartbeat(
    settings: Settings,
    *,
    video_id: int,
    session_token: str | None,
    position_seconds: float,
    watched_seconds_delta: float,
    completed: bool,
) -> WatchHeartbeatResult:
    video = get_video(settings, video_id)
    if video is None:
        raise ValueError(f"Video not found: {video_id}")

    token = (session_token or "").strip() or uuid4().hex
    session = get_watch_session(settings, session_token=token)
    if session is None:
        session = create_watch_session(settings, video_id=video_id, session_token=token)
    elif session.video_id != video_id:
        raise ValueError("session_token does not belong to this video.")

    duration = max(float(video.duration_seconds or 0), 0.0)
    updated_watch_seconds = max(session.accumulated_watch_seconds + max(watched_seconds_delta, 0.0), 0.0)
    updated_position = max(position_seconds, 0.0)
    updated_max_position = max(session.max_position_seconds, updated_position)
    threshold_seconds = duration * VALID_PLAY_THRESHOLD_RATIO if duration > 0 else 0
    valid_play_recorded = session.valid_play_recorded or (
        threshold_seconds > 0 and updated_watch_seconds >= threshold_seconds
    )
    bounce_recorded = session.bounce_recorded or (
        completed and threshold_seconds > 0 and updated_watch_seconds < threshold_seconds
    )

    update_watch_session(
        settings,
        token,
        accumulated_watch_seconds=updated_watch_seconds,
        last_position_seconds=updated_position,
        max_position_seconds=updated_max_position,
        valid_play_recorded=valid_play_recorded,
        bounce_recorded=bounce_recorded,
        completed=completed,
    )

    updated_video = recalculate_video_analytics(settings, video_id=video_id)
    return WatchHeartbeatResult(session_token=token, video=updated_video)


def record_watch_flush(
    settings: Settings,
    *,
    video_id: int,
    session_token: str | None,
    position_seconds: float,
    watched_seconds_delta: float,
    completed: bool,
) -> WatchHeartbeatResult:
    return record_watch_heartbeat(
        settings,
        video_id=video_id,
        session_token=session_token,
        position_seconds=position_seconds,
        watched_seconds_delta=watched_seconds_delta,
        completed=completed,
    )


def recalculate_video_analytics(settings: Settings, *, video_id: int) -> Video:
    video = get_video(settings, video_id)
    if video is None:
        raise ValueError(f"Video not found: {video_id}")

    sessions = list_video_watch_sessions(settings, video_id=video_id)
    duration = max(float(video.duration_seconds or 0), 0.0)
    valid_play_count = sum(1 for session in sessions if session.valid_play_recorded)
    total_session_count = len(sessions)
    total_watch_seconds = sum(max(session.accumulated_watch_seconds, 0.0) for session in sessions)
    bounce_count = sum(1 for session in sessions if session.bounce_recorded)
    bounce_rate = bounce_count / max(total_session_count, 1)
    avg_completion_ratio = _clamp(
        total_watch_seconds / max(valid_play_count * duration, 1.0),
        0.0,
        1.0,
    )
    rewatch_score = min(valid_play_count / 5.0, 1.0)
    interest_score = _clamp(
        0.50 * avg_completion_ratio + 0.30 * rewatch_score + 0.20 * (1.0 - bounce_rate),
        0.0,
        1.0,
    )
    last_session = max(
        sessions,
        key=lambda session: (session.last_activity_at, session.id),
        default=None,
    )
    last_watched_at = last_session.last_activity_at if last_session is not None else None
    last_position_seconds = last_session.last_position_seconds if last_session is not None else 0.0
    highlight_bucket_count = max(video.highlight_bucket_count or DEFAULT_HIGHLIGHT_BUCKET_COUNT, 1)
    highlight_heatmap = _build_highlight_heatmap(
        sessions=sessions,
        duration_seconds=duration,
        bucket_count=highlight_bucket_count,
    )
    highlight_start_seconds, highlight_end_seconds = _derive_highlight_range(
        heatmap=highlight_heatmap,
        duration_seconds=duration,
    )
    popularity_score = _compute_video_popularity_score(
        settings,
        current_video_id=video_id,
        current_valid_play_count=valid_play_count,
        current_total_watch_seconds=total_watch_seconds,
        current_last_watched_at=last_watched_at,
    )
    resume_score = _compute_resume_score(
        duration_seconds=duration,
        last_position_seconds=last_position_seconds,
        last_watched_at=last_watched_at,
    )
    recommendation_score = max(video.recommendation_score, 0.0)
    cache_priority = _compute_cache_priority(
        valid_play_count=valid_play_count,
        resume_score=resume_score,
        recommendation_score=recommendation_score,
        like_count=video.like_count,
    )

    updated_video = update_video_analytics(
        settings,
        video_id,
        valid_play_count=valid_play_count,
        total_session_count=total_session_count,
        total_watch_seconds=total_watch_seconds,
        last_watched_at=last_watched_at,
        last_position_seconds=last_position_seconds,
        avg_completion_ratio=avg_completion_ratio,
        bounce_count=bounce_count,
        bounce_rate=bounce_rate,
        rewatch_score=rewatch_score,
        interest_score=interest_score,
        popularity_score=popularity_score,
        resume_score=resume_score,
        recommendation_score=recommendation_score,
        cache_priority=cache_priority,
        highlight_start_seconds=highlight_start_seconds,
        highlight_end_seconds=highlight_end_seconds,
        highlight_bucket_count=highlight_bucket_count,
        highlight_heatmap=highlight_heatmap,
    )
    _refresh_tag_preferences(settings)
    _refresh_all_recommendation_scores(settings)
    refreshed_video = get_video(settings, video_id)
    if refreshed_video is None:
        raise ValueError(f"Video not found after analytics refresh: {video_id}")
    return refreshed_video


def build_recommendation_shelf(settings: Settings) -> RecommendationShelf:
    videos = list_videos(settings)
    sorted_recommended = sorted(
        videos,
        key=lambda video: (
            -video.recommendation_score,
            -video.popularity_score,
            video.title.casefold(),
            video.id,
        ),
    )
    continue_watching = sorted(
        (
            video
            for video in videos
            if video.resume_score > 0
            and video.duration_seconds
            and video.last_position_seconds > 0
        ),
        key=lambda video: (
            -video.resume_score,
            -(video.last_position_seconds or 0),
            video.title.casefold(),
            video.id,
        ),
    )
    popular = sorted(
        videos,
        key=lambda video: (
            -video.popularity_score,
            -video.valid_play_count,
            video.title.casefold(),
            video.id,
        ),
    )
    return RecommendationShelf(
        recommended_videos=[video.id for video in sorted_recommended[:12]],
        continue_watching_videos=[video.id for video in continue_watching[:12]],
        popular_videos=[video.id for video in popular[:12]],
    )


def find_similar_videos(
    settings: Settings,
    *,
    video_id: int,
    limit: int = 12,
) -> list[Video]:
    videos = list_videos(settings)
    current = next((video for video in videos if video.id == video_id), None)
    if current is None:
        raise ValueError(f"Video not found: {video_id}")

    matches: list[SimilarVideoMatch] = []
    for candidate in videos:
        if candidate.id == current.id:
            continue
        similarity_score = _compute_similarity_score(current, candidate)
        if similarity_score <= 0:
            continue
        matches.append(SimilarVideoMatch(video=candidate, similarity_score=similarity_score))

    matches.sort(
        key=lambda item: (
            -item.similarity_score,
            -item.video.recommendation_score,
            -item.video.popularity_score,
            item.video.title.casefold(),
            item.video.id,
        )
    )
    return [match.video for match in matches[:limit]]


def refresh_recommendation_analytics(settings: Settings) -> None:
    for video in list_videos(settings):
        recalculate_video_analytics(settings, video_id=video.id)


def _refresh_tag_preferences(settings: Settings) -> None:
    videos = list_videos(settings)
    primary_stats: dict[str, tuple[float, int]] = {}
    secondary_stats: dict[str, tuple[float, int]] = {}
    for video in videos:
        primary_tags, secondary_tags = _split_video_tags(video)
        for tag in primary_tags:
            interest_sum, exposure = primary_stats.get(tag, (0.0, 0))
            primary_stats[tag] = (interest_sum + video.interest_score, exposure + 1)
        for tag in secondary_tags:
            interest_sum, exposure = secondary_stats.get(tag, (0.0, 0))
            secondary_stats[tag] = (interest_sum + video.interest_score, exposure + 1)

    for tag, (interest_sum, exposure) in primary_stats.items():
        upsert_tag_preference(
            settings,
            tag_value=tag,
            tag_level="primary",
            interest_sum=interest_sum,
            interest_count=exposure,
            preference_score=interest_sum / max(exposure, 1),
            exposure_count=exposure,
        )
    for tag, (interest_sum, exposure) in secondary_stats.items():
        upsert_tag_preference(
            settings,
            tag_value=tag,
            tag_level="secondary",
            interest_sum=interest_sum,
            interest_count=exposure,
            preference_score=interest_sum / max(exposure, 1),
            exposure_count=exposure,
        )


def _refresh_all_recommendation_scores(settings: Settings) -> None:
    videos = list_videos(settings)
    preferences = list_tag_preferences(settings)
    primary_preferences = {
        preference.tag_value.casefold(): preference
        for preference in preferences
        if preference.tag_level == "primary"
    }
    secondary_preferences = {
        preference.tag_value.casefold(): preference
        for preference in preferences
        if preference.tag_level == "secondary"
    }

    for video in videos:
        primary_tags, secondary_tags = _split_video_tags(video)
        primary_match = _average_preference(primary_tags, primary_preferences)
        secondary_match = _average_preference(secondary_tags, secondary_preferences)
        tag_match_score = PRIMARY_TAG_WEIGHT * primary_match + SECONDARY_TAG_WEIGHT * secondary_match
        primary_explore = _average_exploration(primary_tags, primary_preferences)
        secondary_explore = _average_exploration(secondary_tags, secondary_preferences)
        exploration_score = PRIMARY_TAG_WEIGHT * primary_explore + SECONDARY_TAG_WEIGHT * secondary_explore
        base_recommendation_score = (
            0.65 * tag_match_score
            + 0.20 * exploration_score
            + 0.10 * video.popularity_score
            + 0.02 * _clamp(video.like_count / 99.0, 0.0, 1.0)
        )
        novelty_factor = _novelty_factor(video.valid_play_count)
        recommendation_score = _clamp(base_recommendation_score * novelty_factor, 0.0, 1.0)
        cache_priority = _compute_cache_priority(
            valid_play_count=video.valid_play_count,
            resume_score=video.resume_score,
            recommendation_score=recommendation_score,
            like_count=video.like_count,
        )
        update_video_analytics(
            settings,
            video.id,
            valid_play_count=video.valid_play_count,
            total_session_count=video.total_session_count,
            total_watch_seconds=video.total_watch_seconds,
            last_watched_at=video.last_watched_at,
            last_position_seconds=video.last_position_seconds,
            avg_completion_ratio=video.avg_completion_ratio,
            bounce_count=video.bounce_count,
            bounce_rate=video.bounce_rate,
            rewatch_score=video.rewatch_score,
            interest_score=video.interest_score,
            popularity_score=video.popularity_score,
            resume_score=video.resume_score,
            recommendation_score=recommendation_score,
            cache_priority=cache_priority,
            highlight_start_seconds=video.highlight_start_seconds,
            highlight_end_seconds=video.highlight_end_seconds,
            highlight_bucket_count=video.highlight_bucket_count,
            highlight_heatmap=video.highlight_heatmap,
        )


def _split_video_tags(video: Video) -> tuple[list[str], list[str]]:
    primary_tags: list[str] = []
    secondary_tags: list[str] = []
    for raw_tag in video.tags:
        tag = raw_tag.strip()
        if not tag:
            continue
        if tag.casefold().startswith("secondary:"):
            secondary_tags.append(tag[len("secondary:") :].strip())
            continue
        slash_parts = [part.strip() for part in tag.split("/") if part.strip()]
        if len(slash_parts) > 1:
            primary_tags.append(slash_parts[0])
            secondary_tags.append("/".join(slash_parts[1:]))
            continue
        primary_tags.append(tag)
    return primary_tags, secondary_tags


def _average_preference(tags: list[str], preferences: dict[str, TagPreference]) -> float:
    if not tags:
        return 0.0
    values = [preferences[tag.casefold()].preference_score for tag in tags if tag.casefold() in preferences]
    if not values:
        return 0.0
    return sum(values) / len(values)


def _average_exploration(tags: list[str], preferences: dict[str, TagPreference]) -> float:
    if not tags:
        return 0.0
    values: list[float] = []
    for tag in tags:
        preference = preferences.get(tag.casefold())
        if preference is None:
            continue
        exposure_penalty = min(preference.exposure_count / 5.0, 1.0)
        values.append(preference.preference_score * (1.0 - exposure_penalty))
    if not values:
        return 0.0
    return sum(values) / len(values)


def _novelty_factor(valid_play_count: int) -> float:
    if valid_play_count <= 0:
        return 1.0
    if valid_play_count == 1:
        return 0.25
    return 0.05


def _compute_video_popularity_score(
    settings: Settings,
    *,
    current_video_id: int,
    current_valid_play_count: int,
    current_total_watch_seconds: float,
    current_last_watched_at: str | None,
) -> float:
    videos = list_videos(settings)
    max_valid_play_count = max([current_valid_play_count, *(video.valid_play_count for video in videos)], default=1)
    max_watch_seconds = max([current_total_watch_seconds, *(video.total_watch_seconds for video in videos)], default=1.0)
    normalized_play_count = current_valid_play_count / max(max_valid_play_count, 1)
    normalized_watch_seconds = current_total_watch_seconds / max(max_watch_seconds, 1.0)
    recency_score = 0.0
    if current_last_watched_at is not None:
        recency_values = [1.0 if video.last_watched_at else 0.0 for video in videos if video.id != current_video_id]
        recency_score = max([1.0, *recency_values], default=1.0)
    return _clamp(
        0.40 * normalized_play_count + 0.40 * normalized_watch_seconds + 0.20 * recency_score,
        0.0,
        1.0,
    )


def _compute_resume_score(
    *,
    duration_seconds: float,
    last_position_seconds: float,
    last_watched_at: str | None,
) -> float:
    if duration_seconds <= 0 or last_position_seconds <= 0 or last_watched_at is None:
        return 0.0
    progress_ratio = _clamp(last_position_seconds / duration_seconds, 0.0, 1.0)
    if progress_ratio < CONTINUE_WATCH_MIN_PROGRESS or progress_ratio >= CONTINUE_WATCH_MAX_PROGRESS:
        return 0.0
    incomplete_ratio = 1.0 - progress_ratio
    return _clamp(0.65 * progress_ratio + 0.35 * incomplete_ratio, 0.0, 1.0)


def _compute_cache_priority(
    *,
    valid_play_count: int,
    resume_score: float,
    recommendation_score: float,
    like_count: int,
) -> float:
    watched_penalty = min(valid_play_count * 0.25, 0.8)
    like_boost = _clamp(like_count / 99.0, 0.0, 1.0) * 0.15
    return _clamp(0.50 * recommendation_score + 0.35 * resume_score + like_boost - watched_penalty, 0.0, 1.0)


def _compute_similarity_score(current: Video, candidate: Video) -> float:
    current_primary, current_secondary = _split_video_tags(current)
    candidate_primary, candidate_secondary = _split_video_tags(candidate)
    primary_score = _jaccard_similarity(current_primary, candidate_primary)
    secondary_score = _jaccard_similarity(current_secondary, candidate_secondary)
    if primary_score <= 0 and secondary_score <= 0:
        return 0.0
    return _clamp(
        PRIMARY_TAG_WEIGHT * primary_score
        + SECONDARY_TAG_WEIGHT * secondary_score
        + 0.10 * candidate.popularity_score
        + 0.05 * candidate.interest_score,
        0.0,
        1.5,
    )


def _jaccard_similarity(left: list[str], right: list[str]) -> float:
    left_set = {value.casefold() for value in left if value.strip()}
    right_set = {value.casefold() for value in right if value.strip()}
    if not left_set or not right_set:
        return 0.0
    intersection = len(left_set & right_set)
    union = len(left_set | right_set)
    if union <= 0:
        return 0.0
    return intersection / union


def _build_highlight_heatmap(
    *,
    sessions: list[VideoWatchSession],
    duration_seconds: float,
    bucket_count: int,
) -> list[float]:
    if duration_seconds <= 0 or bucket_count <= 0:
        return []
    heatmap = [0.0 for _ in range(bucket_count)]
    bucket_width = duration_seconds / bucket_count
    if bucket_width <= 0:
        return heatmap
    for session in sessions:
        watched_until = _clamp(session.max_position_seconds, 0.0, duration_seconds)
        watched_for = _clamp(session.accumulated_watch_seconds, 0.0, duration_seconds)
        watched_from = max(watched_until - watched_for, 0.0)
        start_bucket = min(int(watched_from / bucket_width), bucket_count - 1)
        end_bucket = min(int(watched_until / bucket_width), bucket_count - 1)
        for index in range(start_bucket, end_bucket + 1):
            bucket_start = index * bucket_width
            bucket_end = min(bucket_start + bucket_width, duration_seconds)
            overlap_start = max(watched_from, bucket_start)
            overlap_end = min(watched_until, bucket_end)
            if overlap_end > overlap_start:
                heatmap[index] += overlap_end - overlap_start
    return heatmap


def _derive_highlight_range(
    *,
    heatmap: list[float],
    duration_seconds: float,
) -> tuple[float | None, float | None]:
    if not heatmap or duration_seconds <= 0:
        return None, None
    peak_index = max(range(len(heatmap)), key=lambda index: heatmap[index], default=0)
    if heatmap[peak_index] <= 0:
        return None, None
    start_index = peak_index
    end_index = peak_index
    threshold = heatmap[peak_index] * 0.6
    while start_index - 1 >= 0 and heatmap[start_index - 1] >= threshold:
        start_index -= 1
    while end_index + 1 < len(heatmap) and heatmap[end_index + 1] >= threshold:
        end_index += 1
    bucket_width = duration_seconds / len(heatmap)
    start_seconds = start_index * bucket_width
    end_seconds = min(duration_seconds, (end_index + 1) * bucket_width)
    return start_seconds, end_seconds


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))
