#include "playlist_host.h"
#include <cmath>

struct AutomationInput {
    uint64_t target_object;
    int32_t channel;
    uint32_t target_event;
    Placement placement;
    uint32_t point_count;
};
struct Point { float delta, value; };
static_assert(sizeof(AutomationInput) == 40);
static_assert(sizeof(Point) == 8);

static bool WritePoints(Request& request, uintptr_t base, uintptr_t envelope,
                        const Point* points, uint32_t count) {
    reinterpret_cast<void(*)(uintptr_t, uintptr_t, uint64_t, uint64_t)>(base + 0x17FC0)(
        envelope + 0x28, base + 0x797158, 1, count);
    const auto array = Read<uintptr_t>(envelope + 0x28);
    if (!array || Read<int64_t>(array - 8) != count)
        return Fail(request, L"Automation point allocation is unconfirmed");
    for (uint32_t i = 0; i < count; ++i) {
        auto* record = reinterpret_cast<void*>(array + uint64_t(i) * 0x20);
        memset(record, 0, 0x20);
        memcpy(record, &points[i], sizeof(Point));
    }
    reinterpret_cast<void(*)(uintptr_t)>(base + 0x79FE90)(envelope);
    request.stage = 2;
    return true;
}

bool CreateAutomation(Request& request) {
    if (request.bytes < sizeof(Request) + sizeof(AutomationInput))
        return Fail(request, L"Automation request is incomplete");
    const auto& input = *reinterpret_cast<const AutomationInput*>(&request + 1);
    if (request.bytes != sizeof(Request) + sizeof(input) + uint64_t(input.point_count) * sizeof(Point)
        || input.point_count < 2)
        return Fail(request, L"Automation point payload does not match its declared length");
    const auto* points = reinterpret_cast<const Point*>(&input + 1);
    double duration = 0;
    for (uint32_t i = 0; i < input.point_count; ++i) {
        if (!std::isfinite(points[i].delta) || (i ? points[i].delta <= 0 : points[i].delta != 0)
            || !std::isfinite(points[i].value) || points[i].value < 0 || points[i].value > 1)
            return Fail(request, L"Invalid native automation point");
        duration += points[i].delta;
    }
    const auto base = HostBase(request);
    if (!base) return false;
    const auto list = Read<uintptr_t>(Read<uintptr_t>(base + 0x11E6280));
    if (Read<int>(list + 0x10) != request.expected_channels || input.channel < 0
        || input.channel >= request.expected_channels)
        return Fail(request, L"Target channel inventory changed before automation creation");
    const auto target = Read<uintptr_t>(Read<uintptr_t>(list + 8) + uint64_t(input.channel) * 8);
    const uint32_t event = Read<uint32_t>(target + 0x9C);
    if (target != input.target_object || event >= 0x10000000 || (event & 0xFFFF)
        || input.target_event < event + 0x8000 || input.target_event > event + 0xFFFF)
        return Fail(request, L"Generator parameter identity changed before automation creation");
    const auto collection = PlaylistCollection(request, base, input.placement);
    if (!collection) return false;
    // FL owns channel allocation, controller linking, undo registration and dirty state.
    auto create = reinterpret_cast<uintptr_t(*)(uint32_t, uint8_t, uintptr_t, uint8_t, uint8_t)>(base + 0xD91560);
    request.stage = 1;  // A failure after entering creation may have changed FL.
    const auto channel = create(input.target_event, 0, 0, 0, 1);
    if (!channel || Read<int>(list + 0x10) != request.expected_channels + 1)
        return Fail(request, L"Automation channel allocation is unconfirmed");
    request.created_channel = -1;
    for (int i = 0; i < Read<int>(list + 0x10); ++i)
        if (Read<uintptr_t>(Read<uintptr_t>(list + 8) + uint64_t(i) * 8) == channel)
            request.created_channel = i;
    request.source_event = Read<int>(channel + 0x9C);
    const auto envelope = Read<uintptr_t>(Read<uintptr_t>(channel + 0x360) + 0x10);
    if (request.created_channel < 0 || Read<int>(channel + 0x160) != 5
        || Read<int>(envelope + 0x58) != 4 || Read<uintptr_t>(envelope) != base + 0x797558
        || Read<uintptr_t>(Read<uintptr_t>(envelope) + 0x40) != base + 0x79FE90
        || duration > Read<double>(envelope + 0x68))
        return Fail(request, L"Created automation envelope has an unexpected representation");
    if (!WritePoints(request, base, envelope, points, input.point_count)) return false;
    return InsertPlaylistClip(request, base, collection, input.placement,
                              static_cast<uint32_t>(request.source_event) + 0x5000);
}

