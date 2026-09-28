#include "protocol.h"

static void Execute(Request& request) {
    request.thread = GetCurrentThreadId();
    __try {
        bool success = false;
        if (request.operation == Probe) success = true;
        else if (request.operation == RunOwnedScore) success = RunScore(request);
        else if (request.operation == AddGenerator) success = LoadGenerator(request);
        else if (request.operation == AddAutomation) success = CreateAutomation(request);
        else if (request.operation == PlacePattern) success = PlacePatternClip(request);
        else if (request.operation == SelectPlaylistTime) success = SelectPlaylistRange(request);
        else if (request.operation == LoadPluginState) success = LoadGeneratorState(request);
        else if (request.operation == ReviseAutomation) success = ReplaceAutomation(request);
        else if (request.operation == AddSample) success = LoadSample(request);
        else if (request.operation == AddAudioSample) success = LoadSample(request);
        else if (request.operation == PlaceAudio) success = PlaceAudioClip(request);
        else if (request.operation == SaveProjectToPath) success = SaveProjectAs(request);
        else wcscpy_s(request.error, L"Unknown native operation");
        InterlockedExchange(&request.status, success ? Complete : Failed);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        request.exception = GetExceptionCode();
        wcscpy_s(request.error, L"Native host exception; inspect the outcome before continuing");
        InterlockedExchange(&request.status, Failed);
    }
}

extern "C" __declspec(dllexport) LRESULT CALLBACK HostHook(int code, WPARAM wp, LPARAM lp) {
    if (code >= 0) {
        const auto* message = reinterpret_cast<CWPSTRUCT*>(lp);
        if (message->message == RegisterWindowMessageW(MessageName)) {
            wchar_t name[100];
            MappingName(name, _countof(name), GetCurrentProcessId(), message->lParam);
            HANDLE mapping = OpenFileMappingW(FILE_MAP_ALL_ACCESS, FALSE, name);
            if (mapping) {
                auto* request = static_cast<Request*>(MapViewOfFile(
                    mapping, FILE_MAP_ALL_ACCESS, 0, 0, 0));
                if (request) {
                    MEMORY_BASIC_INFORMATION region{};
                    if (VirtualQuery(request, &region, sizeof(region))
                        && region.RegionSize >= sizeof(Request)
                        && request->version == ProtocolVersion && request->bytes >= sizeof(Request)
                        && request->bytes <= region.RegionSize
                        && request->process == GetCurrentProcessId()
                        && request->nonce == static_cast<uint64_t>(message->lParam)
                        && InterlockedCompareExchange(&request->status, Running, Pending) == Pending) {
                        Execute(*request);
                    }
                    UnmapViewOfFile(request);
                }
                CloseHandle(mapping);
            }
        }
    }
    return CallNextHookEx(nullptr, code, wp, lp);
}
