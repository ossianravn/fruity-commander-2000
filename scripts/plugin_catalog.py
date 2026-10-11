"""Discover installed FL presets without treating them as loaded plugins."""

from pathlib import Path

from fl_studio_mcp.host_config import fl_studio_user_data_dir

from scripts.windows_project import ProjectReader


def validate_preset(preset_path, expected_plugin_name):
    path = Path(preset_path)
    if not path.is_absolute() or path.suffix.lower() != ".fst" or not path.is_file():
        raise ValueError("Provide an existing absolute .fst plugin preset path")
    with path.open("rb") as stream:
        if stream.read(4) != b"FLhd":
            raise ValueError("The requested file is not an FL preset")
    if not expected_plugin_name.strip():
        raise ValueError("The expected loaded plugin name is required for identity verification")
    return path.resolve()


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


def list_presets(kind, query=""):
    user = fl_studio_user_data_dir() / "Presets/Plugin database"
    with ProjectReader() as reader:
        factory = reader.engine.parent / "Data/Patches/Plugin database"
    roots = [root / folder for root in (user, factory)
             for folder in (f"Installed/{kind}", kind)]
    return {kind.lower(): generator_entries(roots, query),
            "searched_roots": [str(root) for root in roots]}


def list_generators(query=""):
    return list_presets("Generators", query)


def list_effects(query=""):
    return list_presets("Effects", query)
