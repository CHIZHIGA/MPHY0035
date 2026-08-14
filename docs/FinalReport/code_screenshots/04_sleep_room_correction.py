# Verbatim excerpt: src/EighthPhase/core.py, lines 421-461

import pandas as pd

from EighthPhase.core import PipelineParameters, _boolean_runs, _dominant_context


def apply_sleep_correction(
    timeline: pd.DataFrame,
    episodes: pd.DataFrame,
    params: PipelineParameters,
) -> pd.DataFrame:
    updated = timeline.copy()
    for episode in episodes.loc[episodes["main_sleep"]].itertuples(index=False):
        mask = (updated.index >= episode.start) & (updated.index < episode.end)
        updated.loc[mask, "sleep_episode_id"] = int(episode.candidate_id)
        updated.loc[mask, "main_sleep"] = True
        correction_eligible = bool(getattr(episode, "room_correction_eligible", episode.room_supported))
        if not correction_eligible or pd.isna(episode.dominant_beacon):
            continue
        observed_mask = mask & updated["base_beacon"].notna()
        updated.loc[observed_mask, "corrected_beacon"] = episode.dominant_beacon
        updated.loc[observed_mask, "corrected_room"] = episode.dominant_room
        changed = observed_mask & updated["base_beacon"].ne(episode.dominant_beacon)
        updated.loc[changed, "correction_reason"] = "sleep_episode_dominant_room"
        updated.loc[observed_mask, "location_evidence"] = "sleep_episode_locked"

        missing = mask & updated["base_beacon"].isna()
        for start, end in _boolean_runs(missing, params.window_minutes):
            context = pd.Timedelta(minutes=params.gap_context_minutes)
            before = updated.loc[(updated.index >= max(start - context, episode.start)) & (updated.index < start), "base_beacon"]
            after = updated.loc[(updated.index >= end) & (updated.index < min(end + context, episode.end)), "base_beacon"]
            before_n, before_share = _dominant_context(before, str(episode.dominant_beacon))
            after_n, after_share = _dominant_context(after, str(episode.dominant_beacon))
            supported = (
                before_n >= 1
                and after_n >= 1
                and before_share >= params.context_room_share
                and after_share >= params.context_room_share
            )
            gap_mask = (updated.index >= start) & (updated.index < end)
            if supported:
                updated.loc[gap_mask, "corrected_beacon"] = episode.dominant_beacon
                updated.loc[gap_mask, "corrected_room"] = episode.dominant_room
                updated.loc[gap_mask, "correction_reason"] = "sleep_gap_two_sided_room_support"
                updated.loc[gap_mask, "location_evidence"] = "sleep_gap_context_filled"
                updated.loc[gap_mask, "sleep_gap_filled"] = True
    return updated
