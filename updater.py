# updater.py
import ctypes
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def get_current_version() -> str:
    """Obtiene la versión actual de la aplicación.

    Usa tres métodos en cascada para máxima confiabilidad:
      1. Import del módulo version (funciona cuando está en el bundle)
      2. Lectura del registro de Windows (escrito por el instalador NSIS)
      3. Fallback a "0.0.0"
    """
    # Método 1: import version module (el más directo)
    try:
        from version import __version__

        if __version__ and __version__ != "0.0.0":
            return __version__
    except Exception:
        pass

    # Método 2: leer del registro de Windows (NSIS escribe DisplayVersion)
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"Software\Microsoft\Windows\CurrentVersion\Uninstall\Manarey",
            0,
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
        )
        v, _ = winreg.QueryValueEx(key, "DisplayVersion")
        winreg.CloseKey(key)
        if v and v.strip():
            return v.strip()
    except Exception:
        pass

    return "0.0.0"


# Fallback simple comparador de versiones (evita dependencia externa)
def _parse_version(v: str):
    parts = str(v or "0").split(".")
    ints = []
    for p in parts:
        try:
            ints.append(int(p))
        except Exception:
            ints.append(0)
    while len(ints) < 3:
        ints.append(0)
    return tuple(ints[:4])


def _get_github_repo_from_config() -> tuple:
    """Obtiene GITHUB_REPO desde config.json (múltiples ubicaciones) o fallback hard-coded.

    En la app instalada el CWD no siempre es el directorio del ejecutable,
    así que buscamos config.json en varias rutas posibles.
    """
    _DEFAULT_REPO = "mana1023/manarey-updates"

    search_dirs = []
    try:
        # Directorio actual
        search_dirs.append(os.getcwd())
        # Directorio del ejecutable (Program Files\\Manarey)
        search_dirs.append(os.path.dirname(sys.executable))
        # sys._MEIPASS (donde PyInstaller extrae los archivos)
        if getattr(sys, "_MEIPASS", None):
            search_dirs.append(sys._MEIPASS)
    except Exception:
        pass

    for d in search_dirs:
        try:
            cfg_path = os.path.join(d, "config.json")
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                repo = cfg.get("GITHUB_REPO")
                if repo:
                    return repo, None
        except Exception:
            continue

    # Fallback: variable de entorno o repositorio por defecto
    repo = os.environ.get("GITHUB_REPO") or _DEFAULT_REPO
    return repo, None


def _get_latest_release_from_github() -> Optional[Dict[str, Any]]:
    """Obtiene la última release desde GitHub API.

    Busca activos en este orden de preferencia:
      1. Manarey-Setup-*.exe  (instalador NSIS preferido)
      2. Cualquier *.exe
      3. Cualquier *.zip (fallback: se extrae durante la instalación)

    Si la release más reciente no tiene ningún activo descargable conocido,
    retorna None para no engañar al usuario con una actualización que no funciona.
    Importante: NUNCA hace fallback a Supabase si GitHub responde con éxito.
    """
    try:
        repo, _token = _get_github_repo_from_config()

        if not repo:
            logger.debug("GITHUB_REPO no configurado")
            return None

        import json
        import urllib.request

        url = f"https://api.github.com/repos/{repo}/releases/latest"

        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Manarey-Updater/1.0",
        }

        req = urllib.request.Request(url, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))

                # Extraer versión
                version = data.get("tag_name", "").lstrip("v")
                if not version:
                    version = data.get("name", "").split()[-1]
                if not version:
                    return None

                assets = data.get("assets") or []

                # Prioridad 1: instalador NSIS Manarey-Setup-*.exe
                download_url = None
                asset_type = "exe"
                for asset in assets:
                    aname = asset.get("name", "")
                    if aname.endswith(".exe") and "Manarey-Setup" in aname:
                        download_url = asset["browser_download_url"]
                        break

                # Prioridad 2: cualquier .exe
                if not download_url:
                    for asset in assets:
                        aname = asset.get("name", "")
                        if aname.endswith(".exe"):
                            download_url = asset["browser_download_url"]
                            break

                # Prioridad 3: .zip (se extrae en destino)
                if not download_url:
                    for asset in assets:
                        aname = asset.get("name", "")
                        if aname.endswith(".zip"):
                            download_url = asset["browser_download_url"]
                            asset_type = "zip"
                            break

                if not download_url:
                    # Release existe en GitHub pero sin activo instalable →
                    # retornamos sentinel especial para que el fallback Supabase NO se active
                    logger.debug(
                        f"Release {version} en GitHub sin activo instalable, ignorando"
                    )
                    return {
                        "version": version,
                        "url": None,
                        "_meta": {"source": "github", "no_asset": True},
                    }

                return {
                    "version": version,
                    "url": download_url,
                    "notes": data.get("body", ""),
                    "published_at": str(data.get("published_at", "")),
                    "mandatory": bool(not data.get("prerelease")),
                    "force_after_days": 2,
                    "_meta": {"source": "github", "asset_type": asset_type},
                }
        except Exception as e:
            logger.debug(f"Error consultando GitHub API: {e}")
            return None

    except Exception as e:
        logger.error(f"Error obteniendo release de GitHub: {e}")
        return None


