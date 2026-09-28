#include "host_access.h"

// Independently inspected on 26.1.6.5639. FruityLink's MIT SDK informed the
// Delphi menu layout; no older-build offsets or generic call interface are used.
static uintptr_t FindItem(uintptr_t item, int index, uintptr_t callback, uintptr_t owner) {
    if (Read<int>(item + 0x18) == index && Read<uintptr_t>(item + 0x100) == callback
        && Read<uintptr_t>(item + 0x108) == owner) return item;
    const auto children = Read<uintptr_t>(item + 0xB0);
    if (!children) return 0;
    const auto count = Read<int>(children + 0x10);
    const auto array = Read<uintptr_t>(children + 8);
    for (int i = 0; i < count; ++i) {
        const auto found = FindItem(Read<uintptr_t>(array + i * 8), index, callback, owner);
        if (found) return found;
    }
    return 0;
}

static int FindScript(uintptr_t base, const wchar_t* path) {
    const auto listing = Read<uintptr_t>(base + 0x12BE9F8);
    if (!listing) return -1;
    const auto count = Read<int>(listing + 0x40);
    const auto array = Read<uintptr_t>(listing + 0x38);
    for (int i = 0; i < count; ++i) {
        if (StringEquals(Read<uintptr_t>(array + i * 16), path)) return i;
    }
    return -1;
}

bool RunScore(Request& request) {
    const auto base = HostBase(request);
    if (!base) return false;
    if (wcsnlen_s(request.path, 32768) == 32768)
        return Fail(request, L"Script path has no terminator");
    const auto name = wcsrchr(request.path, L'\\');
    if (!name || _wcsicmp(name + 1, L"Postfader_Apply.PYSCRIPT"))
        return Fail(request, L"Request does not identify the owned score script");
    const auto main = Read<uintptr_t>(Read<uintptr_t>(base + 0x11E5060));
    const auto owner = Read<uintptr_t>(Read<uintptr_t>(base + 0x11E85C0));
    const auto separator = Read<uintptr_t>(main + 0x1660);
    if (!owner || !separator) return Fail(request, L"FL's score editor is not initialized");
    const auto callback = base + 0xA3A380;
    // The real menu-population call at RVA E090A3 uses these exact owners.
    // Refresh every dispatch: retargeting can replace the editor object, so
    // existing menu callbacks may still belong to the previous editor.
    using Refresh = void (*)(uintptr_t, uintptr_t, unsigned char);
    reinterpret_cast<Refresh>(base + 0xA3A540)(owner, separator, 1);
    const int index = FindScript(base, request.path);
    if (index < 0) return Fail(request, L"The owned script is absent from FL's script inventory");
    const auto item = FindItem(Read<uintptr_t>(separator + 0xBC), index, callback, owner);
    if (!item) return Fail(request, L"FL has no live menu item for the owned script");
    using Click = void (*)(uintptr_t, uintptr_t);
    reinterpret_cast<Click>(callback)(owner, item);
    return true;
}