bool ReplaceAutomation(Request& request) {
    struct Input {
        uint64_t channel, envelope;
        int32_t index;
        uint32_t source, before_count, after_count;
    };
    static_assert(sizeof(Input) == 32);
    if (request.bytes < sizeof(Request) + sizeof(Input))
        return Fail(request, L"Automation revision payload is incomplete");
    const auto& input = *reinterpret_cast<const Input*>(&request + 1);
    const uint64_t old_size = uint64_t(input.before_count) * 32;
    if (request.bytes != sizeof(Request) + sizeof(Input) + old_size + uint64_t(input.after_count) * 8
        || !input.before_count || input.after_count < 2)
        return Fail(request, L"Automation revision point counts are invalid");
    const auto* old = reinterpret_cast<const unsigned char*>(&input + 1);
    const auto* points = reinterpret_cast<const Point*>(old + old_size);
    const auto base = HostBase(request);
    if (!base) return false;
    const auto list = Read<uintptr_t>(Read<uintptr_t>(base + 0x11E6280));
    if (input.index < 0 || input.index >= Read<int>(list + 0x10)
        || Read<uintptr_t>(Read<uintptr_t>(list + 8) + uint64_t(input.index) * 8) != input.channel
        || Read<int>(input.channel + 0x160) != 5 || Read<uint32_t>(input.channel + 0x9C) != input.source)
        return Fail(request, L"Automation source changed before revision");
    const auto envelope = Read<uintptr_t>(Read<uintptr_t>(input.channel + 0x360) + 0x10);
    if (envelope != input.envelope || Read<uintptr_t>(envelope) != base + 0x797558
        || Read<int>(envelope + 0x58) != 4
        || Read<uintptr_t>(Read<uintptr_t>(envelope) + 0x40) != base + 0x79FE90)
        return Fail(request, L"Automation envelope changed before revision");
    const auto array = Read<uintptr_t>(envelope + 0x28);
    if (!array || Read<int64_t>(array - 8) != input.before_count
        || memcmp(reinterpret_cast<const void*>(array), old, static_cast<size_t>(old_size)))
        return Fail(request, L"Automation points changed before revision");
    double duration = 0, previous_duration = 0;
    for (uint32_t i = 0; i < input.before_count; ++i)
        previous_duration += Read<float>(array + uint64_t(i) * 32);
    for (uint32_t i = 0; i < input.after_count; ++i) {
        if (!std::isfinite(points[i].delta) || (i ? points[i].delta <= 0 : points[i].delta != 0)
            || !std::isfinite(points[i].value) || points[i].value < 0 || points[i].value > 1)
            return Fail(request, L"Invalid replacement automation point");
        duration += points[i].delta;
    }
    if (duration != previous_duration || duration > Read<double>(envelope + 0x68))
        return Fail(request, L"Revision must preserve the automation source extent");
    struct Label {
        WORD codepage = 1200, unit = 2;
        int32_t references = -1;
        uint32_t length = 15;
        wchar_t text[16] = L"Edit automation";
    } label;
    const auto history = Read<uintptr_t>(Read<uintptr_t>(base + 0x11E5CE0));
    // Native channel-specific undo captures the envelope plus Playlist state.
    // MIDI UF_* constants are not the native history bitset on this build.
    reinterpret_cast<void(*)(uintptr_t, const wchar_t*, int)>(base + 0xC17970)(
        history, label.text, input.index);
    request.stage = 1;
    if (!WritePoints(request, base, envelope, points, input.after_count)) return false;
    const int changed = 1;
    memcpy(reinterpret_cast<void*>(Read<uintptr_t>(base + 0x11E4C38)), &changed, sizeof(changed));
    reinterpret_cast<void(*)(int, int)>(base + 0x7D6930)(7, 0);
    reinterpret_cast<void(*)(int)>(base + 0xF00110)(Read<int>(base + 0x11DA658));
    request.stage = 3;
    return true;
}