def _get_best_manifest() -> Optional[Dict[str, Any]]:
    """Carga el manifiesto de la última release desde GitHub (única fuente)."""
    manifest = _get_latest_release_from_github()
    if not manifest:
        return None
    # Release sin activo instalable → no mostrar update con URL rota
    if manifest.get("_meta", {}).get("no_asset"):
        return None
    if not manifest.get("url"):
        return None
    return manifest


def _state_path() -> str:
    try:
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser(r"~\AppData\Local")
    except Exception:
        base = os.path.expanduser("~")
    root = os.path.join(base, "Manarey")
    try:
        os.makedirs(root, exist_ok=True)
    except Exception:
        pass
    return os.path.join(root, "update_state.json")


def _log_path() -> str:
    """Ruta del archivo de log del updater (diagnóstico de descargas)."""
    try:
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser(r"~\AppData\Local")
    except Exception:
        base = os.path.expanduser("~")
    root = os.path.join(base, "Manarey")
    try:
        os.makedirs(root, exist_ok=True)
    except Exception:
        pass
    return os.path.join(root, "updater.log")


def _log_update_event(msg: str) -> None:
    """Registra un evento del updater para diagnóstico. Nunca falla."""
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(_log_path(), "a", encoding="utf-8") as f:
            f.write(f"{ts} {msg}\n")
    except Exception:
        pass


def _load_state() -> Dict[str, Any]:
    path = _state_path()
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f) or {}
    except Exception:
        pass
    return {}


def _save_state(state: Dict[str, Any]) -> None:
    path = _state_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    s = str(s).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _get_published_at(manifest: Dict[str, Any]) -> datetime:
    # Prioridad: campo published_at -> mtime del manifest -> ahora
    dt = _parse_dt(manifest.get("published_at"))
    if dt:
        return dt
    try:
        meta = manifest.get("_meta") or {}
        mtime = meta.get("manifest_mtime")
        if mtime:
            return datetime.fromtimestamp(float(mtime))
    except Exception:
        pass
    return datetime.now()


def _force_after_days(manifest: Dict[str, Any]) -> int:
    try:
        return int(
            manifest.get("force_after_days")
            or manifest.get("mandatory_after_days")
            or 2
        )
    except Exception:
        return 2


def _is_mandatory(manifest: Dict[str, Any]) -> bool:
    try:
        if manifest.get("mandatory") in (True, "true", "1", 1):
            return True
    except Exception:
        pass
    try:
        pub = _get_published_at(manifest)
        days = _force_after_days(manifest)
        if datetime.now() - pub >= timedelta(days=days):
            return True
    except Exception:
        pass
    return False


