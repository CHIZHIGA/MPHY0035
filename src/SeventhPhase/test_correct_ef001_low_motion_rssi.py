import unittest
from datetime import datetime, timedelta, timezone

from correct_ef001_low_motion_rssi import (
    apply_episode_dominant_room,
    apply_low_motion_vote,
    detect_long_low_motion_episodes,
)


BASE = datetime(2026, 6, 20, tzinfo=timezone(timedelta(hours=-7)))
ROOMS = {"A": "Bedroom", "B": "Living"}


def row(index, beacon, low=True, segment=1):
    return {
        "time": BASE + timedelta(minutes=5 * index),
        "segment_id": segment if beacon else None,
        "observed": bool(beacon),
        "raw_beacon": beacon,
        "raw_location": ROOMS.get(beacon, ""),
        "low_motion": low,
    }


def rssi_for(rows, a=-70.0, b=-75.0):
    result = {}
    for item in rows:
        if item["observed"]:
            result[(item["time"], "A")] = {"mean": a, "count": 1}
            result[(item["time"], "B")] = {"mean": b, "count": 1}
    return result


class AdaptiveVoteTests(unittest.TestCase):
    def test_majority_corrects_low_motion(self):
        rows = [row(i, beacon) for i, beacon in enumerate(["A", "A", "B", "A", "A", "B"])]
        result = apply_low_motion_vote(rows, rssi_for(rows), ROOMS)
        self.assertEqual(result[2]["corrected_beacon"], "A")
        self.assertTrue(result[2]["was_corrected"])

    def test_high_motion_keeps_raw(self):
        rows = [row(i, beacon, low=False) for i, beacon in enumerate(["A", "A", "B", "A", "A", "A"])]
        result = apply_low_motion_vote(rows, rssi_for(rows), ROOMS)
        self.assertEqual(result[2]["corrected_beacon"], "B")
        self.assertEqual(result[2]["correction_reason"], "high_motion_keep_raw")

    def test_vote_tie_uses_mean_rssi(self):
        rows = [row(i, beacon) for i, beacon in enumerate(["A", "B", "A", "B", "A", "B"])]
        result = apply_low_motion_vote(rows, rssi_for(rows, a=-80, b=-65), ROOMS)
        self.assertEqual(result[3]["corrected_beacon"], "B")
        self.assertEqual(result[3]["correction_reason"], "low_motion_60min_vote_tie_rssi")

    def test_missing_is_not_filled(self):
        rows = [row(0, "A"), row(1, ""), row(2, "A", segment=2)]
        result = apply_low_motion_vote(rows, rssi_for(rows), ROOMS)
        self.assertEqual(result[1]["corrected_beacon"], "")
        self.assertEqual(result[1]["correction_reason"], "missing_rssi")

    def test_vote_does_not_cross_segment(self):
        rows = [row(0, "A", segment=1), row(1, "A", segment=1), row(2, "B", segment=2)]
        result = apply_low_motion_vote(rows, rssi_for(rows), ROOMS)
        self.assertEqual(result[2]["corrected_beacon"], "B")
        self.assertEqual(result[2]["vote_window_observed_count"], 1)

    def test_brief_motion_is_bridged_into_one_long_episode(self):
        rows = []
        for index in range(50):
            item = row(index, "A", low=index not in {20, 21, 22})
            item["night_window"] = True
            rows.append(item)
        episodes, _ = detect_long_low_motion_episodes(rows)
        self.assertEqual(len(episodes), 1)
        self.assertEqual(episodes[0]["duration_minutes"], 250)

    def test_episode_dominant_room_locks_observed_windows(self):
        rows = [row(i, beacon) for i, beacon in enumerate(["A", "A", "B", "A", "B", "A"])]
        episode = {"episode_id": 1, "low_motion_share": 1.0, "rows": rows}
        result = apply_episode_dominant_room(rows, [episode], rssi_for(rows), ROOMS)
        self.assertTrue(all(item["corrected_beacon"] == "A" for item in result))


if __name__ == "__main__":
    unittest.main()
