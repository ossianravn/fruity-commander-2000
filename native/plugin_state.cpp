#include "host_access.h"
#include <vector>

bool LoadGeneratorState(Request& request) {
    struct Input { uint64_t channel, instance; int32_t index, padding; };
    if (request.bytes != sizeof(Request) + sizeof(Input))
        return Fail(request, L"Plugin state payload has the wrong size");
    const auto& input = *reinterpret_cast<const Input*>(&request + 1);
    const auto base = HostBase(request);
    if (!base) return false;
    const auto listing = Read<uintptr_t>(Read<uintptr_t>(base + 0x11E6280));
    if (input.index < 0 || input.index >= Read<int>(listing + 0x10)
        || Read<uintptr_t>(Read<uintptr_t>(listing + 8) + input.index * 8) != input.channel)
        return Fail(request, L"Generator changed before state loading");
    const auto container = Read<uintptr_t>(input.channel + 0x38);
    const auto host = container + 0x48;
    if (!container || Read<uintptr_t>(Read<uintptr_t>(host) + 0x20) != base + 0xF32F81)
        return Fail(request, L"Unqualified generator instance owner");
    const auto instance = Read<uintptr_t>(container + 0x2C);
    if (!instance || instance != input.instance)
        return Fail(request, L"Hosted plugin instance changed before state loading");
    const auto wrapper = GetModuleHandleW(L"Fruity Wrapper_x64.dll");
    constexpr BYTE digest[] = {
        0x9c,0x0b,0xc8,0xd6,0xf6,0x3c,0x7a,0x85,0xf4,0x01,0xad,0xab,0x43,0x10,0xe4,0x64,
        0x68,0x5a,0x21,0x42,0xdb,0xd8,0x5b,0x67,0xfc,0x08,0x0a,0xc8,0x23,0x97,0xb6,0x13};
    const auto dispatcher = Read<uintptr_t>(Read<uintptr_t>(instance) + 8);
    if (!QualifiedModule(wrapper, digest)
        || dispatcher != reinterpret_cast<uintptr_t>(wrapper) + 0x46C400)
        return Fail(request, L"State loading is unqualified for this wrapper binary");
    const auto length = wcsnlen_s(request.path, 32768);
    if (!length || length == 32768 || GetFileAttributesW(request.path) == INVALID_FILE_ATTRIBUTES)
        return Fail(request, L"Plugin preset file is unavailable");
    const int size = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, request.path, -1,
                                        nullptr, 0, nullptr, nullptr);
    if (size <= 0) return Fail(request, L"Cannot encode the plugin preset path");
    std::vector<char> path(size);
    if (!WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, request.path, -1,
                            path.data(), size, nullptr, nullptr))
        return Fail(request, L"Cannot encode the plugin preset path");
    request.stage = 1;
    using Dispatch = intptr_t (*)(uintptr_t, intptr_t, intptr_t, const char*);
    const auto accepted = reinterpret_cast<Dispatch>(dispatcher)(instance, 0x12, 0, path.data());
    if (!accepted) return Fail(request, L"Wrapper did not accept the preset file");
    request.stage = 2;
    const int changed = 1;
    memcpy(reinterpret_cast<void*>(Read<uintptr_t>(base + 0x11E4C38)), &changed, sizeof(changed));
    reinterpret_cast<void(*)(int, int)>(base + 0x7D6930)(7, 0);
    return true;
}