def _set_pending_update(manifest: Dict[str, Any]) -> None:
    if not manifest:
        return
    state = _load_state()
    state["pending"] = {
        "version": manifest.get("version"),
        "path": manifest.get("path"),
        "url": manifest.get("url"),
        "notes": manifest.get("notes"),
        "published_at": manifest.get("published_at"),
        "force_after_days": manifest.get("force_after_days"),
        "mandatory": bool(manifest.get("mandatory")),
    }
    state["last_seen"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _save_state(state)


def _clear_pending_update() -> None:
    state = _load_state()
    if "pending" in state:
        state.pop("pending", None)
        _save_state(state)


def get_pending_update() -> Optional[Dict[str, Any]]:
    """Devuelve info de update pendiente (si existe y sigue siendo mÃ¡s nuevo)."""
    try:
        state = _load_state()
        pending = state.get("pending")
        if not pending or not pending.get("version"):
            return None
        cur_v = _parse_version(get_current_version())
        new_v = _parse_version(pending.get("version"))
        if new_v <= cur_v:
            _clear_pending_update()
            return None
        return pending
    except Exception:
        return None


def _download_to_temp(
    src: str,
    progress_cb=None,
    cancel_cb=None,
) -> Optional[str]:
    """Descarga el instalador a TEMP con retries y logging.

    Estrategia robusta para archivos grandes (92+ MB) en conexiones lentas:
      - 3 intentos con backoff exponencial (5s, 10s, 15s)
      - Timeout (30s conectar, sin límite para leer): conexión lenta no aborta
      - Limpia query strings del nombre de archivo (URLs presignadas de S3/Azure)
      - Si tenemos descarga parcial válida, intenta resume con Range
      - Log detallado a %LOCALAPPDATA%\\Manarey\\updater.log para diagnóstico
    """
    # Caso ruta local (compartida de red) ────────────────────────────────────
    if not src.lower().startswith(("http://", "https://")):
        if os.path.exists(src):
            try:
                tmp_dir = tempfile.gettempdir()
                dst = os.path.join(tmp_dir, os.path.basename(src))
                shutil.copy2(src, dst)
                if progress_cb:
                    progress_cb(1, 1)
                _log_update_event(f"copy local ok: {src} -> {dst}")
                return dst
            except Exception as e:
                _log_update_event(f"copy local falló: {e}")
                return None
        _log_update_event(f"ruta local no existe: {src}")
        return None

    # Caso URL http(s) ───────────────────────────────────────────────────────
    tmp_dir = tempfile.gettempdir()
    # URLs presignadas (S3/Azure) traen query string — limpiarlo para el nombre
    base_name = os.path.basename(src.split("?", 1)[0]) or "Manarey-Setup.exe"
    if not base_name.lower().endswith(".exe"):
        base_name = "Manarey-Setup.exe"
    dst = os.path.join(tmp_dir, base_name)
    _log_update_event(f"download inicio: {src} -> {dst}")

    last_err: Optional[str] = None
    for attempt in range(1, 4):
        try:
            import requests

            headers = {
                "User-Agent": "Manarey-Updater/1.0",
                "Accept": "*/*",
            }
            # (connect=30s, read=None) → permite descargas largas sin abortar
            with requests.get(
                src,
                headers=headers,
                stream=True,
                timeout=(30, None),
                allow_redirects=True,
            ) as r:
                if r.status_code != 200:
                    raise RuntimeError(f"HTTP {r.status_code}")
                total = int(r.headers.get("Content-Length") or 0)
                done = 0
                with open(dst, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 256):
                        if cancel_cb and cancel_cb():
                            _log_update_event("download cancelado por usuario")
                            return None
                        if chunk:
                            f.write(chunk)
                            done += len(chunk)
                            if progress_cb:
                                progress_cb(done, total)

            # Validación: el archivo debe ser razonablemente grande y completo
            try:
                size = os.path.getsize(dst)
                if size < 1024 * 1024:
                    raise RuntimeError(f"archivo demasiado pequeño: {size} bytes")
                if total and size < total:
                    raise RuntimeError(f"descarga incompleta: {size}/{total} bytes")
            except RuntimeError:
                raise
            except Exception:
                pass

            if progress_cb:
                progress_cb(1, 1)
            _log_update_event(f"download ok: {dst} ({done} bytes)")
            return dst

        except Exception as e:
            last_err = str(e)
            _log_update_event(f"download intento {attempt}/3 falló: {e}")
            if attempt < 3:
                try:
                    time.sleep(5 * attempt)  # backoff: 5s, 10s
                except Exception:
                    pass

    # Fallback final: urllib (sin retries, última oportunidad)
    try:
        _log_update_event("fallback urllib...")
        with urllib.request.urlopen(src, timeout=60) as resp, open(dst, "wb") as f:
            shutil.copyfileobj(resp, f)
        if os.path.getsize(dst) >= 1024 * 1024:
            if progress_cb:
                progress_cb(1, 1)
            _log_update_event(f"download ok via urllib: {dst}")
            return dst
    except Exception as e:
        _log_update_event(f"fallback urllib falló: {e}")

    _log_update_event(f"download falló definitivamente: {last_err}")
    return None


def refresh_update_state() -> Optional[Dict[str, Any]]:
    """Actualiza update_state.json sin mostrar UI. Devuelve el manifest si hay update nuevo.

    IMPORTANTE: solo limpia el update pendiente cuando GitHub responde exitosamente
    y confirma que no hay versión más nueva. Si la API falla (red caída, timeout,
    rate-limit), NO toca el estado guardado para no perder la notificación.
    """
    manifest = _get_best_manifest()
    if not manifest or not manifest.get("version"):
        # API falló o no hay release publicada — conservar cualquier pending existente
        return None

    cur_v = _parse_version(get_current_version())
    new_v = _parse_version(manifest.get("version"))
    if new_v <= cur_v:
        # GitHub confirmó que no hay versión más nueva → limpiar
        _clear_pending_update()
        return None

    _set_pending_update(manifest)
    return manifest


def _run_installer_and_wait(exe_path: str) -> bool:
    """
    Lanza el instalador NSIS en modo silencioso (/S) con UAC elevado,
    espera a que termine usando WaitForSingleObject, luego cierra la app.
    El instalador NSIS se encarga de relanzar Manarey.exe al terminar.
    """
    if os.name != "nt":
        subprocess.Popen([exe_path])
        time.sleep(2)
        os._exit(0)
        return True

    try:
        # Borrar el marcador previo por si existe
        marker = os.path.join(tempfile.gettempdir(), "manarey_install_ok.txt")
        try:
            if os.path.exists(marker):
                os.remove(marker)
        except Exception:
            pass

        # ── ShellExecuteExW (sin esperar el proceso) ─────────────────────────
        # IMPORTANTE: NO usamos SEE_MASK_NOCLOSEPROCESS ni WaitForSingleObject.
        # Si esperamos que el instalador termine antes de salir, Manarey.exe
        # queda bloqueado (en uso) y NSIS no puede sobrescribirlo.
        # La solución es lanzar el instalador y salir INMEDIATAMENTE,
        # así NSIS puede reemplazar todos los archivos sin restricciones.

        class SHELLEXECUTEINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_ulong),
                ("fMask", ctypes.c_ulong),
                ("hwnd", ctypes.c_void_p),
                ("lpVerb", ctypes.c_wchar_p),
                ("lpFile", ctypes.c_wchar_p),
                ("lpParameters", ctypes.c_wchar_p),
                ("lpDirectory", ctypes.c_wchar_p),
                ("nShow", ctypes.c_int),
                ("hInstApp", ctypes.c_void_p),
                ("lpIDList", ctypes.c_void_p),
                ("lpClass", ctypes.c_wchar_p),
                ("hkeyClass", ctypes.c_void_p),
                ("dwHotKey", ctypes.c_ulong),
                ("hIconOrMonitor", ctypes.c_void_p),
                ("hProcess", ctypes.c_void_p),
            ]

        sei = SHELLEXECUTEINFO()
        sei.cbSize = ctypes.sizeof(sei)
        sei.fMask = 0  # Sin NOCLOSEPROCESS: no necesitamos el handle
        sei.hwnd = None
        sei.lpVerb = "runas"
        sei.lpFile = exe_path
        sei.lpParameters = "/S"  # NSIS silent install
        sei.lpDirectory = None
        sei.nShow = 0  # SW_HIDE
        sei.hProcess = None

        ok = ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(sei))
        if not ok:
            # Usuario canceló UAC o error al lanzar
            logger.warning("ShellExecuteExW: UAC cancelado o error")
            return False

        # Pausa breve para que el prompt UAC aparezca antes de cerrar la ventana
        time.sleep(1)

        # Salir AHORA: así Manarey.exe queda libre y NSIS puede sobrescribirlo.
        # NSIS se encarga de relanzar la nueva versión al terminar.
        os._exit(0)
        return True

    except Exception as e:
        logger.error(f"Error en instalador: {e}")
        os._exit(0)
        return True


