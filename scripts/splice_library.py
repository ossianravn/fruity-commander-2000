"""Owned Splice catalog search, adapted from the user's mpc-sample implementation.

SQLite reads include WAL state. Ownership and download state are distinct.
"""

import os
import sqlite3
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SpliceSearch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = ""
    tags: list[str] = Field(default_factory=list)
    key: str | None = None
    mode: Literal["major", "minor"] | None = None
    sample_type: Literal["loop", "oneshot"] | None = None
    bpm_min: float | None = None
    bpm_max: float | None = None
    availability: Literal["all", "local", "cloud"] = "all"
    limit: int = Field(default=20, ge=1)
    offset: int = Field(default=0, ge=0)
    database_path: str | None = None


def support_directory():
    if os.name != "nt":
        raise OSError("Splice Desktop discovery is currently qualified on Windows")
    return Path(os.environ["LOCALAPPDATA"]) / "SpliceSettings"


def find_database(explicit_path=None):
    if explicit_path:
        return Path(explicit_path).expanduser().resolve()
    paths = sorted((support_directory() / "users/default").glob("*/sounds.db"))
    if len(paths) != 1:
        raise ValueError(f"Found {len(paths)} Splice catalogs; provide database_path for the intended profile")
    return paths[0].resolve()


def connect(database_path=None):
    path = find_database(database_path)
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def owned_sample(file_hash, database_path=None):
    connection = connect(database_path)
    try:
        row = connection.execute("SELECT filename,file_hash,local_path FROM samples "
            "WHERE file_hash=? AND purchased_at IS NOT NULL", (file_hash,)).fetchone()
        if row is None:
            raise ValueError("The selected sound is not in this owned Splice catalog")
        return dict(row)
    finally:
        connection.close()


def search_owned(options):
    clauses, values = ["s.purchased_at IS NOT NULL"], []
    if options.query:
        escaped = options.query.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        clauses.append("lower(coalesce(s.filename,'') || ' ' || coalesce(s.tags,'') "
                       "|| ' ' || coalesce(p.name,'')) LIKE ? ESCAPE '\\'")
        values.append("%" + escaped + "%")
    for tag in options.tags:
        clauses.append("instr(',' || lower(s.tags) || ',', ?) > 0")
        values.append("," + tag.strip().lower() + ",")
    for column, value in (("audio_key", options.key), ("chord_type", options.mode),
                          ("sample_type", options.sample_type)):
        if value:
            clauses.append(f"lower(s.{column}) = ?")
            values.append(value.lower())
    for operator, value in ((">=", options.bpm_min), ("<=", options.bpm_max)):
        if value is not None:
            clauses.append(f"s.bpm {operator} ?")
            values.append(value)
    if options.availability != "all":
        operator = "!=" if options.availability == "local" else "="
        clauses.append(f"coalesce(s.local_path,'') {operator} ''")
    source = "FROM samples s LEFT JOIN packs p ON p.uuid=s.pack_uuid WHERE " + " AND ".join(clauses)
    connection = connect(options.database_path)
    try:
        connection.execute("BEGIN")
        inventory = dict(connection.execute("SELECT count(*) AS owned_samples, "
            "count(nullif(local_path,'')) AS samples_with_local_path FROM samples "
            "WHERE purchased_at IS NOT NULL").fetchone())
        total = connection.execute("SELECT count(*) " + source, values).fetchone()[0]
        rows = connection.execute("SELECT s.filename,s.file_hash,s.audio_key AS musical_key, "
            "s.chord_type AS mode,s.bpm,s.sample_type,s.duration AS duration_ms,s.tags,p.name AS pack, "
            "s.local_path " + source + " ORDER BY s.purchased_at DESC,s.id DESC LIMIT ? OFFSET ?",
            values + [options.limit, options.offset]).fetchall()
        results = []
        for row in rows:
            item = dict(row)
            item["tags"] = item["tags"].split(",") if item["tags"] else []
            item["file_exists"] = bool(item["local_path"]) and Path(item["local_path"]).is_file()
            results.append(item)
        return {"source": "Splice Desktop owned catalog", "inventory": inventory,
                "total_matches": total, "returned": len(results), "results": results}
    finally:
        connection.close()
