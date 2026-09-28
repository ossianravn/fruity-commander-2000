#include "host_access.h"
#include "constant_path.h"

// Qualified on the same exact engine as score_host.cpp. Six load arguments are
// essential on FL 2026: the fifth is another Delphi string, the sixth a double.
bool LoadChannelFile(Request& request, bool sample) {
    const auto base = HostBase(request);
    if (!base) return false;
    const auto length = wcsnlen_s(request.path, 32768);
    if (!length || length == 32768 || length < 4
        || _wcsicmp(request.path + length - 4, sample ? L".wav" : L".fst"))
        return Fail(request, L"Channel loading requires the expected file type");
    const auto attributes = GetFileAttributesW(request.path);
    if (attributes == INVALID_FILE_ATTRIBUTES || (attributes & FILE_ATTRIBUTE_DIRECTORY))
        return Fail(request, L"The requested generator preset is unavailable");
    const auto listing = Read<uintptr_t>(Read<uintptr_t>(base + 0x11E6280));
    const int count = Read<int>(listing + 0x10);
    if (count != request.expected_channels)
        return Fail(request, L"Channel inventory changed before insertion");
    const wchar_t* preset = nullptr;
    if (request.operation == AddAudioSample) {
        const auto bytes = request.bytes - sizeof(Request);
        if (bytes < 2 || bytes > 65536 || bytes % 2)
            return Fail(request, L"Audio Clip preset payload is invalid");
        preset = reinterpret_cast<const wchar_t*>(&request + 1);
        if (preset[bytes / 2 - 1] || GetFileAttributesW(preset) == INVALID_FILE_ATTRIBUTES)
            return Fail(request, L"FL's Audio Clip factory preset is unavailable");
    }

    // A refcount -1 Delphi constant is copied by FL when retained. Keep it alive
    // for the entire synchronous host call; do not fabricate a refcounted object.
    const ConstantPath path(request.path);

    using Insert = uintptr_t (*)(int, unsigned char, unsigned char);
    const auto channel = reinterpret_cast<Insert>(base + 0xC03D00)(count, 0, 0);
    if (!channel) return Fail(request, L"FL did not insert a generator channel");
    request.created_channel = count;
    request.source_event = Read<int>(channel + 0x9C);
    request.stage = 1;
    const auto vmt = Read<uintptr_t>(channel);
    const auto load = Read<uintptr_t>(vmt + 0x150);
    if (load != base + 0xBFEB80)
        return Fail(request, L"Channel inserted, but its load method is not qualified");
    using Load = void (*)(uintptr_t, const wchar_t*, unsigned char, WORD, uintptr_t, double);
    if (preset) {
        const ConstantPath clipPreset(preset);
        reinterpret_cast<Load>(load)(channel, clipPreset.text, 0, 0x42, 0, -1.0);
        if (Read<int>(channel + 0x160) != 4)
            return Fail(request, L"Inserted channel did not become an Audio Clip");
    }
    reinterpret_cast<Load>(load)(channel, path.text, sample ? 1 : 0, 0x42, 0, -1.0);
    request.stage = 2;
    using Refresh = void (*)();
    reinterpret_cast<Refresh>(base + 0xD85F50)();
    const auto after = Read<uintptr_t>(Read<uintptr_t>(base + 0x11E6280));
    if (Read<int>(after + 0x10) != count + 1
        || Read<uintptr_t>(Read<uintptr_t>(after + 8) + count * 8) != channel)
        return Fail(request, L"Generator loading changed the expected channel inventory");
    return true;
}

bool LoadGenerator(Request& request) { return LoadChannelFile(request, false); }
bool LoadSample(Request& request) { return LoadChannelFile(request, true); }
