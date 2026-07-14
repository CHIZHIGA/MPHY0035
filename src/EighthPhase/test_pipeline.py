from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from EighthPhase.core import (
    PipelineParameters,
    apply_sleep_correction,
    build_raw_rssi_features,
    choose_ordered_clustering,
    classify_away_runs,
    classify_movement,
    infer_bedroom,
    run_inference,
    select_main_sleep,
)
from EighthPhase.io import _quality_filter, load_steps
from EighthPhase.evaluation import analyse_copresence
from EighthPhase.pressure import _auto_groups, constrain_rssi_with_pressure


def grid(count: int) -> pd.DatetimeIndex:
    return pd.date_range("2026-01-01", periods=count, freq="5min", tz="UTC")


class ClusteringTests(unittest.TestCase):
    def test_movement_clustering_uses_lowest_state(self):
        index = grid(120)
        values = pd.Series(np.r_[np.full(60, 0.004), np.full(60, 0.08)], index=index)
        result, diagnostics, audit = classify_movement(values, "acc", PipelineParameters())
        self.assertEqual(audit["movement_k"], 2)
        self.assertTrue(result.iloc[:60]["low_motion"].all())
        self.assertFalse(result.iloc[60:]["low_motion"].any())
        self.assertTrue(diagnostics["selected"].any())

    def test_near_best_rule_prefers_smaller_k(self):
        values = pd.Series(np.r_[np.zeros(50), np.ones(50)])
        states, centers, _ = choose_ordered_clustering(values, (2, 3), 10, 0.05, 0.25, 0.02)
        self.assertEqual(len(centers), 2)
        self.assertEqual(set(states.dropna().astype(int)), {1, 2})

    def test_sleep_k2_accepts_four_episodes_with_two_per_class(self):
        candidates = pd.DataFrame(
            {
                "duration_minutes": [75.0, 90.0, 420.0, 480.0],
            }
        )
        episodes, diagnostics, audit = select_main_sleep(candidates, PipelineParameters())
        self.assertTrue(audit["sleep_resolved"])
        self.assertEqual(int(episodes["main_sleep"].sum()), 2)
        self.assertTrue(diagnostics.loc[diagnostics["k"].eq(2), "accepted"].iloc[0])

    def test_sleep_rejects_singleton_duration_cluster(self):
        candidates = pd.DataFrame(
            {
                "duration_minutes": [75.0, 80.0, 90.0, 100.0, 1000.0],
            }
        )
        _, diagnostics, audit = select_main_sleep(candidates, PipelineParameters())
        self.assertFalse(audit["sleep_resolved"])
        self.assertFalse(diagnostics["accepted"].any())

    def test_borderline_silhouette_needs_center_ratio(self):
        values = pd.Series(np.log([95, 350, 190, 225, 330, 305, 165]))
        states, centers, diagnostics = choose_ordered_clustering(
            values,
            (2,),
            2,
            0,
            0.50,
            0,
            silhouette_borderline_min=0.45,
            borderline_min_center_ratio=2.0,
        )
        self.assertIsNotNone(centers)
        self.assertFalse(states.isna().any())
        self.assertEqual(diagnostics.iloc[0]["separation_tier"], "borderline")


