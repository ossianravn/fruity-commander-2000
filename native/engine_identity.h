#pragma once
#include <windows.h>
bool QualifiedEngine(HMODULE engine);
bool QualifiedModule(HMODULE module, const BYTE* expected);
