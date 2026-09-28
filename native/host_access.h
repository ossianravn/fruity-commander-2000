#pragma once
#include "protocol.h"
#include "engine_identity.h"

template<typename T> inline T Read(uintptr_t address) {
    T value;
    memcpy(&value, reinterpret_cast<const void*>(address), sizeof(value));
    return value;
}

inline bool Fail(Request& request, const wchar_t* error) {
    wcscpy_s(request.error, error);
    return false;
}

inline bool StringEquals(uintptr_t address, const wchar_t* expected) {
    if (!address) return !*expected;
    if (Read<WORD>(address - 12) != 1200 || Read<WORD>(address - 10) != 2) return false;
    const auto length = Read<uint32_t>(address - 4);
    return length < 32768 && wcsnlen_s(expected, 32768) == length
        && _wcsnicmp(reinterpret_cast<const wchar_t*>(address), expected, length) == 0;
}

inline uintptr_t HostBase(Request& request) {
    const auto engine = GetModuleHandleW(L"FLEngine_x64.dll");
    if (!QualifiedEngine(engine)) {
        Fail(request, L"Native execution is unqualified for this engine");
        return 0;
    }
    const auto base = reinterpret_cast<uintptr_t>(engine);
    if (!StringEquals(Read<uintptr_t>(base + 0x12C0C90), request.project)) {
        Fail(request, L"Project changed before native execution");
        return 0;
    }
    return base;
}
