"""FL Piano Roll range editing; only notes whose onsets are in scope are touched."""

# FL 26.1.6 crashes on a second script run importing native _decimal.
# Its bundled pure-Python implementation preserves exact decimal rounding.
from _pydecimal import Decimal, ROUND_HALF_UP

LENGTH_MARKER_MODE = 6  # Qualified against FL's native Length marker.


NOTE_FIELDS = (
    "number", "time", "length", "group", "pan", "velocity", "release", "color",
    "fcut", "fres", "pitchofs", "slide", "porta", "muted", "selected", "repeats",
)


def ticks(qn, ppq):
    return int((Decimal(str(qn)) * ppq).to_integral_value(rounding=ROUND_HALF_UP))


def note_snapshot(note):
    return {field: getattr(note, field) for field in NOTE_FIELDS}


def snapshot(score):
    return [note_snapshot(score.getNote(i)) for i in range(score.noteCount)]


def in_range(time, ppq, start, end):
    onset = Decimal(time) / ppq
    return Decimal(str(start)) <= onset < Decimal(str(end))


def signatures(notes):
    return sorted(tuple(note[field] for field in NOTE_FIELDS) for note in notes)


def markers_snapshot(score):
    markers = []
    for i in range(score.markerCount):
        marker = score.getMarker(i)
        row = {}
        for field in ("time", "name", "mode", "tsnum", "tsden"):
            row[field] = getattr(marker, field)
        markers.append(row)
    return markers


def inspect_score(flp, request):
    score = flp.score
    notes = snapshot(score)
    markers = markers_snapshot(score)
    lengths = [m["time"] for m in markers if m["mode"] == LENGTH_MARKER_MODE]
    return {"status": "observed", "ppq": score.PPQ, "notes": notes,
            "markers": markers,
            "phrase_length_qn": lengths[0] / score.PPQ if len(lengths) == 1 else None,
            "message": "Notes and timeline markers inspected in FL's score runtime."}


def note_timing(source, ppq, start, end):
    onset = ticks(source["start_qn"], ppq)
    endpoint = Decimal(str(source["start_qn"])) + Decimal(str(source["duration_qn"]))
    length = ticks(endpoint, ppq) - onset
    if length <= 0:
        raise ValueError("A requested note becomes zero ticks at the project PPQ")
    if not in_range(onset, ppq, start, end):
        raise ValueError("A rounded note onset falls outside the requested range")
    return onset, length


def prepare_notes(score, sources, start, end):
    prepared = []
    for source in sources:
        onset, length = note_timing(source, score.PPQ, start, end)
        note = score.getDefaultNoteProperties()
        note.number = source["pitch"]
        note.time, note.length = onset, length
        note.velocity = source["velocity"]
        prepared.append(note)
    return prepared


def create_score(flp, request):
    score = flp.score
    if score.noteCount or score.markerCount:
        raise ValueError("The new target score is no longer empty")
    if score.PPQ != request["expected_ppq"]:
        raise ValueError("Project PPQ changed after pattern preparation")
    extent = ticks(request["phrase_length_qn"], score.PPQ)
    if extent <= 0:
        raise ValueError("The phrase becomes zero ticks at the project PPQ")
    prepared = prepare_notes(score, request["notes"], 0, request["phrase_length_qn"])
    marker = flp.Marker()
    marker.time, marker.mode, marker.name = extent, LENGTH_MARKER_MODE, "Length"
    added = 0
    try:
        for note in prepared:
            score.addNote(note)
            added += 1
        score.addMarker(marker)
        observed = inspect_score(flp, {})
        expected = signatures([note_snapshot(n) for n in prepared])
        verified = (signatures(observed["notes"]) == expected
                    and observed["phrase_length_qn"] == extent / score.PPQ)
        return {**observed, "status": "applied" if verified else "partial",
                "added_count": added, "requested_phrase_length_qn": request["phrase_length_qn"],
                "message": "Created notes and phrase extent inspected in FL's score runtime."
                if verified else "The observed score or extent did not match the request."}
    except Exception as error:
        return {"status": "partial", "added_count": added,
                "message": f"{type(error).__name__}: {error}",
                "next_action": "Inspect the prepared pattern before correcting it."}


def replace_range(flp, request):
    score = flp.score
    ppq = score.PPQ
    start, end = request["range_start_qn"], request["range_end_qn"]
    before = snapshot(score)
    markers_before = markers_snapshot(score)
    outside = [n for n in before if not in_range(n["time"], ppq, start, end)]
    removed = [i for i, n in enumerate(before)
               if in_range(n["time"], ppq, start, end)]
    # Construct and validate every new note before removing any existing note.
    prepared = prepare_notes(score, request["notes"], start, end)

    mutation_started = False
    removed_count = added_count = 0
    try:
        for index in reversed(removed):
            mutation_started = True
            score.deleteNote(index)
            removed_count += 1
        for note in prepared:
            mutation_started = True
            score.addNote(note)
            added_count += 1
        after = snapshot(score)
        markers_after = markers_snapshot(score)
        after_outside = [n for n in after if not in_range(n["time"], ppq, start, end)]
        kept = signatures(outside) == signatures(after_outside)
        inside = [n for n in after if in_range(n["time"], ppq, start, end)]
        expected = signatures([note_snapshot(n) for n in prepared])
        verified = kept and signatures(inside) == expected and markers_before == markers_after
        return {"status": "applied" if verified else "partial", "ppq": ppq,
                "removed_count": len(removed), "added_count": len(prepared),
                "untouched_notes_preserved": kept, "notes": after,
                "markers_preserved": markers_before == markers_after,
                "markers": markers_after,
                "message": "Range and untouched notes inspected in FL's score runtime."
                if verified else "The observed score did not match the full postcondition."}
    except Exception as error:
        return {"status": "partial" if mutation_started else "failed",
                "removed_count": removed_count, "added_count": added_count,
                "message": f"{type(error).__name__}: {error}",
                "next_action": "Read the score before deciding how to correct it."}
