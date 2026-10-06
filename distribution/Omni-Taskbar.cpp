// A small GUI-subsystem entry point. All runtimes are installed alongside it.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <shellapi.h>
#include <string>
int WINAPI wWinMain(HINSTANCE,HINSTANCE,PWSTR,int) {
 wchar_t file[32768];GetModuleFileNameW(nullptr,file,32768);
 std::wstring root(file);root.resize(root.find_last_of(L"\\/"));
 SetEnvironmentVariableW(L"OMNI_PROGRAM_ROOT",root.c_str());
 int argc=0;LPWSTR* args=CommandLineToArgvW(GetCommandLineW(),&argc);
 std::wstring command=argc>1?args[1]:L"--start";
 // Python's installed layout resolver loads the owning user directory marker.
 std::wstring exe=root+L"\\runtime\\python\\pythonw.exe";
 std::wstring script=root+L"\\shell-updater\\installed_app.py";
 std::wstring line=L"\""+exe+L"\" \""+script+L"\" "+command;
 for(int i=2;i<argc;i++)line+=L" \""+std::wstring(args[i])+L"\"";
 LocalFree(args);STARTUPINFOW si{};si.cb=sizeof(si);PROCESS_INFORMATION pi{};
 BOOL ok=CreateProcessW(exe.c_str(),line.data(),nullptr,nullptr,FALSE,CREATE_NO_WINDOW,nullptr,root.c_str(),&si,&pi);
 if(!ok){MessageBoxW(nullptr,L"Omni Taskbar runtime is missing. Run the installer to repair it.",L"Omni Taskbar",MB_OK|MB_ICONERROR);return 1;}
 CloseHandle(pi.hThread);CloseHandle(pi.hProcess);return 0;
}
