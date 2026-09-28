#include "engine_identity.h"
#include <bcrypt.h>

bool QualifiedModule(HMODULE engine, const BYTE* expected) {
    wchar_t path[32768];
    if (!engine || !GetModuleFileNameW(engine, path, _countof(path))) return false;
    HANDLE file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, nullptr,
                             OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) return false;
    BCRYPT_ALG_HANDLE algorithm = nullptr;
    BCRYPT_HASH_HANDLE hash = nullptr;
    bool ok = BCryptOpenAlgorithmProvider(&algorithm, BCRYPT_SHA256_ALGORITHM, nullptr, 0) == 0;
    if (ok) ok = BCryptCreateHash(algorithm, &hash, nullptr, 0, nullptr, 0, 0) == 0;
    BYTE buffer[65536], digest[32];
    DWORD count;
    while (ok) {
        if (!ReadFile(file, buffer, sizeof(buffer), &count, nullptr)) { ok = false; break; }
        if (!count) break;
        ok = BCryptHashData(hash, buffer, count, 0) == 0;
    }
    if (ok) ok = BCryptFinishHash(hash, digest, sizeof(digest), 0) == 0;
    if (hash) BCryptDestroyHash(hash);
    if (algorithm) BCryptCloseAlgorithmProvider(algorithm, 0);
    CloseHandle(file);
    return ok && memcmp(digest, expected, 32) == 0;
}

bool QualifiedEngine(HMODULE engine) {
    constexpr BYTE expected[] = {
        0xbc,0x36,0x37,0xc3,0xe4,0x16,0x94,0xc8,0x20,0x86,0x5e,0x75,0x7d,0x88,0xa4,0x2b,
        0xdc,0x15,0xb6,0xdb,0x40,0x11,0x58,0x2a,0x2e,0xf8,0xf4,0xd1,0xb0,0x5a,0x2d,0x95};
    return QualifiedModule(engine, expected);
}
