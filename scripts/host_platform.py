"""Select owned host routes by operating system, without FL or OS access at import."""

from fl_studio_mcp.host_config import platform_family


class HostRouteUnavailable(OSError):
    """This operating system has no implemented owned route for an operation."""


def family():
    return platform_family()


def is_macos():
    return platform_family() == "macos"


def require_windows_native(route):
    """Fail before any Win32 access when the qualified native route cannot apply."""
    current = platform_family()
    if current == "windows":
        return
    name = "macOS" if current == "macos" else "this operating system"
    raise HostRouteUnavailable(
        f"{route} uses Fruity Commander's Windows native helper; no {name} route is "
        "implemented yet. fl_get_capabilities lists the routes available here.")
