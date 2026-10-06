// Narrow Win32 IPC client: no resident process or Python/.NET/PowerShell startup.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <string>
#include <vector>

static std::wstring ReadString(const std::wstring& json, const wchar_t* key) {
    size_t i = json.find(std::wstring(L"\"") + key + L"\"");
    if (i == std::wstring::npos) return {};
    i = json.find(L':', i);
    if (i == std::wstring::npos) return {};
    ++i;
    while (i < json.size() && (json[i] == L' ' || json[i] == L'\t')) ++i;
    if (i >= json.size() || json[i++] != L'"') return {};
    std::wstring value;
    while (i < json.size()) {
        wchar_t c = json[i++];
        if (c == L'"') return value;
        if (c != L'\\') { value += c; continue; }
        if (i >= json.size()) return {};
        c = json[i++];
        switch (c) {
        case L'"': case L'\\': case L'/': value += c; break;
        case L'b': value += L'\b'; break;
        case L'f': value += L'\f'; break;
        case L'n': value += L'\n'; break;
        case L'r': value += L'\r'; break;
        case L't': value += L'\t'; break;
        case L'u': {
            if (i + 4 > json.size()) return {};
            unsigned code = 0;
            for (unsigned n = 0; n < 4; ++n) {
                wchar_t hex = json[i++];
                unsigned digit = hex >= L'0' && hex <= L'9' ? hex-L'0' :
                    hex >= L'a' && hex <= L'f' ? hex-L'a'+10 :
                    hex >= L'A' && hex <= L'F' ? hex-L'A'+10 : 16;
                if (digit == 16) return {};
                code = code * 16 + digit;
            }
            // JSON surrogate pairs remain the Windows UTF-16 surrogate pair.
            value += static_cast<wchar_t>(code); break;
        }
        default: return {};
        }
    }
    return {};
}

int WINAPI wWinMain(HINSTANCE, HINSTANCE, PWSTR, int) {
    wchar_t module[32768];
    DWORD count = GetModuleFileNameW(nullptr, module, 32768);
    if (!count || count >= 32768) return 1;
    std::wstring root(module, count);
    root.resize(root.find_last_of(L"\\/") + 1);
    HANDLE file = CreateFileW((root+L"runtime.json").c_str(), GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, nullptr, OPEN_EXISTING, 0, nullptr);
    if (file == INVALID_HANDLE_VALUE) return 1;
    char raw[16384]; DWORD bytes = 0;
    BOOL read = ReadFile(file, raw, sizeof(raw), &bytes, nullptr);
    CloseHandle(file);
    if (!read || !bytes || bytes == sizeof(raw)) return 1;
    int length = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, raw, bytes, nullptr, 0);
    if (length <= 0) return 1;
    std::wstring json(length, L'\0');
    MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, raw, bytes, &json[0], length);
    std::wstring name=ReadString(json,L"pipe"), python=ReadString(json,L"python"), script=ReadString(json,L"script");
    if (name.empty() || python.empty() || script.empty()) return 1;
    std::wstring path=L"\\\\.\\pipe\\"+name;
    HANDLE pipe=CreateFileW(path.c_str(),GENERIC_READ|GENERIC_WRITE,0,nullptr,OPEN_EXISTING,0,nullptr);
    if (pipe==INVALID_HANDLE_VALUE && GetLastError()==ERROR_PIPE_BUSY && WaitNamedPipeW(path.c_str(),150))
        pipe=CreateFileW(path.c_str(),GENERIC_READ|GENERIC_WRITE,0,nullptr,OPEN_EXISTING,0,nullptr);
    if (pipe!=INVALID_HANDLE_VALUE) {
        const char message[]="{\"command\":\"toggle\",\"reply\":false}\n";
        DWORD written=0;
        BOOL ok=WriteFile(pipe,message,sizeof(message)-1,&written,nullptr);
        CloseHandle(pipe);
        if (ok && written==sizeof(message)-1) return 0;
    }
    // Existing Python host lock and watchdog arbitrate recovery; never duplicate.
    if (python.find(L'"')!=std::wstring::npos || script.find(L'"')!=std::wstring::npos) return 1;
    std::wstring command=L"\""+python+L"\" \""+script+L"\" --toggle";
    STARTUPINFOW start={sizeof(start)}; PROCESS_INFORMATION process={};
    start.dwFlags=STARTF_USESHOWWINDOW;start.wShowWindow=SW_HIDE;
    BOOL ok=CreateProcessW(python.c_str(),&command[0],nullptr,nullptr,FALSE,
        CREATE_NO_WINDOW,nullptr,root.c_str(),&start,&process);
    if (ok) { CloseHandle(process.hThread);CloseHandle(process.hProcess); }
    return ok ? 0 : 1;
}