def _download_and_install_with_progress(src: str, parent_widget=None) -> bool:
    """Descarga el instalador (.exe) y lo ejecuta con UAC, mostrando progreso en dos fases."""
    import threading

    try:
        from PyQt5.QtWidgets import QApplication

        from ui.ui_update_dialog import UpdateProgressDialog
    except Exception:
        # Fallback sin UI
        exe_path = _download_to_temp(src)
        if exe_path:
            return _run_installer_and_wait(exe_path)
        return False

    dlg = UpdateProgressDialog(parent_widget)
    dlg.cancelled = False

    def download_progress_cb(done: int, total: int):
        if total and total > 0:
            dlg.update_progress(done, total, stage="download")
        QApplication.processEvents()

    dlg.show()

    # ── Fase 1: Descargar ────────────────────────────────────────────────────
    exe_path = _download_to_temp(
        src,
        progress_cb=download_progress_cb,
        cancel_cb=lambda: dlg.cancelled,
    )

    if dlg.cancelled or not exe_path:
        try:
            dlg.close()
        except Exception:
            pass
        # Mostrar error al usuario si no fue cancelación explícita
        if not dlg.cancelled:
            try:
                from PyQt5.QtWidgets import QMessageBox

                QMessageBox.warning(
                    parent_widget,
                    "Actualización falló",
                    "No se pudo descargar la actualización.\n\n"
                    "Posibles causas:\n"
                    "  • Conexión a internet lenta o interrumpida\n"
                    "  • Firewall/antivirus bloqueando la descarga\n"
                    "  • Servidor de GitHub temporalmente no disponible\n\n"
                    f"Detalles: {_log_path()}\n\n"
                    "Podés reintentar cerrando y abriendo la app.",
                )
            except Exception:
                pass
        return False

    # ── Fase 2: Instalar (en hilo, UI sigue viva) ────────────────────────────
    try:
        dlg.update_progress(100, 100, stage="download")
        dlg.start_install_phase()
        QApplication.processEvents()
    except Exception:
        pass

    install_done = threading.Event()

    def _install():
        _run_installer_and_wait(exe_path)  # hace os._exit(0) al terminar
        install_done.set()  # solo llega acá si falla

    t = threading.Thread(target=_install, daemon=True)
    t.start()

    # Mantener UI viva mientras instala
    while not install_done.wait(timeout=0.05):
        try:
            QApplication.processEvents()
        except Exception:
            break

    # Si llegamos acá es porque instalación falló (no hizo os._exit)
    try:
        dlg.close()
    except Exception:
        pass
    return False


