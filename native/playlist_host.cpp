#include "playlist_host.h"
#include <climits>

uintptr_t PlaylistCollection(Request& request, uintptr_t base, const Placement& p) {
    if (p.track < 1 || p.track > 500 || p.start < 0 || p.length <= 0
        || int64_t(p.start) + p.length > INT_MAX || p.arrangement < 0
        || Read<int>(base + 0x11DA658) != p.arrangement) {
        Fail(request, L"Playlist position or current arrangement does not match");
        return 0;
    }
    auto get = reinterpret_cast<uintptr_t(*)()>(base + 0xEE6580);
    const auto collection = Read<uintptr_t>(get() + 0x14);
    const auto table = Read<uintptr_t>(collection);
    // This engine uses 88-byte records, unlike the inspected reference build's 72.
    if (Read<int>(collection + 0x10) != 0x58
        || Read<int>(collection + 0x14) != p.expected_clips
        || table != base + 0xC53C38
        || Read<uintptr_t>(table + 8) != base + 0xC61F30
        || Read<uintptr_t>(table + 0x10) != base + 0xC61ED0) {
        Fail(request, L"Playlist collection changed or has an unexpected layout");
        return 0;
    }
    return collection;
}

bool InsertPlaylistClip(Request& request, uintptr_t base, uintptr_t collection,
                        const Placement& p, uint32_t source) {
    alignas(8) unsigned char record[0x58]{};
    reinterpret_cast<void(*)(uintptr_t, void*)>(base + 0xC61ED0)(collection, record);
    const auto track = static_cast<int16_t>(500 - p.track);
    memcpy(record, &p.start, 4);
    memcpy(record + 4, &source, 4);
    memcpy(record + 8, &p.length, 4);
    memcpy(record + 0xC, &track, 2);
    record[0x13] |= 0x80;
    // Use FL's source-range setter: +8 alone is a derived length cache.
    reinterpret_cast<void(*)(void*, double, double)>(base + 0xC641A0)(
        record, 0.0, static_cast<double>(p.length));
    const int index = reinterpret_cast<int(*)(uintptr_t, void*)>(base + 0xC61F30)(collection, record);
    request.created_clip = index;
    request.stage = 3;
    if (index < 0 || Read<int>(collection + 0x14) != p.expected_clips + 1
        || index >= Read<int>(collection + 0x14))
        return Fail(request, L"Playlist insertion did not return the expected collection entry");
    // FL's editing paths inline this changed-state write plus project notification.
    // Same-index arrangement refresh does not mark edits dirty on its own.
    const int changed = 1;
    memcpy(reinterpret_cast<void*>(Read<uintptr_t>(base + 0x11E4C38)), &changed, sizeof(changed));
    reinterpret_cast<void(*)(int, int)>(base + 0x7D6930)(7, 0);
    reinterpret_cast<void(*)(uintptr_t)>(base + 0xC60830)(collection);
    // The ordinary arrangement selector refreshes sources, song extent and Playlist paint.
    reinterpret_cast<void(*)(int)>(base + 0xF00110)(p.arrangement);
    request.stage = 4;
    return true;
}

void BeginPlaylistEdit(uintptr_t base) {
    struct Label {
        WORD codepage = 1200, unit = 2;
        int32_t references = -1;
        uint32_t length = 10;
        wchar_t text[11] = L"Place clip";
    } label;
    const uint64_t flags = 4;  // UF_PL, same owner/call as general.saveUndo.
    const auto history = Read<uintptr_t>(Read<uintptr_t>(base + 0x11E5CE0));
    reinterpret_cast<void(*)(uintptr_t, const wchar_t*, const uint64_t*, uint8_t)>(base + 0xC175E0)(
        history, label.text, &flags, 1);
}

bool PlacePatternClip(Request& request) {
    struct Input { uint64_t name_pointer; int32_t pattern; Placement placement; };
    static_assert(sizeof(Input) == 32);
    if (request.bytes != sizeof(Request) + sizeof(Input))
        return Fail(request, L"Pattern placement payload has the wrong size");
    const auto& input = *reinterpret_cast<const Input*>(&request + 1);
    const auto base = HostBase(request);
    if (!base) return false;
    // FL's own patternMax callback returns 999 on this qualified binary.
    if (input.pattern < 1 || input.pattern > 999
        || Read<uintptr_t>(base + 0x1543CE0 + uint64_t(input.pattern) * 0xC0) != input.name_pointer)
        return Fail(request, L"Pattern identity changed before Playlist placement");
    const auto collection = PlaylistCollection(request, base, input.placement);
    if (!collection) return false;
    BeginPlaylistEdit(base);
    request.stage = 1;
    return InsertPlaylistClip(request, base, collection, input.placement,
                              0x50005000u + (static_cast<uint32_t>(input.pattern) << 16));
}

bool SelectPlaylistRange(Request& request) {
    struct Input { uint64_t owner; int32_t start, end; };
    if (request.bytes != sizeof(Request) + sizeof(Input))
        return Fail(request, L"Playlist selection payload has the wrong size");
    const auto& input = *reinterpret_cast<const Input*>(&request + 1);
    const auto base = HostBase(request);
    if (!base) return false;
    const auto playlist = Read<uintptr_t>(Read<uintptr_t>(base + 0x11E7630));
    if (!playlist || playlist != input.owner)
        return Fail(request, L"Playlist window changed before time selection");
    if (!((input.start == -1 && input.end == -1) || (input.start >= 0 && input.end > input.start)))
        return Fail(request, L"Invalid Playlist time selection");
    request.stage = 1;
    // Same TEventEditForm selection method as arrangement.liveSelection, but
    // explicitly owns the Playlist rather than whichever editor has focus.
    using Select = void (*)(uintptr_t, int, int, uint8_t, uint8_t);
    reinterpret_cast<Select>(base + 0xA43F40)(playlist, input.start, input.end, 1, 1);
    request.stage = 2;
    return true;
}