class InputTests(unittest.TestCase):
    def test_low_coverage_rssi_is_kept_missing(self):
        index = grid(3)
        mean = pd.DataFrame({"A": [-60.0, -61.0, -62.0]}, index=index)
        count = pd.DataFrame({"A": [10, 1, 10]}, index=index)
        filtered, _, coverage = _quality_filter(mean, count)
        self.assertTrue(pd.isna(filtered.iloc[1, 0]))
        self.assertLess(float(coverage.iloc[1]), 1.0)

    def test_rssi_tie_uses_stable_beacon_order(self):
        index = grid(1)
        mean = pd.DataFrame({"A": [-60.0], "B": [-60.0]}, index=index)
        result = build_raw_rssi_features(mean, mean.notna().astype(int), {"A": "Living", "B": "Bedroom"})
        self.assertEqual(result.iloc[0]["raw_strongest_beacon"], "A")

    def test_step_counter_reset_is_not_negative_motion(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "steps.csv"
            path.write_text(
                "1767225600000,,100\n"
                "1767225660000,,110\n"
                "1767225720000,,3\n"
                "1767225780000,,8\n"
            )
            increments, online = load_steps(path)
        self.assertEqual(float(increments.sum()), 15.0)
        self.assertTrue(online.all())

    def test_equal_step_counter_reconstructs_bounded_zero_plateau(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "steps.csv"
            path.write_text(
                "1767225600000,,100\n"
                "1767227460000,,100\n"  # 31 minutes later
            )
            increments, online = load_steps(path)
        expected = pd.date_range("2026-01-01 00:00", "2026-01-01 00:30", freq="5min", tz="UTC")
        self.assertTrue(expected.isin(increments.index).all())
        self.assertTrue(increments.reindex(expected).eq(0).all())
        self.assertTrue(online.reindex(expected).all())

    def test_increasing_step_counter_does_not_fill_interval_censored_gap(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "steps.csv"
            path.write_text(
                "1767225600000,,100\n"
                "1767227460000,,110\n"  # movement timing within the gap is unknown
            )
            increments, _ = load_steps(path)
        self.assertNotIn(pd.Timestamp("2026-01-01 00:05", tz="UTC"), increments.index)
        self.assertEqual(float(increments.sum()), 10.0)

    def test_equal_step_counter_does_not_fill_gap_over_35_minutes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "steps.csv"
            path.write_text(
                "1767225600000,,100\n"
                "1767228000000,,100\n"  # 40 minutes later
            )
            increments, _ = load_steps(path)
        self.assertNotIn(pd.Timestamp("2026-01-01 00:05", tz="UTC"), increments.index)


class StateTests(unittest.TestCase):
    def test_bedroom_requires_two_nights(self):
        episodes = pd.DataFrame(
            [
                {"start": pd.Timestamp("2026-01-01 22:00", tz="UTC"), "main_sleep": True, "room_supported": True, "dominant_beacon": "B", "observed_windows": 50, "dominant_count": 40},
                {"start": pd.Timestamp("2026-01-02 22:00", tz="UTC"), "main_sleep": True, "room_supported": True, "dominant_beacon": "B", "observed_windows": 50, "dominant_count": 40},
            ]
        )
        audit = infer_bedroom(episodes, set(), "UTC")
        self.assertTrue(audit["bedroom_inferred"])
        self.assertEqual(audit["bedroom_beacons"], "B")

    def test_sleep_gap_requires_two_sided_support(self):
        index = grid(12)
        timeline = pd.DataFrame(index=index)
        timeline["base_beacon"] = ["B"] * 4 + [pd.NA] * 2 + ["B"] * 6
        timeline["base_room"] = timeline["base_beacon"].map({"B": "Bedroom"})
        timeline["corrected_beacon"] = timeline["base_beacon"]
        timeline["corrected_room"] = timeline["base_room"]
        timeline["correction_reason"] = "none"
        timeline["location_evidence"] = "observed_raw"
        timeline["sleep_gap_filled"] = False
        timeline["sleep_episode_id"] = pd.Series(pd.NA, index=index, dtype="Int64")
        timeline["main_sleep"] = False
        episodes = pd.DataFrame(
            [{
                "candidate_id": 1,
                "start": index[0],
                "end": index[-1] + pd.Timedelta(minutes=5),
                "main_sleep": True,
                "room_supported": True,
                "dominant_beacon": "B",
                "dominant_room": "Bedroom",
            }]
        )
        result = apply_sleep_correction(timeline, episodes, PipelineParameters())
        self.assertTrue(result.iloc[4:6]["sleep_gap_filled"].all())
        self.assertTrue(result.iloc[4:6]["corrected_room"].eq("Bedroom").all())

    def test_one_sided_sleep_gap_remains_missing(self):
        index = grid(8)
        timeline = pd.DataFrame(index=index)
        timeline["base_beacon"] = [pd.NA] * 2 + ["B"] * 6
        timeline["base_room"] = timeline["base_beacon"].map({"B": "Bedroom"})
        timeline["corrected_beacon"] = timeline["base_beacon"]
        timeline["corrected_room"] = timeline["base_room"]
        timeline["correction_reason"] = "none"
        timeline["location_evidence"] = "missing"
        timeline["sleep_gap_filled"] = False
        timeline["sleep_episode_id"] = pd.Series(pd.NA, index=index, dtype="Int64")
        timeline["main_sleep"] = False
        episodes = pd.DataFrame([{"candidate_id": 1, "start": index[0], "end": index[-1] + pd.Timedelta(minutes=5), "main_sleep": True, "room_supported": True, "dominant_beacon": "B", "dominant_room": "Bedroom"}])
        result = apply_sleep_correction(timeline, episodes, PipelineParameters())
        self.assertTrue(result.iloc[:2]["corrected_beacon"].isna().all())

    def test_ineligible_step_sleep_room_is_not_locked(self):
        index = grid(8)
        timeline = pd.DataFrame(index=index)
        timeline["base_beacon"] = ["B", "B", "X", "X", "X", "X", "X", "X"]
        timeline["base_room"] = timeline["base_beacon"].map({"B": "Bedroom", "X": "Bathroom"})
        timeline["corrected_beacon"] = timeline["base_beacon"]
        timeline["corrected_room"] = timeline["base_room"]
        timeline["correction_reason"] = "none"
        timeline["location_evidence"] = "observed_raw"
        timeline["sleep_gap_filled"] = False
        timeline["sleep_episode_id"] = pd.Series(pd.NA, index=index, dtype="Int64")
        timeline["main_sleep"] = False
        episodes = pd.DataFrame([{
            "candidate_id": 1,
            "start": index[0],
            "end": index[-1] + pd.Timedelta(minutes=5),
            "main_sleep": True,
            "room_supported": True,
            "room_correction_eligible": False,
            "dominant_beacon": "X",
            "dominant_room": "Bathroom",
        }])
        result = apply_sleep_correction(timeline, episodes, PipelineParameters())
        pd.testing.assert_series_equal(result["corrected_room"], timeline["corrected_room"])
        self.assertTrue(result["main_sleep"].all())

    def test_away_does_not_use_sleep_missing_windows(self):
        index = grid(36)
        timeline = pd.DataFrame(index=index)
        timeline["rssi_observed"] = False
        timeline["wearable_online"] = True
        timeline["main_sleep"] = False
        timeline.loc[index[:12], "main_sleep"] = True
        # Six non-sleep runs separated by observed windows; three short, three long.
        timeline["rssi_observed"] = True
        for start, length in ((12, 1), (14, 1), (16, 1), (18, 4), (23, 4), (28, 4)):
            timeline.loc[index[start : start + length], "rssi_observed"] = False
        probable, runs, _ = classify_away_runs(timeline, PipelineParameters(away_silhouette_min=0.1))
        self.assertFalse(probable.loc[index[:12]].any())
        self.assertEqual(len(runs), 6)


class PipelineTests(unittest.TestCase):
    def test_adaptive_window_does_not_cross_rssi_gap(self):
        index = grid(120)
        rssi = pd.DataFrame({"A": -60.0, "B": -80.0}, index=index)
        rssi.loc[index[90], :] = np.nan
        rssi.loc[index[91]:, "A"] = -90.0
        rssi.loc[index[91]:, "B"] = -50.0
        movement = pd.Series(np.r_[np.full(100, 0.004), np.full(20, 0.08)], index=index)
        output = run_inference(rssi, rssi.notna().astype(int), movement, "acc", pd.Series(True, index=index), {"A": "Living", "B": "Bedroom"}, "UTC")["timeline"]
        self.assertEqual(output.loc[index[91], "corrected_beacon"], "B")

    def test_copresence_missing_rooms_are_not_equal(self):
        index = grid(2)
        left = pd.DataFrame(
            {
                "raw_room": [pd.NA, "Living"],
                "corrected_room": [pd.NA, "Living"],
                "occupancy_state": ["unknown", "indoor_observed"],
                "behaviour_state": ["awake", "awake"],
            },
            index=index,
        )
        right = left.copy()
        timeline, metrics = analyse_copresence(left, right, "L", "R")
        self.assertFalse(bool(timeline.iloc[0]["raw_copresent"]))
        self.assertTrue(bool(timeline.iloc[1]["corrected_copresent"]))
        self.assertFalse(metrics.empty)

    def test_awake_missing_is_never_filled(self):
        index = grid(120)
        rssi = pd.DataFrame({"A": -60.0, "B": -80.0}, index=index)
        rssi.loc[index[80], :] = np.nan
        counts = rssi.notna().astype(int)
        movement = pd.Series(np.r_[np.full(60, 0.004), np.full(60, 0.08)], index=index)
        output = run_inference(rssi, counts, movement, "acc", pd.Series(True, index=index), {"A": "Living", "B": "Bedroom"}, "UTC")["timeline"]
        self.assertTrue(pd.isna(output.loc[index[80], "corrected_room"]))
        self.assertEqual(output.iloc[-1]["adaptive_window_minutes"], 5)
        self.assertEqual(output.iloc[-1]["corrected_beacon"], output.iloc[-1]["raw_strongest_beacon"])

    def test_pressure_inactive_does_not_change_rssi(self):
        index = grid(20)
        rssi = pd.DataFrame({"A": -60.0, "B": -70.0}, index=index)
        constrained, info, audit = constrain_rssi_with_pressure(rssi, pd.DataFrame(index=index), pd.Series(index=index, dtype=float))
        pd.testing.assert_frame_equal(rssi, constrained)
        self.assertFalse(audit["pressure_enabled"])
        self.assertFalse(info["pressure_floor_trusted"].any())

    def test_auto_pressure_rejects_stable_same_floor_height_offsets(self):
        index = pd.date_range("2026-01-01", periods=200, freq="5min", tz="UTC")
        weather = np.sin(np.linspace(0, 4 * np.pi, len(index)))
        # Two very stable offset groups separated by 0.23 hPa.  This is
        # statistically clusterable but still plausible within one storey due
        # to mounting height and fixed sensor calibration differences.
        environmental = pd.DataFrame(
            {
                "A": 1000 + weather - 0.12,
                "B": 1000 + weather - 0.11,
                "C": 1000 + weather + 0.11,
                "D": 1000 + weather + 0.12,
            },
            index=index,
        )
        groups, audit = _auto_groups(environmental)
        self.assertEqual(groups, {})
        self.assertFalse(audit["pressure_auto_groups_valid"])
        self.assertTrue(audit["pressure_null_model_selected"])
        self.assertIn("floor_scale_separation", audit["pressure_reason"])

    def test_auto_pressure_accepts_storey_scale_offsets(self):
        index = pd.date_range("2026-01-01", periods=200, freq="5min", tz="UTC")
        weather = np.sin(np.linspace(0, 4 * np.pi, len(index)))
        environmental = pd.DataFrame(
            {
                "A": 1000 + weather - 0.20,
                "B": 1000 + weather - 0.18,
                "C": 1000 + weather + 0.18,
                "D": 1000 + weather + 0.20,
            },
            index=index,
        )
        groups, audit = _auto_groups(environmental)
        self.assertEqual(len(set(groups.values())), 2)
        self.assertTrue(audit["pressure_auto_groups_valid"])
        self.assertFalse(audit["pressure_null_model_selected"])
        self.assertGreaterEqual(audit["pressure_group_min_separation_hpa"], 0.30)

    def test_pressure_manual_groups_handle_missing_windows(self):
        index = grid(120)
        rssi = pd.DataFrame({"A": -60.0, "B": -70.0, "C": -80.0, "D": -85.0}, index=index)
        rssi.loc[index[10], :] = np.nan
        environmental = pd.DataFrame(
            {"A": 1000.4, "B": 1000.42, "C": 1000.0, "D": 1000.02},
            index=index,
        )
        environmental.loc[index[10], :] = np.nan
        wearable = pd.Series(1000.38, index=index)
        constrained, info, audit = constrain_rssi_with_pressure(
            rssi,
            environmental,
            wearable,
            movement_state=pd.Series(2, index=index),
            floor_override={"A": "1F", "B": "1F", "C": "2F", "D": "2F"},
        )
        self.assertTrue(audit["pressure_enabled"])
        self.assertTrue(info["pressure_floor_trusted"].any())
        self.assertEqual(constrained.shape, rssi.shape)


if __name__ == "__main__":
    unittest.main()