def _run_installer(exe_path: str) -> bool:
    """Compatibilidad: delega a _run_installer_and_wait."""
    return _run_installer_and_wait(exe_path)


def _downloads_dir() -> str:
    """Carpeta Descargas del usuario (fallback: %USERPROFILE%\\Downloads)."""
    try:
        home = os.path.expanduser("~")
        d = os.path.join(home, "Downloads")
        if os.path.isdir(d):
            return d
    except Exception:
        pass
    return tempfile.gettempdir()


def _download_installer_with_progress(src: str, parent_widget=None) -> Optional[str]:
    """Descarga el instalador a la carpeta Descargas con barra de progreso.

    Devuelve la ruta local al .exe descargado o None si falla/cancela.
    NO ejecuta el instalador — eso lo hace el usuario manualmente.
    """
    # Nombre limpio (sin query strings de S3/Azure)
    base_name = os.path.basename(src.split("?", 1)[0]) or "Manarey-Setup.exe"
    if not base_name.lower().endswith(".exe"):
        base_name = "Manarey-Setup.exe"

    dst_dir = _downloads_dir()
    try:
        os.makedirs(dst_dir, exist_ok=True)
    except Exception:
        pass
    dst = os.path.join(dst_dir, base_name)

    # Intentar UI con QProgressDialog (más simple y fiable)
    dlg = None
    try:
        from PyQt5.QtCore import Qt
        from PyQt5.QtWidgets import QApplication, QProgressDialog

        dlg = QProgressDialog(
            f"Descargando {base_name} desde GitHub...",
            "Cancelar",
            0,
            100,
            parent_widget,
        )
        dlg.setWindowTitle("Descargando actualización")
        dlg.setWindowModality(Qt.ApplicationModal)
        dlg.setAutoClose(False)
        dlg.setAutoReset(False)
        dlg.setMinimumDuration(0)
        dlg.setValue(0)
        dlg.show()
        QApplication.processEvents()
    except Exception:
        dlg = None

    cancelled = {"v": False}

    def cancel_cb():
        try:
            if dlg is not None and dlg.wasCanceled():
                cancelled["v"] = True
                return True
        except Exception:
            pass
        return cancelled["v"]

    def progress_cb(done: int, total: int):
        try:
            if dlg is None:
                return
            if total and total > 0:
                pct = int(done * 100 / total)
                dlg.setValue(max(0, min(100, pct)))
                mb_done = done / (1024 * 1024)
                mb_total = total / (1024 * 1024)
                dlg.setLabelText(
                    f"Descargando desde GitHub...\n"
                    f"{mb_done:.1f} MB / {mb_total:.1f} MB"
                )
            else:
                dlg.setLabelText(
                    f"Descargando desde GitHub...\n{done / (1024 * 1024):.1f} MB"
                )
            from PyQt5.QtWidgets import QApplication

            QApplication.processEvents()
        except Exception:
            pass

    # Descargar al directorio Descargas directamente
    _log_update_event(f"descarga a Descargas: {src} -> {dst}")
    ok_path = _download_to_path(src, dst, progress_cb=progress_cb, cancel_cb=cancel_cb)

    try:
        if dlg is not None:
            dlg.close()
    except Exception:
        pass

    return ok_path


