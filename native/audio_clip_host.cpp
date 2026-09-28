#include "playlist_host.h"

bool PlaceAudioClip(Request& request) {
    struct Input { uint64_t channel; int32_t index; uint32_t source; Placement placement; };
    static_assert(sizeof(Input) == 40);
    if (request.bytes != sizeof(Request) + sizeof(Input))
        return Fail(request, L"Audio placement payload has the wrong size");
    const auto& input = *reinterpret_cast<const Input*>(&request + 1);
    const auto base = HostBase(request);
    if (!base) return false;
    const auto listing = Read<uintptr_t>(Read<uintptr_t>(base + 0x11E6280));
    if (input.index < 0 || input.index >= Read<int>(listing + 0x10)
        || Read<uintptr_t>(Read<uintptr_t>(listing + 8) + input.index * 8) != input.channel
        || Read<int>(input.channel + 0x160) != 4
        || Read<uint32_t>(input.channel + 0x9C) != input.source)
        return Fail(request, L"Audio Clip source changed before placement");
    const auto collection = PlaylistCollection(request, base, input.placement);
    if (!collection) return false;
    BeginPlaylistEdit(base);
    request.stage = 1;
    return InsertPlaylistClip(request, base, collection, input.placement, input.source + 0x5000);
}
