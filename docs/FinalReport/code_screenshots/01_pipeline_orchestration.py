# Verbatim excerpt: src/EighthPhase/run_pipeline.py, lines 90-129

import pandas as pd

from EighthPhase.core import PipelineParameters, classify_movement, run_inference
from EighthPhase.io import load_session_inputs
from EighthPhase.pressure import constrain_rssi_with_pressure
from EighthPhase.run_pipeline import RESULTS_ROOT


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
