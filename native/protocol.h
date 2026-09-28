#pragma once
#include <windows.h>
#include <cstdint>
#include <cwchar>

constexpr wchar_t MessageName[] = L"FruityCommander.Native.v3";
constexpr uint32_t ProtocolVersion = 3;
enum Operation : uint32_t { Probe = 1, RunOwnedScore = 2, AddGenerator = 3,
                            AddAutomation = 4, PlacePattern = 5, SelectPlaylistTime = 6,
                            LoadPluginState = 7, ReviseAutomation = 8,
                            AddSample = 9, SaveProjectToPath = 10,
                            AddAudioSample = 11, PlaceAudio = 12 };
enum Status : LONG { Pending = 0, Running = 1, Complete = 2, Failed = 3 };

// Fixed UTF-16 fields use the Windows extended-path capacity, not a music limit.
struct Request {
    uint32_t version;
    uint32_t bytes;
    uint32_t process;
    uint32_t operation;
    uint64_t nonce;
    volatile LONG status;
    uint32_t thread;
    uint32_t exception;
    int32_t expected_channels;
    int32_t created_channel;
    int32_t source_event;
    uint32_t stage;  // Operation-specific progress; never sufficient musical verification.
    int32_t created_clip;
    wchar_t path[32768];
    wchar_t project[32768];
    wchar_t error[512];
};

inline void MappingName(wchar_t* buffer, size_t size, DWORD pid, uint64_t nonce) {
    swprintf_s(buffer, size, L"Local\\FruityCommander.%lu.%016llx", pid, nonce);
}

bool RunScore(Request& request);
bool LoadGenerator(Request& request);
bool CreateAutomation(Request& request);
bool ReplaceAutomation(Request& request);
bool PlacePatternClip(Request& request);
bool SelectPlaylistRange(Request& request);
bool LoadGeneratorState(Request& request);
bool LoadSample(Request& request);
bool SaveProjectAs(Request& request);
bool PlaceAudioClip(Request& request);
