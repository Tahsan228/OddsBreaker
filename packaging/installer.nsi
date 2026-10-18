; OddsBreaker installer (NSIS 3). Built by packaging/build.py, which passes:
;   VERSION, SRCDIR (the PyInstaller folder build), OUTFILE, ASSETS, LICENSEFILE
; Installs for the current user only, so no admin rights are needed.

Unicode true
; The app is 64-bit, so the installer is too.
Target amd64-unicode
!include "MUI2.nsh"
!include "FileFunc.nsh"

!ifndef VERSION
  !define VERSION "1.0.0"
!endif
!ifndef SRCDIR
  !define SRCDIR "..\dist\OddsBreaker"
!endif
!ifndef OUTFILE
  !define OUTFILE "..\release\OddsBreaker-${VERSION}-Setup.exe"
!endif
!ifndef ASSETS
  !define ASSETS "..\build\assets"
!endif
!ifndef LICENSEFILE
  !define LICENSEFILE "..\LICENSE"
!endif

!define APPNAME "OddsBreaker"
!define PUBLISHER "Tahsan"
!define WEBSITE "https://github.com/Tahsan228/ShinyHunt"
!define UNINSTKEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}"

Name "${APPNAME}"
OutFile "${OUTFILE}"
InstallDir "$LOCALAPPDATA\Programs\${APPNAME}"
InstallDirRegKey HKCU "Software\${APPNAME}" "InstallDir"
RequestExecutionLevel user
SetCompressor /SOLID lzma
BrandingText "${APPNAME} ${VERSION} by ${PUBLISHER}"
ShowInstDetails nevershow
ShowUninstDetails nevershow

VIProductVersion "${VERSION}.0"
VIAddVersionKey "ProductName" "${APPNAME}"
VIAddVersionKey "CompanyName" "${PUBLISHER}"
VIAddVersionKey "LegalCopyright" "Copyright (c) 2026 ${PUBLISHER}"
VIAddVersionKey "FileDescription" "${APPNAME} installer"
VIAddVersionKey "FileVersion" "${VERSION}"
VIAddVersionKey "ProductVersion" "${VERSION}"

!define MUI_ICON "${ASSETS}\icon.ico"
!define MUI_UNICON "${ASSETS}\icon.ico"
!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_RIGHT
!define MUI_HEADERIMAGE_BITMAP "${ASSETS}\header.bmp"
!define MUI_HEADERIMAGE_UNBITMAP "${ASSETS}\header.bmp"
!define MUI_WELCOMEFINISHPAGE_BITMAP "${ASSETS}\wizard.bmp"
!define MUI_UNWELCOMEFINISHPAGE_BITMAP "${ASSETS}\wizard.bmp"
!define MUI_ABORTWARNING

!define MUI_WELCOMEPAGE_TITLE "Welcome to ${APPNAME} ${VERSION}"
!define MUI_WELCOMEPAGE_TEXT "The automatic shiny hunter for any emulator.$\r$\n$\r$\n${APPNAME} plays the reset loop for you, looks at every encounter and stops with a jingle the moment a shiny shows up.$\r$\n$\r$\nIt installs just for you, so it doesn't need admin rights. Your hunts are kept in %APPDATA%\${APPNAME}.$\r$\n$\r$\nMade by ${PUBLISHER}."
!define MUI_FINISHPAGE_RUN "$INSTDIR\${APPNAME}.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Start ${APPNAME} now"
!define MUI_FINISHPAGE_LINK "Guide and updates on GitHub"
!define MUI_FINISHPAGE_LINK_LOCATION "${WEBSITE}"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "${LICENSEFILE}"
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

Function .onInit
  ; A running copy would lock its files.
  FindWindow $0 "TkTopLevel" "${APPNAME}"
  StrCmp $0 0 done
    MessageBox MB_OKCANCEL|MB_ICONINFORMATION "${APPNAME} is running. Close it (your hunt is saved automatically), then click OK." IDOK done
    Abort
  done:
FunctionEnd

Section "${APPNAME}" SecMain
  SectionIn RO
  SetOutPath "$INSTDIR"
  ; clear out files from an older version first
  RMDir /r "$INSTDIR\_internal"
  File /r "${SRCDIR}\*"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateShortcut "$SMPROGRAMS\${APPNAME}.lnk" "$INSTDIR\${APPNAME}.exe" "" "$INSTDIR\${APPNAME}.exe" 0
  WriteRegStr HKCU "Software\${APPNAME}" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "${UNINSTKEY}" "DisplayName" "${APPNAME}"
  WriteRegStr HKCU "${UNINSTKEY}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "${UNINSTKEY}" "Publisher" "${PUBLISHER}"
  WriteRegStr HKCU "${UNINSTKEY}" "DisplayIcon" "$INSTDIR\${APPNAME}.exe"
  WriteRegStr HKCU "${UNINSTKEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${UNINSTKEY}" "URLInfoAbout" "${WEBSITE}"
  WriteRegStr HKCU "${UNINSTKEY}" "HelpLink" "${WEBSITE}"
  WriteRegStr HKCU "${UNINSTKEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegStr HKCU "${UNINSTKEY}" "QuietUninstallString" '"$INSTDIR\Uninstall.exe" /S'
  WriteRegDWORD HKCU "${UNINSTKEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINSTKEY}" "NoRepair" 1
  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  IntFmt $0 "0x%08X" $0
  WriteRegDWORD HKCU "${UNINSTKEY}" "EstimatedSize" "$0"
SectionEnd

Section "Desktop shortcut" SecDesktop
  CreateShortcut "$DESKTOP\${APPNAME}.lnk" "$INSTDIR\${APPNAME}.exe" "" "$INSTDIR\${APPNAME}.exe" 0
SectionEnd

LangString DESC_Main ${LANG_ENGLISH} "The app itself."
LangString DESC_Desktop ${LANG_ENGLISH} "Put a ${APPNAME} shortcut on your desktop."
!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SecMain} $(DESC_Main)
  !insertmacro MUI_DESCRIPTION_TEXT ${SecDesktop} $(DESC_Desktop)
!insertmacro MUI_FUNCTION_DESCRIPTION_END

Section "Uninstall"
  Delete "$DESKTOP\${APPNAME}.lnk"
  Delete "$SMPROGRAMS\${APPNAME}.lnk"
  RMDir /r "$INSTDIR\_internal"
  Delete "$INSTDIR\${APPNAME}.exe"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  DeleteRegKey HKCU "${UNINSTKEY}"
  DeleteRegKey HKCU "Software\${APPNAME}"
  ; Your hunts in %APPDATA%\OddsBreaker are left alone on purpose.
SectionEnd
