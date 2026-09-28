#include <windows.h>
#include <cstdio>

static LRESULT CALLBACK WindowProc(HWND window, UINT message, WPARAM wp, LPARAM lp) {
    if (message == WM_APP + 1)
        return reinterpret_cast<LRESULT>(GetModuleHandleW(L"FruityCommanderHost.dll"));
    if (message == WM_APP + 2) {
        puts("busy");
        fflush(stdout);
        Sleep(200);
        return 0;
    }
    if (message == WM_CLOSE) { DestroyWindow(window); return 0; }
    if (message == WM_DESTROY) { PostQuitMessage(0); return 0; }
    return DefWindowProcW(window, message, wp, lp);
}

int main() {
    WNDCLASSW cls{};
    cls.lpfnWndProc = WindowProc;
    cls.hInstance = GetModuleHandleW(nullptr);
    cls.lpszClassName = L"FruityCommander.NativeTest";
    if (!RegisterClassW(&cls)) return 1;
    HWND window = CreateWindowW(cls.lpszClassName, L"Native dispatch fixture", 0,
                               0, 0, 0, 0, nullptr, nullptr, cls.hInstance, nullptr);
    if (!window) return 2;
    printf("%llu %lu %lu\n", reinterpret_cast<unsigned long long>(window),
           GetCurrentProcessId(), GetCurrentThreadId());
    fflush(stdout);
    MSG message;
    while (GetMessageW(&message, nullptr, 0, 0) > 0) {
        TranslateMessage(&message);
        DispatchMessageW(&message);
    }
    return 0;
}
