#include "host_access.h"
#include "constant_path.h"

// FruityLink's MIT SDK mixer-slot technique, independently located on 26.1.6.5639.
// The six-argument slot VMT method loads and refreshes its own track/slot.
struct EffectTarget {
    int32_t track, slot;
    uint64_t array, object;
};

bool LoadMixerEffect(Request& request) {
    const auto base = HostBase(request);
    if (!base) return false;
    if (request.bytes != sizeof(Request) + sizeof(EffectTarget))
        return Fail(request, L"Mixer effect target payload is invalid");
    const auto target = Read<EffectTarget>(reinterpret_cast<uintptr_t>(&request + 1));
    const auto count = Read<int>(Read<uintptr_t>(base + 0x11E6200));
    if (target.track < 0 || target.track > count - 2 || target.slot < 0 || target.slot >= 10)
        return Fail(request, L"Mixer effect target is outside the live track/slot range");
    const auto array = Read<uintptr_t>(base + 0x11E4708);
    if (!array || array != target.array)
        return Fail(request, L"Mixer inventory changed before effect loading");
    const auto object = Read<uintptr_t>(array + target.track * 0x1478 + 0x134C + target.slot * 8);
    if (!object || object != target.object || Read<int>(object + 0x64) != -1)
        return Fail(request, L"Mixer effect slot changed or is no longer empty");
    if (Read<int>(object + 0x130) != target.track || Read<int>(object + 0x134) != target.slot)
        return Fail(request, L"Mixer slot does not report the requested target");
    const auto load = Read<uintptr_t>(Read<uintptr_t>(object) + 0xF0);
    if (load != base + 0xEC43D0)
        return Fail(request, L"Mixer effect load method is not qualified");
    const auto length = wcsnlen_s(request.path, 32768);
    if (length < 4 || length == 32768 || _wcsicmp(request.path + length - 4, L".fst"))
        return Fail(request, L"Mixer effect loading requires an FL preset");
    const auto attributes = GetFileAttributesW(request.path);
    if (attributes == INVALID_FILE_ATTRIBUTES || (attributes & FILE_ATTRIBUTE_DIRECTORY))
        return Fail(request, L"Mixer effect preset is unavailable");

    const ConstantPath path(request.path);
    using Load = void (*)(uintptr_t, int32_t, const wchar_t*, unsigned char, unsigned char, unsigned char);
    request.stage = 1;
    reinterpret_cast<Load>(load)(object, -3, path.text, 0, 1, 1);
    request.stage = 2;
    // The Python owner reads the actual plugin and preserved track/slot state.
    return true;
}
