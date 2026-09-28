"""Discover FL's generator preset entries without treating them as loaded plugins."""

from pathlib import Path

from fl_studio_mcp.host_config import fl_studio_user_data_dir

from scripts.windows_project import ProjectReader


def preset_metadata(path):
    sidecar = path.with_suffix(".nfo")
    if not sidecar.is_file():
        return {}
    data = sidecar.read_bytes()
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        source = data.decode("utf-16")
    else:
        source = data.decode("utf-8-sig")
    return dict(line.split("=", 1) for line in source.splitlines() if "=" in line)


def generator_entries(roots, query=""):
    entries = []
    seen = set()
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.fst")):
            path = path.resolve()
            if path in seen:
                continue
            seen.add(path)
            metadata = preset_metadata(path)
            name = metadata.get("ps_name") or path.stem
            if query.casefold() not in f"{name} {path.stem}".casefold():
                continue
            entries.append({"name": name, "preset_path": str(path),
                            "expected_plugin_name": metadata.get("ps_name"),
                            "vendor": metadata.get("ps_file_vendorname_0"),
                            "binary_path": metadata.get("ps_file_filename_0"),
                            "format": metadata.get("tip"),
                            "evidence": "FL_plugin_database_entry_not_loaded_instance"})
    return entries


def list_generators(query=""):
    user = fl_studio_user_data_dir() / "Presets/Plugin database"
    with ProjectReader() as reader:
        factory = reader.engine.parent / "Data/Patches/Plugin database"
    roots = [root / kind for root in (user, factory)
             for kind in ("Installed/Generators", "Generators")]
    return {"generators": generator_entries(roots, query),
            "searched_roots": [str(root) for root in roots]}