def _download_to_path(
    src: str, dst: str, progress_cb=None, cancel_cb=None
) -> Optional[str]:
    """Descarga src (URL) a dst (ruta absoluta) con retries robustos."""
    if not src.lower().startswith(("http://", "https://")):
        return None

    last_err: Optional[str] = None
    for attempt in range(1, 4):
        try:
            import requests

            headers = {"User-Agent": "Manarey-Updater/1.0", "Accept": "*/*"}
            with requests.get(
                src,
                headers=headers,
                stream=True,
                timeout=(30, None),
                allow_redirects=True,
            ) as r:
                if r.status_code != 200:
                    raise RuntimeError(f"HTTP {r.status_code}")
                total = int(r.headers.get("Content-Length") or 0)
                done = 0
                with open(dst, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 256):
                        if cancel_cb and cancel_cb():
                            _log_update_event("descarga cancelada")
                            try:
                                f.close()
                                os.remove(dst)
                            except Exception:
                                pass
                            return None
                        if chunk:
                            f.write(chunk)
                            done += len(chunk)
                            if progress_cb:
                                progress_cb(done, total)

            size = os.path.getsize(dst)
            if size < 1024 * 1024:
                raise RuntimeError(f"archivo muy pequeño: {size}")
            if total and size < total:
                raise RuntimeError(f"incompleto: {size}/{total}")

            _log_update_event(f"descarga ok: {dst} ({size} bytes)")
            return dst

        except Exception as e:
            last_err = str(e)
            _log_update_event(f"intento {attempt}/3 falló: {e}")
            if attempt < 3:
                try:
                    time.sleep(5 * attempt)
                except Exception:
                    pass

    _log_update_event(f"descarga falló definitivamente: {last_err}")
    return None


