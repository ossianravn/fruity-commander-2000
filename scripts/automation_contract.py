"""Musical automation request and native representation, independent of FL access."""

import struct
from pydantic import BaseModel, ConfigDict, Field, model_validator

from scripts.range_runtime import ticks


class AutomationPoint(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    time_qn: float = Field(ge=0)
    value: float = Field(ge=0, le=1)


class AutomationCreation(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    channel_index: int = Field(ge=0)
    parameter_index: int = Field(ge=0)
    target_fingerprint: str = Field(min_length=1)
    track: int = Field(ge=1, le=500)
    start_qn: float = Field(ge=0)
    length_qn: float = Field(gt=0)
    points: list[AutomationPoint] = Field(min_length=2)

    @model_validator(mode="after")
    def validate_curve(self):
        if self.points[0].time_qn != 0 or self.points[-1].time_qn != self.length_qn:
            raise ValueError("Provide curve endpoints at zero and the requested clip length")
        if any(a.time_qn >= b.time_qn for a, b in zip(self.points, self.points[1:])):
            raise ValueError("Automation point times must be strictly increasing")
        return self

    def encoded(self, ppq):
        start, end = ticks(self.start_qn, ppq), ticks(self.start_qn + self.length_qn, ppq)
        if not 0 <= start < end <= 0x7fffffff:
            raise ValueError("Requested placement is outside FL's signed 32-bit tick range")
        payload, observed = encode_points(self.points)
        return start, end - start, payload, observed


def encode_points(points):
    previous, actual_time = 0.0, 0.0
    payload, observed = bytearray(), []
    for i, point in enumerate(points):
        raw = struct.pack("<ff", point.time_qn - previous, point.value)
        delta, value = struct.unpack("<ff", raw)
        if i and delta <= 0:
            raise ValueError("Point spacing cannot be represented by FL's float deltas")
        actual_time += delta
        observed.append({"time_qn": actual_time, "value": value, "tension": 0.0, "curve": 0})
        payload.extend(raw)
        previous = point.time_qn
    return bytes(payload), observed


def observed_creation(before, after, target_event, expected_points, track, start, length):
    """Resolve even a lost acknowledgement from new linked native objects, never an echo."""
    old_sources = {row["source_event"] for row in before["automation"]}
    candidates = [row for row in after["automation"] if row["source_event"] not in old_sources
                  and {"source_event": row["source_event"], "target_event": target_event} in after["links"]]
    if len(candidates) != 1:
        return None
    curve = candidates[0]
    matching = [clip for clip in after["clips"] if clip["source_id"] == curve["source_event"] + 0x5000
                and (clip["track"], clip["start_tick"], clip["length_tick"], clip["muted"]) ==
                (track, start, length, False)]
    if len(matching) != 1 or curve["points"] != expected_points:
        return None
    # FL may reorder collection indices; compare old clips by their musical fields.
    remaining = [{k: v for k, v in clip.items() if k != "index"} for clip in after["clips"]]
    remaining.remove({k: v for k, v in matching[0].items() if k != "index"})
    for clip in before["clips"]:
        value = {k: v for k, v in clip.items() if k != "index"}
        if value not in remaining:
            return None
        remaining.remove(value)
    if remaining or any(curve not in after["automation"] for curve in before["automation"]):
        return None
    if any(link not in after["links"] for link in before["links"]):
        return None
    return {"automation": curve, "clip": matching[0]}
