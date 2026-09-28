#pragma once
#include "host_access.h"
void BeginPlaylistEdit(uintptr_t base);

struct Placement {
    int32_t arrangement;
    int32_t expected_clips;
    int32_t track;
    int32_t start;
    int32_t length;
};

uintptr_t PlaylistCollection(Request& request, uintptr_t base, const Placement& placement);
bool InsertPlaylistClip(Request& request, uintptr_t base, uintptr_t collection,
                        const Placement& placement, uint32_t source);
