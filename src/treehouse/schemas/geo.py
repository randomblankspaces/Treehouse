"""GeoJSON geometry records (EPSG:4326, lon/lat order)."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import AfterValidator, model_validator

from treehouse.schemas.base import Frozen

Position = tuple[float, float]


def _bbox_ok(b: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    if b[0] > b[2] or b[1] > b[3]:
        raise ValueError("bbox must be [min_lon, min_lat, max_lon, max_lat]")
    return b


BBox = Annotated[tuple[float, float, float, float], AfterValidator(_bbox_ok)]


class Point(Frozen):
    type: Literal["Point"] = "Point"
    coordinates: Position


class Polygon(Frozen):
    """A Polygon (list of rings) or MultiPolygon (list of polygons). Rings must be closed."""

    type: Literal["Polygon", "MultiPolygon"]
    coordinates: list[list[Position]] | list[list[list[Position]]]

    def polygons(self) -> list[list[list[Position]]]:
        if self.type == "Polygon":
            return [self.coordinates]  # type: ignore[list-item]
        return self.coordinates  # type: ignore[return-value]

    @model_validator(mode="after")
    def _shape(self) -> Polygon:
        c = self.coordinates
        depth = 0
        while isinstance(c, list):
            depth += 1
            c = c[0] if c else None
        if depth != (2 if self.type == "Polygon" else 3):
            raise ValueError(f"coordinates nesting does not match type {self.type}")
        for poly in self.polygons():
            if not poly:
                raise ValueError("polygon has no rings")
            for ring in poly:
                if len(ring) < 4 or ring[0] != ring[-1]:
                    raise ValueError("each ring needs >= 4 positions and must be closed")
        return self
