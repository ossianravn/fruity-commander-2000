#pragma once
#include "protocol.h"

// FL copies a refcount -1 Delphi constant if it retains the string.
struct ConstantPath {
    WORD codepage = 1200, unit = 2;
    int32_t references = -1;
    uint32_t length = 0;
    wchar_t text[32768]{};

    explicit ConstantPath(const wchar_t* source) {
        length = static_cast<uint32_t>(wcsnlen_s(source, 32768));
        if (length < 32768) wcscpy_s(text, source);
    }
};
