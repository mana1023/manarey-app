!include "MUI2.nsh"
!include "WinMessages.nsh"

!define APP_NAME "Manarey"
!define APP_VERSION "1.1.0"
!define APP_PUBLISHER "Manarey"
!define APP_EXE "Manarey.exe"
!define ROOT_DIR "C:\Users\USUARIO\Desktop\Manarey"
!define VCRUNTIME "${ROOT_DIR}\\Oficial\\third_party\\vc_redist.x64.exe"

Name "${APP_NAME}"
OutFile "${ROOT_DIR}\\DESCARGABLE\\Manarey-Setup-${APP_VERSION}.exe"
InstallDir "$PROGRAMFILES64\\Manarey"
InstallDirRegKey HKLM "Software\\${APP_NAME}" "Install_Dir"
RequestExecutionLevel admin

ShowInstDetails show
ShowUninstDetails show
!define MUI_ABORTWARNING

; En modo silencioso (/S) omitir todas las páginas MUI
!ifdef NSIS_SILENT
  ; no pages
!else
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!endif

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

!insertmacro MUI_LANGUAGE "Spanish"

Section "Manarey" SEC01
  SetRegView 64
  ; Esperar a que el proceso anterior (Manarey.exe) haya cerrado antes de
  ; intentar sobreescribir el ejecutable. Sin esta pausa, Windows bloquea
  ; el exe y NSIS lo programa para "reemplazar al reiniciar" en vez de
  ; instalarlo ahora.
  Sleep 2000
  SetOutPath "$INSTDIR"
  File /r "${ROOT_DIR}\\dist\\Manarey\\*"
  File /nonfatal "${ROOT_DIR}\\config.json"
  File /nonfatal "${ROOT_DIR}\\.dburl"

  ; Instalar VC++ Runtime si está disponible (evita crashes de Qt)
  IfFileExists "${VCRUNTIME}" 0 +4
    SetOutPath "$TEMP"
    File /oname=$TEMP\\vc_redist.x64.exe "${VCRUNTIME}"
    ExecWait '"$TEMP\\vc_redist.x64.exe" /install /quiet /norestart'
    Delete "$TEMP\\vc_redist.x64.exe"

  WriteUninstaller "$INSTDIR\\Uninstall.exe"

  CreateDirectory "$SMPROGRAMS\\${APP_NAME}"
  CreateShortCut "$SMPROGRAMS\\${APP_NAME}\\${APP_NAME}.lnk" "$INSTDIR\\${APP_EXE}"
  CreateShortCut "$DESKTOP\\${APP_NAME}.lnk" "$INSTDIR\\${APP_EXE}"

  WriteRegStr HKLM "Software\\${APP_NAME}" "Install_Dir" "$INSTDIR"
  WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${APP_NAME}" "DisplayName" "${APP_NAME}"
  WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${APP_NAME}" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${APP_NAME}" "Publisher" "${APP_PUBLISHER}"
  WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${APP_NAME}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${APP_NAME}" "UninstallString" "$INSTDIR\\Uninstall.exe"

  ; Escribir marcador de instalación exitosa (Python lo detecta)
  FileOpen $0 "$TEMP\manarey_install_ok.txt" w
  FileWrite $0 "${APP_VERSION}"
  FileClose $0

  ; Relanzar la app automáticamente después de instalar
  Exec '"$INSTDIR\\${APP_EXE}"'

SectionEnd

Section "Uninstall"
  SetRegView 64
  Delete "$DESKTOP\\${APP_NAME}.lnk"
  Delete "$SMPROGRAMS\\${APP_NAME}\\${APP_NAME}.lnk"
  RMDir "$SMPROGRAMS\\${APP_NAME}"

  Delete "$INSTDIR\\config.json"
  Delete "$INSTDIR\\.dburl"
  Delete "$INSTDIR\\Uninstall.exe"
  RMDir /r "$INSTDIR"

  DeleteRegKey HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${APP_NAME}"
  DeleteRegKey HKLM "Software\\${APP_NAME}"
SectionEnd
















































































