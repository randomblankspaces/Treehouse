"""Explicit browser summaries of tool inputs and metadata; raw sealed payloads stay local."""
from __future__ import annotations

import math

PARAMETERS = {
    "build_index": {"source_id", "cell_size_m", "year", "aoi_bbox"},
    "list_embedding_sources": {"aoi_bbox", "bbox", "year"},
    "get_examples": {"split", "n", "cls"},
    "retrieve": {"index_id", "method", "example_ids", "k", "query_lonlat", "query_text"},
    "classify": {"index_id", "method", "example_ids", "cell_ids", "k"},
    "aggregate": {"index_id", "scores", "threshold"},
    "imagery_window": {"source_id", "bbox", "aoi_bbox", "side_m", "lon", "lat", "gsd_m", "out_px", "scene_id"},
    "stac_search": {"source_id", "bbox", "time_window", "limit"},
    "classify_window": {"result_id", "cls"},
    "record_claim": {"step_id", "lon", "lat", "cls", "status", "confidence", "reason", "evidence_refs"},
    "note_limitation": {"text"},
    "submit_understanding": {"goal_restated", "scope", "planned_data", "known_limits"},
    "clay_search": {"bbox", "aoi_bbox", "k", "query", "top_k"},
}
NUMERIC_LISTS = {"aoi_bbox", "bbox", "bbox_read", "query_lonlat"}
STRING_LISTS = {"example_ids", "cell_ids", "date_range", "time_window", "planned_data", "known_limits"}
PROVENANCE = {"source", "source_id", "access", "fixture", "real_access_path", "fixture_base_cell_m", "grid_id",
              "date_range", "resolution_m", "cell_size_m", "crs", "licence", "cost_usd", "cells", "dims", "synthetic"}
METADATA = {"index_id", "source_id", "cells", "dims", "date_range", "resolution_m", "cell_size_m", "bbox_read",
            "effective_gsd_m", "nominal_gsd_m", "pixel_spacing_m", "scene_id", "scene_datetime", "reader",
            "bytes_read", "license", "synthetic", "claim_id", "method", "pricing", "count", "code", "message"}


def _scalar(value):
    return value is None or isinstance(value, str | bool) or (
        isinstance(value, int | float) and math.isfinite(value))


def _fields(value, allowed):
    if not isinstance(value, dict):
        return {}
    result = {}
    for key, item in value.items():
        if key not in allowed:
            continue
        if _scalar(item):
            result[key] = item
        elif isinstance(item, list) and key in NUMERIC_LISTS and all(
                isinstance(x, int | float) and not isinstance(x, bool) and math.isfinite(x) for x in item):
            result[key] = item
        elif isinstance(item, list) and key in STRING_LISTS and all(isinstance(x, str) for x in item):
            result[key] = item
    return result


def parameters(tool, value):
    result = _fields(value, PARAMETERS.get(tool, set()))
    if tool == "record_claim" and isinstance(value, dict) and isinstance(value.get("evidence_refs"), list):
        result["evidence_refs"] = [_fields(ref, {"result_id", "role"}) for ref in value["evidence_refs"]]
    return result


def metadata(value):
    result = _fields(value, METADATA)
    if isinstance(value, dict) and isinstance(value.get("provenance"), dict):
        result["provenance"] = _fields(value["provenance"], PROVENANCE)
    if isinstance(value, dict) and isinstance(value.get("grid"), dict):
        result["grid"] = {k: v for k, v in value["grid"].items() if k in {"lon0", "lat0", "cell_deg", "nx", "ny"}
                          and isinstance(v, int | float) and not isinstance(v, bool) and math.isfinite(v)}
    return result
