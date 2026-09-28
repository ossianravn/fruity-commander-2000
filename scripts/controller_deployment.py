"""Compose owned host extensions with the external, pinned controller.

Use PostFader's installer and hash stamp unchanged. Dependency files are never
edited. The installed generated controller is not maintained source.
"""

import argparse
import sys
from functools import lru_cache
from pathlib import Path

from fl_studio_mcp import bridge_install
from fl_studio_mcp.bridge_stamp import stamp_bridge_source


EXTENSIONS = ("host_patterns.py", "host_editor.py", "host_identity.py", "host_save.py",
              "host_history.py")


def controller_sources():
    return (bridge_install.bridge_source_path(),
            *(Path(__file__).with_name(name) for name in EXTENSIONS))


@lru_cache(maxsize=4)
def _compose(paths_and_stats):
    source = b"\n\n".join(Path(path).read_bytes() for path, _ in paths_and_stats)
    source.decode("ascii")  # FL's controller loader requires ASCII source.
    compile(source, "Fruity Commander controller", "exec")
    return stamp_bridge_source(source)


def expected_deployment():
    try:
        sources = []
        for path in controller_sources():
            stat = path.stat()
            sources.append((str(path), (stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)))
        return _compose(tuple(sources))
    except (OSError, ValueError, SyntaxError) as error:
        raise bridge_install.BridgeInstallError(
            f"Could not build Fruity Commander's controller: {error}") from error


def configure():
    bridge_install.expected_bridge_deployment = expected_deployment
    # The inspector may already have been imported by tools or tests.
    from fl_studio_mcp import readonly_inspector
    readonly_inspector.expected_bridge_deployment = expected_deployment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-data-dir", help="FL Studio user-data folder")
    arguments = parser.parse_args()
    configure()
    try:
        result = bridge_install.deploy(arguments.user_data_dir)
    except (bridge_install.BridgeInstallError, OSError) as error:
        parser.exit(1, f"Controller deployment failed: {error}\n")
    print(f"{'Installed' if result['changed'] else 'Already current'}: {result['target']}")
    print(f"Source SHA-256: {result['digest']}")
    if result["backup"]:
        print(f"Previous controller: {result['backup']}")
    print("In running FL: View > Script output > Fruity Commander > Reload script.")
    print("Restart the MCP connection after client code changes; verify matching provenance.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