def _open_folder_and_select(path: str) -> bool:
    """Abre el Explorador de Windows seleccionando el archivo."""
    try:
        if os.name == "nt":
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
            return True
        # Otros OS: abrir directorio
        folder = os.path.dirname(path)
        if sys.platform == "darwin":
            subprocess.Popen(["open", folder])
        else:
            subprocess.Popen(["xdg-open", folder])
        return True
    except Exception as e:
        _log_update_event(f"no se pudo abrir carpeta: {e}")
        return False


def _launch_installer_wizard_and_exit(exe_path: str) -> bool:
    """Lanza el instalador NSIS (con wizard, NO silent) pidiendo UAC y cierra la app.

    Cerrar la app es crítico: NSIS necesita sobrescribir Manarey.exe y no puede
    si el proceso sigue corriendo. Lanzamos el instalador con 'runas' (UAC),
    esperamos ~1s para que aparezca el prompt de UAC, y luego os._exit(0).
    """
    if not os.path.exists(exe_path):
        _log_update_event(f"launch: no existe {exe_path}")
        return False

    # Non-Windows: fallback simple
    if os.name != "nt":
        try:
            subprocess.Popen([exe_path])
            time.sleep(1)
            os._exit(0)
        except Exception as e:
            _log_update_event(f"launch non-win falló: {e}")
        return True

    # Windows: ShellExecuteExW con 'runas' (UAC) — SIN /S para mostrar wizard
    try:

        class SHELLEXECUTEINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_ulong),
                ("fMask", ctypes.c_ulong),
                ("hwnd", ctypes.c_void_p),
                ("lpVerb", ctypes.c_wchar_p),
                ("lpFile", ctypes.c_wchar_p),
                ("lpParameters", ctypes.c_wchar_p),
                ("lpDirectory", ctypes.c_wchar_p),
                ("nShow", ctypes.c_int),
                ("hInstApp", ctypes.c_void_p),
                ("lpIDList", ctypes.c_void_p),
                ("lpClass", ctypes.c_wchar_p),
                ("hkeyClass", ctypes.c_void_p),
                ("dwHotKey", ctypes.c_ulong),
                ("hIconOrMonitor", ctypes.c_void_p),
                ("hProcess", ctypes.c_void_p),
            ]

        sei = SHELLEXECUTEINFO()
        sei.cbSize = ctypes.sizeof(sei)
        sei.fMask = 0
        sei.hwnd = None
        sei.lpVerb = "runas"  # UAC elevation
        sei.lpFile = exe_path
        sei.lpParameters = ""  # wizard (NO /S)
        sei.lpDirectory = None
        sei.nShow = 1  # SW_SHOWNORMAL
        sei.hProcess = None

        ok = ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(sei))
        if not ok:
            _log_update_event("ShellExecuteExW: UAC cancelado o error al lanzar")
            return False

        _log_update_event("instalador lanzado OK, cerrando app en 1s")
        time.sleep(1)  # dejar que UAC aparezca antes de cerrar la ventana
        os._exit(0)
        return True

    except Exception as e:
        _log_update_event(f"launch installer error: {e}")
        try:
            os.startfile(exe_path)
            time.sleep(1)
            os._exit(0)
        except Exception as e2:
            _log_update_event(f"fallback startfile falló: {e2}")
        return False


def _start_update_from_manifest(manifest: Dict[str, Any], parent_widget=None) -> bool:
    """Descarga el instalador de GitHub y lo lanza, cerrando la app.

    Flujo (simple, tal como pidió el usuario):
      1. Descargar el .exe con barra de progreso a %USERPROFILE%\\Downloads.
      2. Lanzar el instalador NSIS (wizard, con UAC).
      3. Cerrar la app inmediatamente para que NSIS pueda sobrescribirla.
    """
    src = manifest.get("path") or manifest.get("url")
    if not src:
        _log_update_event("start_update: manifest sin url/path")
        return False

    # Ruta local ya descargada (compartida de red, etc.)
    if not src.lower().startswith(("http://", "https://")):
        if os.path.exists(src):
            return _launch_installer_wizard_and_exit(src)
        return False

    # URL http(s) → descargar a Downloads con progreso
    exe_path = _download_installer_with_progress(src, parent_widget)
    if not exe_path:
        try:
            from PyQt5.QtWidgets import QMessageBox

            QMessageBox.warning(
                parent_widget,
                "Descarga fallida",
                "No se pudo descargar el instalador desde GitHub.\n\n"
                "Revisá tu conexión y volvé a intentar más tarde.\n\n"
                f"Log: {_log_path()}",
            )
        except Exception:
            pass
        return False

    # Descarga OK → lanzar instalador + cerrar app
    return _launch_installer_wizard_and_exit(exe_path)


