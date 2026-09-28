#include "host_access.h"
#include "constant_path.h"

// FruityLink supplied the direct FLP writer and project-path techniques. These
// addresses and path/name assignments were traced on our qualified binary.
bool SaveProjectAs(Request& request) {
    const auto base = HostBase(request);
    if (!base) return false;
    const ConstantPath path(request.path);
    if (path.length < 4 || path.length >= 32768
        || _wcsicmp(path.text + path.length - 4, L".flp"))
        return Fail(request, L"Save As requires an FLP destination");
    const auto project = Read<uintptr_t>(base + 0x12C0C00);
    if (!project) return Fail(request, L"FL project object is unavailable");
    request.stage = 1;
    // Use FL's self-contained Save Copy writer, avoiding the normal wrapper's
    // temporary-file move. The caller separately verifies the completed file.
    using Write = uint8_t (*)(const wchar_t*, uint8_t);
    if (!reinterpret_cast<Write>(base + 0xDDB8D0)(path.text, 0))
        return Fail(request, L"FL did not write the requested project file");
    request.stage = 2;
    using SetPath = void (*)(uintptr_t, const wchar_t*, const wchar_t*, uint8_t);
    reinterpret_cast<SetPath>(base + 0xDD8E40)(project, path.text, path.text, 1);
    request.stage = 3;
    return true;  // The MCP owner independently verifies path and complete FLP.
}
