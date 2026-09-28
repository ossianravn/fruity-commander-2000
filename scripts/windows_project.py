"""Read current project identity from the qualified Windows engine, without injection.

The project-path reference was located using FruityLink's ProjectPath signature
(MIT SDK, c0a76bc5779728084a4165b08314a8575d5e781e), then independently observed on
26.1.6.5639. Addresses below are RVAs in that exact binary, not another build.
"""

import ctypes
import hashlib
import os
import struct
from ctypes import wintypes as w
from pathlib import Path

from scripts.windows_shortcut import _windows_api, _find_window


ENGINE_SHA256 = "bc3637c3e41694c820865e757d88a42bdc15b6db4011582a2ef8f4d1b05a2d95"
PATH_REFERENCE_RVA = 0xD86424
PATH_POINTER_RVA = 0x12C0C90


def path_reference(image):
    """Verify the qualified disk image and return its exact reference instruction."""
    if hashlib.sha256(image).hexdigest() != ENGINE_SHA256:
        raise ValueError("Current-project path access is not qualified for this FL engine binary")
    pe = struct.unpack_from("<I", image, 60)[0]
    count = struct.unpack_from("<H", image, pe + 6)[0]
    optional_size = struct.unpack_from("<H", image, pe + 20)[0]
    for index in range(count):
        offset = pe + 24 + optional_size + index * 40
        size, rva, raw_size, raw = struct.unpack_from("<IIII", image, offset + 8)
        if rva <= PATH_REFERENCE_RVA < rva + min(size, raw_size):
            start = raw + PATH_REFERENCE_RVA - rva
            instruction = image[start:start + 7]
            destination = PATH_REFERENCE_RVA + 7 + struct.unpack_from("<i", instruction, 3)[0]
            if instruction[:3] != b"\x48\x8b\x15" or destination != PATH_POINTER_RVA:
                raise ValueError("Qualified project-path instruction does not match its target")
            return instruction
    raise ValueError("Qualified project-path instruction is outside the engine sections")


class ProjectReader:
    def __enter__(self):
        if os.name != "nt":
            raise OSError("Native project-file identity is currently qualified on Windows only")
        self.user, self.kernel, callback = _windows_api()
        self.window = _find_window(self.user, self.kernel, callback)
        pid = w.DWORD()
        self.user.GetWindowThreadProcessId(self.window, ctypes.byref(pid))
        self.pid = pid.value
        self.kernel.ReadProcessMemory.argtypes = [w.HANDLE, ctypes.c_void_p,
            ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
        self.kernel.ReadProcessMemory.restype = w.BOOL
        self.process = self.kernel.OpenProcess(0x410, False, self.pid)
        if not self.process:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            self.base, self.engine = self._engine_module()
            instruction = path_reference(self.engine.read_bytes())
            if self.read(self.base + PATH_REFERENCE_RVA, 7) != instruction:
                raise ValueError("Loaded FL engine differs from the qualified disk image")
            return self
        except BaseException:
            self.kernel.CloseHandle(self.process)
            raise

    def __exit__(self, *unused):
        self.kernel.CloseHandle(self.process)

    def _engine_module(self):
        ps = ctypes.WinDLL("psapi", use_last_error=True)
        ps.EnumProcessModules.argtypes = [w.HANDLE, ctypes.POINTER(w.HMODULE),
                                         w.DWORD, ctypes.POINTER(w.DWORD)]
        ps.EnumProcessModules.restype = w.BOOL
        ps.GetModuleFileNameExW.argtypes = [w.HANDLE, w.HMODULE, w.LPWSTR, w.DWORD]
        ps.GetModuleFileNameExW.restype = w.DWORD
        needed = w.DWORD()
        if not ps.EnumProcessModules(self.process, None, 0, ctypes.byref(needed)):
            raise ctypes.WinError(ctypes.get_last_error())
        modules = (w.HMODULE * (needed.value // ctypes.sizeof(w.HMODULE)))()
        if not ps.EnumProcessModules(self.process, modules, ctypes.sizeof(modules),
                                     ctypes.byref(needed)):
            raise ctypes.WinError(ctypes.get_last_error())
        if needed.value > ctypes.sizeof(modules):
            raise ValueError("FL module inventory changed during project-file inspection")
        for module in modules:
            path = ctypes.create_unicode_buffer(32768)
            if not ps.GetModuleFileNameExW(self.process, module, path, len(path)):
                raise ctypes.WinError(ctypes.get_last_error())
            if Path(path.value).name.lower() == "flengine_x64.dll":
                return module, Path(path.value)
        raise ValueError("FL engine module was not found in the identified FL process")

    def read(self, address, size):
        buffer = ctypes.create_string_buffer(size)
        actual = ctypes.c_size_t()
        if not self.kernel.ReadProcessMemory(self.process, address, buffer, size,
                                              ctypes.byref(actual)):
            raise ctypes.WinError(ctypes.get_last_error())
        if actual.value != size:
            raise OSError("FL project identity returned an incomplete memory read")
        return buffer.raw

    def identity(self):
        address = self.base + PATH_POINTER_RVA
        pointer_bytes = self.read(address, 8)
        pointer = struct.unpack("<Q", pointer_bytes)[0]
        value = ""
        if pointer:
            header = self.read(pointer - 12, 12)
            codepage, element_size, _, length = struct.unpack("<HHiI", header)
            # Windows extended-length paths are at most 32,767 UTF-16 code units.
            if codepage != 1200 or element_size != 2 or length > 32767:
                raise ValueError("FL project-path string has an unexpected representation")
            data = self.read(pointer, (length + 1) * 2)
            if data[-2:] != b"\0\0" or self.read(pointer - 12, 12) != header:
                raise ValueError("FL project-path string changed during inspection")
            value = data[:-2].decode("utf-16-le")
        if self.read(address, 8) != pointer_bytes:
            raise ValueError("FL project identity changed during inspection")
        return {"process_id": self.pid, "path": value or None,
                "engine_sha256": ENGINE_SHA256,
                "identity_basis": "qualified_native_project_path_read"}


def current_project_file():
    with ProjectReader() as reader:
        return reader.identity()
