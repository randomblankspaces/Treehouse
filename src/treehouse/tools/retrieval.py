"""Retrieval tool server (task 3, design.md ``tools/retrieval.py``): the ``retrieval`` MCP server.

Tools: ``list_embedding_sources``, ``build_index``, ``get_examples``, ``retrieve``, ``classify``, ``aggregate``.
Inputs and outputs are JSON; every result carries the index provenance (source, date range, resolution, cell
size, licence, cost; ``CellIndex.describe()``). Classifiers are plain numpy (logistic regression with L2 and a
linear SVM by hinge-loss subgradient descent), trained on example cells versus random negative cells drawn with
a fixed seed, so a run is deterministic.

Few-shot examples come from the training split only (RV4). The server reads the split itself through an
injectable ``ExampleProvider``; the agent never passes a ``keys/`` path, and no key path appears in a result.
Gifu (transfer target) and Bangladesh get ``NoExamples``.

Seams (not built here): ``retrieve(method="zero_shot_text")`` needs Bedrock vision on chips and
``classify(method="vision_subagent")`` is task 5; both return ``ToolError("not_configured")``.
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any, Literal, Protocol

import numpy as np
from mcp.server import MCPServer

from treehouse.paths import keys_root
from treehouse.schemas.task import TaskCard
from treehouse.schemas.tools import ToolError
from treehouse.tools.sources.aef import AefSource
from treehouse.tools.sources.clay_lgnd import NATIVE_CELLS_M, ClayLgndSource
from treehouse.tools.sources.embedding_source import BBox, CellIndex, EmbeddingSource, load_fixture_points

TOOL_NAMES = ("list_embedding_sources", "build_index", "get_examples", "retrieve", "classify", "aggregate")
SEED = 20261104
HIGH_CONFIDENCE = 0.8
FORBIDDEN_VENDORS = ("maxar", "vantor")  # RV2: commercial VHR imagery is never a permitted source
SOURCE_INFO: dict[str, dict[str, Any]] = {
    "aef-10m-annual": {"model": "AlphaEarth Foundations annual embedding (64-d per 10 m pixel)",
                       "cell_sizes_m": "160 x k (fixture base grid 160 m)", "factory": AefSource.for_aoi},
    "lgnd-clay-embeddings": {"model": "Clay v1.5 on Sentinel-2 (LGND precomputed)",
                             "cell_sizes_m": list(NATIVE_CELLS_M), "factory": ClayLgndSource.for_aoi},
}
AOI_FIXTURES = {"nagoya": "nagoya", "gifu": "gifu", "bangladesh": "chattogram", "chattogram": "chattogram"}
_CELL = re.compile(r"^r(\d+)c(\d+)$")


# ---------------------------------------------------------------- examples (server-side, train split only)
class ExampleProvider(Protocol):
    def train_examples(self) -> list[dict]: ...  # [{"example_id", "lon", "lat"}], sorted by id
    def provenance(self) -> dict: ...


class NoExamples:
    """No labelled examples for this AOI (Gifu is a transfer target with no new labels)."""

    def __init__(self, reason: str = "no labelled training examples for this area") -> None:
        self.reason = reason

    def train_examples(self) -> list[dict]:
        return []

    def provenance(self) -> dict:
        return {"source": "none", "licence": "n/a", "split": "train", "note": self.reason, "cost_usd": 0.0}


class SplitExamples:
    """Training-split points from the PLATEAU warehouse reference (read here, never exposed as a path)."""

    def __init__(self, city: str) -> None:
        self.city = city
        self._cache: list[dict] | None = None

    def train_examples(self) -> list[dict]:
        if self._cache is None:
            base = keys_root() / "plateau"
            train = set(json.loads((base / f"{self.city}-split.json").read_text())["train"])
            fc = json.loads((base / f"{self.city}-warehouses.geojson").read_text())
            self._cache = sorted(({"example_id": f["id"], "lon": float(f["geometry"]["coordinates"][0]),
                                   "lat": float(f["geometry"]["coordinates"][1])}
                                  for f in fc["features"] if f["id"] in train), key=lambda e: e["example_id"])
        return list(self._cache)

    def provenance(self) -> dict:
        return {"source": f"PLATEAU 3D city model ({self.city}), training split", "licence": "CC-BY-4.0",
                "split": "train", "cost_usd": 0.0}


# ---------------------------------------------------------------- numpy classifiers
def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -50, 50)))


def fit_logistic(x: np.ndarray, y: np.ndarray, *, l2: float = 1e-2, steps: int = 400, lr: float = 1.0
                 ) -> tuple[np.ndarray, float]:
    """Class-balanced logistic regression, L2 on weights, full-batch gradient descent (deterministic)."""
    w, b = np.zeros(x.shape[1]), 0.0
    sw = np.where(y == 1, 0.5 / max(1, (y == 1).sum()), 0.5 / max(1, (y == 0).sum()))
    for _ in range(steps):
        g = (_sigmoid(x @ w + b) - y) * sw
        w -= lr * (x.T @ g + l2 * w)
        b -= lr * g.sum()
    return w, b


def fit_linear_svm(x: np.ndarray, y01: np.ndarray, *, lam: float = 1e-2, steps: int = 400
                   ) -> tuple[np.ndarray, float]:
    """Class-balanced linear SVM: hinge loss + L2, full-batch subgradient descent, lr = 1/sqrt(t)."""
    y = np.where(y01 == 1, 1.0, -1.0)
    sw = np.where(y01 == 1, 0.5 / max(1, (y01 == 1).sum()), 0.5 / max(1, (y01 == 0).sum()))
    w, b = np.zeros(x.shape[1]), 0.0
    for t in range(1, steps + 1):
        act = (y * (x @ w + b) < 1).astype(float) * sw
        lr = 1.0 / np.sqrt(t)
        w -= lr * (lam * w - x.T @ (act * y))
        b += lr * (act * y).sum()
    return w, b


# ---------------------------------------------------------------- the tools
class RetrievalTools:
    def __init__(self, *, allowed_source_ids: list[str], aoi: str | None, aoi_bbox: BBox,
                 date_range: tuple[str, str], examples: ExampleProvider,
                 factories: dict[str, Callable[[str], EmbeddingSource]] | None = None) -> None:
        self.allowed = list(allowed_source_ids)
        self.aoi, self.aoi_bbox, self.date_range = aoi, tuple(aoi_bbox), date_range
        self.examples = examples
        self.factories = factories if factories is not None else {k: v["factory"] for k, v in SOURCE_INFO.items()}
        self.indexes: dict[str, CellIndex] = {}
        self._keys: dict[tuple, str] = {}

    # -- helpers
    def _bbox(self, aoi_bbox) -> BBox:
        return tuple(float(v) for v in aoi_bbox) if aoi_bbox is not None else self.aoi_bbox

    def _index(self, index_id: str) -> CellIndex | ToolError:
        idx = self.indexes.get(index_id)
        return idx if idx is not None else ToolError(code="unknown_index", message=f"no index {index_id}; "
                                                     "call build_index first")

    def _example_cells(self, idx: CellIndex, example_ids: list[str] | None,
                       query_lonlat: tuple[float, float] | None = None) -> list[int] | ToolError:
        pool = {e["example_id"]: e for e in self.examples.train_examples()}
        ids = list(pool) if example_ids is None else list(example_ids)
        bad = [i for i in ids if i not in pool]
        if bad:
            return ToolError(code="bad_args", message=f"not training-split example ids: {bad[:5]}")
        pts = [(pool[i]["lon"], pool[i]["lat"]) for i in ids] + ([tuple(query_lonlat)] if query_lonlat else [])
        if not pts:
            return ToolError(code="no_examples", message="no example ids or query_lonlat (and no training "
                             "examples are available for this area)")
        return sorted({int(np.argmin((idx.lon - x) ** 2 + (idx.lat - y) ** 2)) for x, y in pts})

    def _train(self, idx: CellIndex, pos: list[int], method: str) -> tuple[np.ndarray, float, dict]:
        rng = np.random.default_rng(SEED)
        rest = np.setdiff1d(np.arange(len(idx.cell_ids)), pos)
        neg = np.sort(rng.choice(rest, size=min(len(rest), max(200, 10 * len(pos))), replace=False))
        x = idx.emb[np.concatenate([pos, neg])].astype(np.float64)
        y = np.concatenate([np.ones(len(pos)), np.zeros(len(neg))])
        w, b = (fit_logistic if method != "linear_svm" else fit_linear_svm)(x, y)
        return w, b, {"positives": len(pos), "negatives": int(len(neg)), "negatives_from": "random cells",
                      "seed": SEED, "steps": 400}

    def _cells(self, idx: CellIndex, order, scores) -> list[dict]:
        return [{"cell_id": str(idx.cell_ids[j]), "lon": float(idx.lon[j]), "lat": float(idx.lat[j]),
                 "score": round(float(scores[j]), 6)} for j in order]

    # -- tools
    def list_embedding_sources(self, aoi_bbox: BBox | None = None) -> dict:
        out = []
        for sid in self.allowed:
            info = SOURCE_INFO.get(sid)
            if info is None or sid not in self.factories or self.aoi is None:
                continue
            src = self.factories[sid](self.aoi)
            dates = list(self.date_range)
            if sid == "lgnd-clay-embeddings":
                dates = list(load_fixture_points(src.fixture)[3]["date_range"])
            out.append({"source_id": sid, "model": info["model"], "resolution_m": src.resolution_m,
                        "native_cell_m": src.native_cell_m, "cell_sizes_m": info["cell_sizes_m"],
                        "date_range": dates, "licence": src.licence, "estimated_cost_usd": 0.0,
                        "access": "fixture"})
        return {"aoi_bbox": list(self._bbox(aoi_bbox)), "sources": out}

    def build_index(self, source_id: str, cell_size_m: float, year: int, aoi_bbox: BBox | None = None
                    ) -> dict | ToolError:
        if any(v in source_id.casefold() for v in FORBIDDEN_VENDORS):
            return ToolError(code="forbidden_source", message="commercial VHR vendor imagery is forbidden (RV2)")
        if source_id not in self.allowed:
            return ToolError(code="not_allowlisted", message=f"{source_id} is not an embeddings source on this "
                             "task's allow-list; see list_embedding_sources")
        if source_id not in self.factories or self.aoi is None:
            return ToolError(code="no_coverage", message=f"no {source_id} embeddings available for this area")
        bbox = self._bbox(aoi_bbox)
        key = (source_id, float(cell_size_m), int(year), bbox)
        if key not in self._keys:
            try:
                idx = self.factories[source_id](self.aoi).index(bbox, float(cell_size_m), int(year))
            except (ValueError, FileNotFoundError) as e:
                return ToolError(code="bad_args", message=str(e))
            iid = f"idx-{len(self.indexes) + 1:03d}"
            self.indexes[iid], self._keys[key] = idx, iid
        iid = self._keys[key]
        idx = self.indexes[iid]
        return {"index_id": iid, "cells": len(idx.cell_ids), "grid": {"nx": idx.nx, "ny": idx.ny},
                "provenance": idx.describe()}

    def get_examples(self, n: int = 10, split: str = "train") -> dict | ToolError:
        if split != "train":
            return ToolError(code="heldout_forbidden", message="few-shot examples come from the training split "
                             "only; the held-out split is grading-only (RV4)")
        ex = self.examples.train_examples()
        return {"split": "train", "available": len(ex), "examples": ex[: max(0, int(n))],
                "provenance": self.examples.provenance()}

    def retrieve(self, index_id: str, method: str, k: int = 50, example_ids: list[str] | None = None,
                 query_lonlat: tuple[float, float] | None = None) -> dict | ToolError:
        if method == "zero_shot_text":
            return ToolError(code="not_configured", message="zero_shot_text needs Bedrock vision on image chips, "
                             "which is not configured here; use few_shot or concept_vector")
        if method not in ("few_shot", "concept_vector"):
            return ToolError(code="bad_args", message=f"unknown method {method}")
        idx = self._index(index_id)
        if isinstance(idx, ToolError):
            return idx
        pos = self._example_cells(idx, example_ids, query_lonlat)
        if isinstance(pos, ToolError):
            return pos
        if method == "few_shot":
            q = idx.emb[pos].astype(np.float64).mean(0)
            scores = idx.emb.astype(np.float64) @ (q / max(np.linalg.norm(q), 1e-12))
            extra: dict = {"query": "mean of example-cell embeddings", "score": "cosine similarity"}
        else:
            w, _, extra = self._train(idx, pos, "linear_probe")
            scores = idx.emb.astype(np.float64) @ (w / max(np.linalg.norm(w), 1e-12))
            extra = {**extra, "score": "projection on the linear-probe direction"}
        r = np.round(scores, 6)
        order = sorted(range(len(r)), key=lambda j: (-r[j], idx.cell_ids[j]))[: max(1, min(int(k), 1000))]
        return {"index_id": index_id, "method": method, "cells": self._cells(idx, order, scores),
                "example_cells": len(pos), "details": extra, "provenance": idx.describe()}

    def classify(self, index_id: str, method: str, cell_ids: list[str] | None = None,
                 example_ids: list[str] | None = None) -> dict | ToolError:
        if method == "vision_subagent":
            return ToolError(code="not_configured", message="vision_subagent is not configured (task 5); use "
                             "linear_probe or linear_svm")
        if method not in ("linear_probe", "linear_svm"):
            return ToolError(code="bad_args", message=f"unknown method {method}")
        idx = self._index(index_id)
        if isinstance(idx, ToolError):
            return idx
        pos = self._example_cells(idx, example_ids)
        if isinstance(pos, ToolError):
            return pos
        where = {c: j for j, c in enumerate(idx.cell_ids.tolist())}
        if cell_ids is None:
            rows = list(range(len(idx.cell_ids)))
        else:
            missing = [c for c in cell_ids if c not in where]
            if missing:
                return ToolError(code="bad_args", message=f"unknown cell ids: {missing[:5]}")
            rows = [where[c] for c in cell_ids]
        w, b, info = self._train(idx, pos, method)
        scores = _sigmoid(idx.emb.astype(np.float64) @ w + b)
        info["score"] = "probe probability" if method == "linear_probe" else "sigmoid of the SVM margin"
        return {"index_id": index_id, "method": method, "scores": self._cells(idx, rows, scores),
                "training": info, "provenance": idx.describe()}

    def aggregate(self, index_id: str, scored_cells: list[dict], threshold: float,
                  merge_rule: Literal["8-neighbour", "4-neighbour"] = "8-neighbour") -> dict | ToolError:
        idx = self._index(index_id)
        if isinstance(idx, ToolError):
            return idx
        where = {c: j for j, c in enumerate(idx.cell_ids.tolist())}
        score: dict[str, float] = {}
        for sc in scored_cells:
            cid = str(sc.get("cell_id", ""))
            if cid not in where or _CELL.match(cid) is None:
                return ToolError(code="bad_args", message=f"unknown cell id {cid!r} for {index_id}")
            score[cid] = max(score.get(cid, 0.0), float(sc.get("score", 0.0)))
        kept = {tuple(int(v) for v in _CELL.match(c).groups()): c for c, s in score.items() if s >= threshold}
        steps = [(dy, dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if (dy, dx) != (0, 0)
                 and (merge_rule == "8-neighbour" or dy == 0 or dx == 0)]
        seen: set = set()
        comps = []
        for start in sorted(kept):
            if start in seen:
                continue
            stack, comp = [start], []
            seen.add(start)
            while stack:
                y, x = stack.pop()
                comp.append(kept[(y, x)])
                for dy, dx in steps:
                    nb = (y + dy, x + dx)
                    if nb in kept and nb not in seen:
                        seen.add(nb)
                        stack.append(nb)
            comps.append(sorted(comp))
        comps.sort(key=lambda m: (-max(score[c] for c in m), m[0]))
        sites = []
        for i, m in enumerate(comps, 1):
            j = [where[c] for c in m]
            sites.append({"site_id": f"s-{i:03d}", "lon": round(float(idx.lon[j].mean()), 8),
                          "lat": round(float(idx.lat[j].mean()), 8), "member_cell_ids": m,
                          "max_score": round(max(score[c] for c in m), 6)})
        unreviewed = sorted(set(where) - set(score))
        return {"index_id": index_id, "threshold": threshold, "merge_rule": merge_rule, "sites": sites,
                "count": {"low": sum(s["max_score"] >= HIGH_CONFIDENCE for s in sites), "high": len(sites),
                          "high_confidence_threshold": HIGH_CONFIDENCE},
                "unreviewed_cell_count": len(unreviewed), "unreviewed_cells": unreviewed[:200],
                "unreviewed_cells_truncated": len(unreviewed) > 200, "provenance": idx.describe()}


def _card_bbox(card: TaskCard) -> BBox:
    def flat(c):
        return [c] if isinstance(c[0], (int, float)) else [p for x in c for p in flat(x)]
    pts = flat(card.aoi.coordinates)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def retrieval_for_card(card: TaskCard, *, examples: ExampleProvider | None = None) -> RetrievalTools:
    aoi = next((v for k, v in AOI_FIXTURES.items() if k in card.id), None)
    if examples is None:
        examples = SplitExamples("nagoya") if aoi == "nagoya" else NoExamples()
    allowed = [d.source_id for d in card.data_allowlist if d.kind == "embeddings"]
    return RetrievalTools(allowed_source_ids=allowed, aoi=aoi, aoi_bbox=_card_bbox(card),
                          date_range=tuple(str(d) for d in card.time_window), examples=examples)


def make_retrieval_server(tools: RetrievalTools) -> MCPServer:
    srv = MCPServer("retrieval")

    @srv.tool(description=(
        "List the embedding sources this task permits, with model, input resolution, native cell size, dates,\n"
        "licence and estimated cost. Choose a source and a cell size that can resolve the target objects."))
    def list_embedding_sources(aoi_bbox: tuple[float, float, float, float] | None = None) -> dict:
        return tools.list_embedding_sources(aoi_bbox)

    @srv.tool(description=(
        "Build (or reuse) a grid of embedding cells for a source, cell size (m) and year over aoi_bbox (default:\n"
        "the task AOI). Returns an index_id, the cell count and provenance. Only allow-listed sources."))
    def build_index(source_id: str, cell_size_m: float, year: int,
                    aoi_bbox: tuple[float, float, float, float] | None = None) -> dict | ToolError:
        return tools.build_index(source_id, cell_size_m, year, aoi_bbox)

    @srv.tool(description=(
        "Up to n permitted few-shot positive examples (id, lon, lat) from the training split. Other splits are\n"
        "refused. May return none when the area has no labelled examples."))
    def get_examples(n: int = 10, split: str = "train") -> dict | ToolError:
        return tools.get_examples(n, split)

    @srv.tool(description=(
        "Rank the cells of an index. method few_shot: cosine similarity to the mean of the example cells;\n"
        "concept_vector: projection on a linear-probe direction (examples vs random cells); zero_shot_text: text\n"
        "query via vision (may be not configured). Give example_ids and/or query_lonlat. Returns top k cells."))
    def retrieve(index_id: str, method: Literal["few_shot", "concept_vector", "zero_shot_text"], k: int = 50,
                 example_ids: list[str] | None = None,
                 query_lonlat: tuple[float, float] | None = None) -> dict | ToolError:
        return tools.retrieve(index_id, method, k, example_ids, query_lonlat)

    @srv.tool(description=(
        "Score cells in [0, 1] with a classifier trained on example cells vs random cells (fixed seed).\n"
        "method linear_probe (logistic regression), linear_svm (sigmoid of the margin) or vision_subagent (may be\n"
        "not configured). cell_ids defaults to every cell; example_ids defaults to all training examples."))
    def classify(index_id: str, method: Literal["linear_probe", "linear_svm", "vision_subagent"],
                 cell_ids: list[str] | None = None, example_ids: list[str] | None = None) -> dict | ToolError:
        return tools.classify(index_id, method, cell_ids, example_ids)

    @srv.tool(description=(
        "Keep scored cells with score >= threshold and merge touching kept cells (8- or 4-neighbour) into sites.\n"
        "Returns sites (centroid, member cells, max score), a count range (low: sites with max score >= 0.8,\n"
        "high: all sites) and the cells never scored (unreviewed). scored_cells: [{cell_id, score}]."))
    def aggregate(index_id: str, scored_cells: list[dict[str, Any]], threshold: float,
                  merge_rule: Literal["8-neighbour", "4-neighbour"] = "8-neighbour") -> dict | ToolError:
        return tools.aggregate(index_id, scored_cells, threshold, merge_rule)

    return srv
