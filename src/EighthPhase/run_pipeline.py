#!/usr/bin/env python3
"""Run the unified eighth-phase pipeline for one collection or all collections."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from EighthPhase.core import PipelineParameters, classify_movement, run_inference
    from EighthPhase.evaluation import analyse_copresence, evaluate_reference
    from EighthPhase.io import ROOT, STEP_PLATEAU_MAX_GAP, load_manifest, load_session_inputs
    from EighthPhase.plotting import plot_clustering, plot_confusion, plot_timeline
    from EighthPhase.pressure import (
        PRESSURE_MIN_FLOOR_SEPARATION_HPA,
        PRESSURE_MIN_GROUP_SILHOUETTE,
        constrain_rssi_with_pressure,
    )
else:
    from .core import PipelineParameters, classify_movement, run_inference
    from .evaluation import analyse_copresence, evaluate_reference
    from .io import ROOT, STEP_PLATEAU_MAX_GAP, load_manifest, load_session_inputs
    from .plotting import plot_clustering, plot_confusion, plot_timeline
    from .pressure import (
        PRESSURE_MIN_FLOOR_SEPARATION_HPA,
        PRESSURE_MIN_GROUP_SILHOUETTE,
        constrain_rssi_with_pressure,
    )


DEFAULT_MANIFEST = Path(__file__).resolve().parent / "config" / "datasets.json"
RESULTS_ROOT = ROOT / "Results" / "EighthPhase"


def _write_frame(frame: pd.DataFrame, path: Path, index: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=index)


def _merge_partial(existing_path: Path, current: pd.DataFrame, selected_collections: set[str]) -> pd.DataFrame:
    if not existing_path.exists() or "collection" not in current.columns:
        return current
    existing = pd.read_csv(existing_path)
    if "collection" not in existing.columns:
        return current
    retained = existing.loc[~existing["collection"].isin(selected_collections)]
    return pd.concat([retained, current], ignore_index=True, sort=False)


def _capability_row(collection: str, participant: str, session: dict) -> dict[str, object]:
    def available(key: str) -> bool:
        if not session.get(key):
            return False
        path = ROOT / session[key]
        return path.exists() and path.stat().st_size > 0

    rssi_spec = session.get("rssi", {})
    rssi_path = ROOT / rssi_spec.get("path", "")
    return {
        "collection": collection,
        "participant": participant,
        "session": session["id"],
        "rssi_available": rssi_path.exists(),
        "rssi_adapter": rssi_spec.get("type", ""),
        "acc_available": available("acc_path"),
        "step_available": available("step_path"),
        "wearable_pressure_available": available("wearable_pressure_path"),
        "environmental_pressure_available": bool(rssi_spec.get("environmental_pressure_path")) or rssi_spec.get("type") == "combined_tags",
        "reference_available": bool(session.get("reference")),
        "timezone": session.get("timezone", "UTC"),
    }


def _prepare_csv_timeline(timeline: pd.DataFrame, collection: str, participant: str, session: str, timezone: str) -> pd.DataFrame:
    output = timeline.copy()
    output.index.name = "time_utc"
    output.insert(0, "time_local", output.index.tz_convert(timezone).astype(str))
    output.insert(0, "session", session)
    output.insert(0, "participant", participant)
    output.insert(0, "collection", collection)
    return output.reset_index()


def run_session(collection: dict, participant: dict, session: dict, params: PipelineParameters, make_plots: bool) -> tuple[pd.DataFrame, dict[str, object]]:
    collection_id = collection["id"]
    participant_id = participant["id"]
    session_id = session["id"]
    output_dir = RESULTS_ROOT / collection_id / participant_id / session_id
    output_dir.mkdir(parents=True, exist_ok=True)
    inputs = load_session_inputs(session)

    movement_preview = None
    if inputs["movement_source"] is not None:
        movement_preview = classify_movement(inputs["movement"], inputs["movement_source"], params)[0]["movement_state"]
    constrained_rssi, pressure_info, pressure_audit = constrain_rssi_with_pressure(
        inputs["rssi_mean"],
        inputs["environmental_pressure"],
        inputs["wearable_pressure"],
        movement_state=movement_preview,
        floor_override=session.get("floor_override"),
    )
    result = run_inference(
        inputs["rssi_mean"],
        inputs["rssi_count"],
        inputs["movement"],
        inputs["movement_source"],
        inputs["wearable_online"],
        inputs["beacon_to_room"],
        session.get("timezone", "UTC"),
        params,
        base_rssi_mean=constrained_rssi,
        context_features=pressure_info,
    )
    timeline = result["timeline"]
    timeline["rssi_coverage"] = inputs["rssi_coverage"].reindex(timeline.index).fillna(0)
    audit = {
        "collection": collection_id,
        "participant": participant_id,
        "session": session_id,
        "step_reconstructed_zero_windows": inputs["step_reconstructed_zero_windows"],
        **result["audit"],
        **pressure_audit,
    }
    csv_timeline = _prepare_csv_timeline(timeline, collection_id, participant_id, session_id, session.get("timezone", "UTC"))
    _write_frame(csv_timeline, output_dir / "timeline_5min.csv")
    _write_frame(result["episodes"], output_dir / "sleep_episode_summary.csv")
    _write_frame(result["away_runs"], output_dir / "away_gap_summary.csv")
    _write_frame(result["movement_diagnostics"], output_dir / "movement_clustering_audit.csv")
    _write_frame(result["sleep_diagnostics"], output_dir / "sleep_duration_clustering_audit.csv")
    _write_frame(pd.DataFrame([audit]), output_dir / "session_audit.csv")
    _write_frame(pd.DataFrame(sorted(inputs["beacon_to_room"].items()), columns=["beacon", "room"]), output_dir / "beacon_room_mapping.csv")

    if session.get("reference"):
        metrics, aligned, confusion = evaluate_reference(timeline, session["reference"])
        _write_frame(metrics, output_dir / "reference_agreement_metrics.csv")
        _write_frame(aligned.reset_index(names="time_utc"), output_dir / "reference_aligned_predictions.csv")
        _write_frame(confusion, output_dir / "reference_confusion_matrix.csv")
        for row in metrics.itertuples(index=False):
            prefix = "raw" if str(row.method).startswith("raw") else "corrected"
            for field in ("coverage", "conditional_accuracy", "balanced_accuracy", "macro_f1", "end_to_end_accuracy"):
                audit[f"reference_{prefix}_{field}"] = getattr(row, field)
        if make_plots:
            plot_confusion(confusion, output_dir / "reference_confusion_matrix.png")
    if make_plots:
        title = f"{collection_id} / {participant_id} / {session_id}: raw and movement-supported RSSI"
        plot_timeline(timeline, session.get("timezone", "UTC"), title, output_dir / "raw_vs_corrected_timeline.png")
        plot_clustering(timeline, result["episodes"], session.get("timezone", "UTC"), f"{collection_id} movement and low-motion episode clustering", output_dir / "movement_sleep_clustering.png")
    return timeline, audit


def run_collection(collection: dict, participant_filter: str | None, session_filter: str | None, params: PipelineParameters, make_plots: bool) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    audits, capabilities = [], []
    participant_timelines: dict[str, list[pd.DataFrame]] = {}
    for participant in collection.get("participants", []):
        if participant_filter and participant["id"] != participant_filter:
            continue
        for session in participant.get("sessions", []):
            if session_filter and session["id"] != session_filter:
                continue
            capabilities.append(_capability_row(collection["id"], participant["id"], session))
            print(f"[{collection['id']}] {participant['id']} / {session['id']}", flush=True)
            timeline, audit = run_session(collection, participant, session, params, make_plots)
            audits.append(audit)
            participant_timelines.setdefault(participant["id"], []).append(timeline)

    combined = {participant: pd.concat(frames).sort_index() for participant, frames in participant_timelines.items() if frames}
    collection_dir = RESULTS_ROOT / collection["id"]
    for left, right in collection.get("copresence_pairs", []):
        if left not in combined or right not in combined:
            continue
        timeline, metrics = analyse_copresence(combined[left], combined[right], left, right)
        _write_frame(timeline.reset_index(names="time_utc"), collection_dir / f"copresence_{left}_{right}_timeline.csv")
        _write_frame(metrics, collection_dir / f"copresence_{left}_{right}_metrics.csv")
    if audits:
        _write_frame(pd.DataFrame(audits), collection_dir / "collection_summary.csv")
    return audits, capabilities


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default="all", help="Collection id or 'all'")
    parser.add_argument("--participant", help="Optional participant id")
    parser.add_argument("--session", help="Optional session id")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--no-plots", action="store_true", help="Skip PNG generation")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = load_manifest(args.manifest)
    RESULTS_ROOT.mkdir(parents=True, exist_ok=True)
    selected = [item for item in manifest["collections"] if args.dataset == "all" or item["id"] == args.dataset]
    if not selected:
        raise SystemExit(f"Unknown collection: {args.dataset}")
    params = PipelineParameters()
    audits, capabilities, failures = [], [], []
    for collection in selected:
        try:
            collection_audits, collection_capabilities = run_collection(collection, args.participant, args.session, params, not args.no_plots)
            audits.extend(collection_audits)
            capabilities.extend(collection_capabilities)
        except Exception as error:  # Continue all-mode while preserving an audit trail.
            failures.append({"collection": collection["id"], "error_type": type(error).__name__, "error": str(error)})
            print(f"ERROR [{collection['id']}]: {type(error).__name__}: {error}", file=sys.stderr, flush=True)
            if args.dataset != "all":
                raise
    capability_frame = pd.DataFrame(capabilities)
    summary_frame = pd.DataFrame(audits)
    failure_frame = pd.DataFrame(failures, columns=["collection", "error_type", "error"])
    if args.dataset != "all":
        selected_ids = {item["id"] for item in selected}
        capability_frame = _merge_partial(RESULTS_ROOT / "dataset_capability_audit.csv", capability_frame, selected_ids)
        summary_frame = _merge_partial(RESULTS_ROOT / "cross_dataset_summary.csv", summary_frame, selected_ids)
        failure_frame = _merge_partial(RESULTS_ROOT / "pipeline_failures.csv", failure_frame, selected_ids)
    _write_frame(capability_frame, RESULTS_ROOT / "dataset_capability_audit.csv")
    _write_frame(pd.DataFrame(manifest.get("excluded", [])), RESULTS_ROOT / "excluded_dataset_audit.csv")
    _write_frame(summary_frame, RESULTS_ROOT / "cross_dataset_summary.csv")
    _write_frame(failure_frame, RESULTS_ROOT / "pipeline_failures.csv")
    with (RESULTS_ROOT / "pipeline_parameters.json").open("w") as handle:
        exported_parameters = {
            **params.__dict__,
            "step_plateau_max_gap_minutes": STEP_PLATEAU_MAX_GAP.total_seconds() / 60,
            "pressure_min_floor_separation_hpa": PRESSURE_MIN_FLOOR_SEPARATION_HPA,
            "pressure_min_group_silhouette": PRESSURE_MIN_GROUP_SILHOUETTE,
        }
        json.dump(exported_parameters, handle, indent=2)
    print(f"Completed {len(audits)} sessions; failures: {len(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