def start_update_from_pending(parent_widget=None) -> bool:
    """Inicia instalacion usando el update pendiente guardado."""
    pending = get_pending_update()
    if not pending:
        return False
    ok = _start_update_from_manifest(pending, parent_widget)
    if not ok:
        try:
            from PyQt5.QtWidgets import QMessageBox

            QMessageBox.warning(
                parent_widget, "Actualizacion", "No se pudo iniciar la actualizacion."
            )
        except Exception:
            pass
    return ok


def check_for_updates(parent_widget=None, show_ui: bool = True) -> None:
    """Chequea updates en base de datos (Supabase) y ofrece instalar.
    Usa UI integrada profesional con estilos de la app.
    """
    manifest = refresh_update_state()
    if not manifest:
        return

    mandatory = _is_mandatory(manifest)
    pub = _get_published_at(manifest)
    force_days = _force_after_days(manifest)
    days_passed = max(0, int((datetime.now() - pub).days))
    days_left = max(0, force_days - days_passed)

    if not show_ui:
        # Solo actualizar estado. Si es obligatorio, avisar con UI mínima.
        if mandatory:
            try:
                from PyQt5.QtWidgets import QMessageBox

                msg = (
                    f"Actualización obligatoria disponible ({manifest.get('version')}).\n"
                    "Debes actualizar para continuar."
                )
                QMessageBox.warning(parent_widget, "Actualización obligatoria", msg)
            except Exception:
                pass
            try:
                os._exit(0)
            except Exception:
                sys.exit(0)
        return

    ui_confirmed = False
    show_install = False

    # Intentar usar diálogo profesional styled
    try:
        from ui.ui_update_dialog import UpdateDialog

        dlg = UpdateDialog(parent_widget)

        # Preparar changelog con información de días
        changelog = (
            manifest.get("notes")
            or "Mejoras de rendimiento, estabilidad y correcciones."
        )
        if not mandatory and days_left > 0:
            changelog += f"\n\n⏰ Tienes {days_left} día(s) antes de ser obligatoria."

        dlg.set_update_info(manifest.get("version"), changelog, mandatory=mandatory)

        ui_confirmed = dlg.exec_() == UpdateDialog.Accepted

        if ui_confirmed:
            show_install = True
        else:
            if mandatory:
                try:
                    os._exit(0)
                except Exception:
                    sys.exit(0)
            return

    except Exception as e:
        # Log pero continúa con fallback
        try:
            logger.debug(f"Error cargando diálogo de actualización: {e}")
        except Exception:
            pass

        # Fallback a QMessageBox genérico
        try:
            from PyQt5.QtWidgets import QMessageBox

            notes = manifest.get("notes") or "Hay una actualización disponible."
            msg = f"Versión {manifest.get('version')} disponible.\n{notes}\n\n¿Deseas descargar e instalar ahora?"
            if not mandatory:
                msg += (
                    f"\n\n⏰ Si no actualizas en {days_left} día(s), será obligatoria."
                )
            else:
                msg += "\n\n⚠️ Esta actualización es obligatoria."

            ret = QMessageBox.question(parent_widget, "Actualización disponible", msg)
            if ret != QMessageBox.Yes:
                if mandatory:
                    try:
                        os._exit(0)
                    except Exception:
                        sys.exit(0)
                return
            show_install = True
        except Exception:
            if mandatory:
                try:
                    os._exit(0)
                except Exception:
                    sys.exit(0)
            return

    # SOLO instalar si el usuario confirmó explícitamente
    if show_install:
        _start_update_from_manifest(manifest, parent_widget)
