"""Pattern naming without an invented cap; FL readback decides exact success."""

from typing import Annotated

from pydantic import Field
from fl_studio_mcp import performance as p, track_b_contracts as contracts


class ExpectedIdentity(contracts.ExpectedPatternIdentityState):
    name: str | None = None


class IdentitySnapshot(contracts.PatternIdentitySnapshot):
    name: str | None = None


class IdentityWrite(contracts.VerifiedPatternIdentityWrite):
    requested_name: str | None = None
    before: IdentitySnapshot
    after: IdentitySnapshot


def snapshot(raw):
    value = p._snapshot_payload(raw, "pattern identity snapshot")
    return IdentitySnapshot(name=value.get("name"),
                            color=p._bridge_color(value.get("color"), "pattern"))


def set_pattern_identity(self, *, pattern_number, name=None, color=None,
                         session_fingerprint=None, expected_before=None):
    pattern = p._strict_int(pattern_number, "pattern_number", low=1,
                            high=p.MAX_PATTERN_NUMBER)
    if name is not None and not isinstance(name, str):
        raise ValueError("name must be text")
    color_value = (None if color is None else
                   p._strict_int(color, "color", low=0, high=p.FL_COLOR_WORD_MAX))
    if name is None and color_value is None:
        raise ValueError("name, color, or both is required")
    arguments = {"pattern": pattern}
    if name is not None:
        arguments["name"] = name
    if color_value is not None:
        arguments["color"] = color_value
    raw = self._call("pattern.set_identity", arguments,
                     session_fingerprint=session_fingerprint,
                     expected_before=expected_before)
    p._echoed_index(raw, "pattern", pattern, low=1)
    fields = p._verified_fields(raw)
    name_verified = None if name is None else p._strict_field_bool(fields, "name")
    color_verified = (None if color_value is None else
                      p._strict_field_bool(fields, "color"))
    verified = p._strict_bool(raw, "verified")
    before, after = snapshot(raw.get("before")), snapshot(raw.get("after"))
    proofs = [proof for request, proof in ((name, name_verified),
              (color_value, color_verified)) if request is not None]
    p._require_aggregate_verified(reported=verified,
                                  expected=all(proof is True for proof in proofs),
                                  label="pattern identity aggregate")
    if name is not None:
        p._require_verified_value(reported=name_verified is True,
                                  matches=after.name == name, label="pattern name")
    if color_value is not None:
        p._require_verified_value(reported=color_verified is True,
                                  matches=p.fl_colors_equivalent(after.color, color_value),
                                  label="pattern color")
    summary, warnings = p._summary(
        verified, "FL read every requested pattern identity field back on a later tick.",
        "At least one requested pattern identity field did not read back exactly.")
    return IdentityWrite(
        applied_at=p._now(), pattern_number=pattern, requested_name=name,
        requested_color=color_value, before=before, after=after,
        name_verified=name_verified, color_verified=color_verified,
        verified=verified, verification_summary=summary,
        undo_point_created=p._optional_bool(raw.get("undo_point_created")),
        warnings=p._warnings(raw, warnings), **p._precondition_fields(raw))


def install():
    p.TrackBController.set_pattern_identity = set_pattern_identity


def register(server):
    server.mcp.remove_tool("fl_set_pattern_identity")

    @server.mcp.tool(name="fl_set_pattern_identity", annotations=server.MUTATING)
    async def fl_set_pattern_identity(
        pattern_number: Annotated[int, Field(ge=1, le=p.MAX_PATTERN_NUMBER)],
        name: str | None = None,
        color: Annotated[int | None, Field(ge=0, le=p.FL_COLOR_WORD_MAX)] = None,
        session_fingerprint: server.SessionFingerprintArg = None,
        expected_before: ExpectedIdentity | None = None,
    ) -> IdentityWrite:
        """Set pattern name/color and inspect the actual result on a later host tick.

        Preserves full names. If FL changes the requested name, returns the
        observed name and verified=false. Does not save the project or retry.
        """
        return await server._performance_write(
            "set_pattern_identity", pattern_number=pattern_number, name=name,
            color=color, session_fingerprint=session_fingerprint,
            expected_before=expected_before)
