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
    """Obtiene la versión actual de la aplicación"""
    try:
        from version import __version__

        return __version__
    except Exception:
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


_GITHUB_REPO_DEFAULT = "mana1023/manarey-updates"


def _get_github_repo_from_config() -> tuple:
    """Obtiene GITHUB_REPO de config, env, o usa el repo oficial como fallback.
    Nota: el cliente NO debe guardar tokens por seguridad.
    """
    try:
        import json

        # Buscar config.json en el directorio del ejecutable o el actual
        _exe_dir = os.path.dirname(
            os.path.abspath(sys.argv[0] if sys.argv else __file__)
        )
        _config_paths = [
            os.path.join(_exe_dir, "config.json"),
            "config.json",
            os.path.join(
                os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"),
                "Manarey",
                "config.json",
            ),
        ]
        for _cp in _config_paths:
            try:
                with open(_cp, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    repo = cfg.get("GITHUB_REPO") or os.environ.get("GITHUB_REPO")
                    if repo:
                        return repo, None
            except Exception:
                continue
    except Exception:
        pass
    # Siempre usar el repo oficial si no se encontró en config
    return os.environ.get("GITHUB_REPO") or _GITHUB_REPO_DEFAULT, None


def _get_latest_release_from_github() -> Optional[Dict[str, Any]]:
    """Obtiene la última release desde GitHub API"""
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

                # Extraer información relevante
                version = data.get("tag_name", "").lstrip("v")
                if not version:
                    version = data.get("name", "").split()[-1]

                # Buscar asset (preferir instalador .exe)
                download_url = None
                for asset in data.get("assets", []):
                    name = asset.get("name", "")
                    if name.endswith(".exe") and "Manarey-Setup" in name:
                        download_url = asset["browser_download_url"]
                        break
                if not download_url:
                    for asset in data.get("assets", []):
                        name = asset.get("name", "")
                        if name.endswith(".exe"):
                            download_url = asset["browser_download_url"]
                            break

                if not download_url:
                    logger.debug("No se encontraron assets en release")
                    return None

                return {
                    "version": version,
                    "url": download_url,
                    "notes": data.get("body", ""),
                    "published_at": str(data.get("published_at", "")),
                    "mandatory": bool(not data.get("prerelease")),
                    "force_after_days": 2,
                    "_meta": {"source": "github"},
                }
        except Exception as e:
            logger.debug(f"Error consultando GitHub API: {e}")
            return None

    except Exception as e:
        logger.error(f"Error obteniendo release de GitHub: {e}")
        return None


def _load_manifest_from_db() -> Optional[Dict[str, Any]]:
    """Intenta cargar desde GitHub primero, fallback a Supabase"""
    # Primero intentar GitHub (nuevo y recomendado)
    github_manifest = _get_latest_release_from_github()
    if github_manifest:
        return github_manifest

    # Fallback a Supabase (legacy)
    try:
        from models import update_center

        latest = update_center.latest_update()
        if not latest:
            return None
        return {
            "version": latest.get("version"),
            "url": latest.get("download_url"),
            "notes": latest.get("changelog") or "",
            "published_at": str(latest.get("created_at") or ""),
            "mandatory": bool(latest.get("mandatory")),
            "force_after_days": 2,
            "_meta": {"source": "db"},
        }
    except Exception as e:
        try:
            logger.debug(f"Error cargando manifest de Supabase: {e}")
        except Exception:
            pass
        return None


def _get_best_manifest() -> Optional[Dict[str, Any]]:
    """Carga manifiesto desde la base (Supabase) y devuelve la ultima version."""
    return _load_manifest_from_db()


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
    try:
        # src puede ser ruta local (compartida) o URL http(s)
        tmp_dir = tempfile.gettempdir()
        fname = os.path.basename(src)
        dst = os.path.join(tmp_dir, fname)
        if src.lower().startswith(("http://", "https://")):
            # Preferir requests si esta disponible (mejor manejo de redirects)
            try:
                import requests

                headers = {"User-Agent": "Manarey-Updater/1.0"}
                with requests.get(
                    src, headers=headers, stream=True, timeout=60, allow_redirects=True
                ) as r:
                    if r.status_code != 200:
                        return None
                    total = int(r.headers.get("Content-Length") or 0)
                    done = 0
                    with open(dst, "wb") as f:
                        for chunk in r.iter_content(chunk_size=1024 * 256):
                            if cancel_cb and cancel_cb():
                                return None
                            if chunk:
                                f.write(chunk)
                                done += len(chunk)
                                if progress_cb:
                                    progress_cb(done, total)
            except Exception:
                # Fallback urllib
                with urllib.request.urlopen(src, timeout=60) as resp, open(
                    dst, "wb"
                ) as f:
                    shutil.copyfileobj(resp, f)
        else:
            if os.path.exists(src):
                shutil.copy2(src, dst)
            else:
                return None
        # Validar tamaño minimo (evita guardar HTML de error)
        try:
            if os.path.getsize(dst) < 1024 * 1024:
                return None
        except Exception:
            pass
        if progress_cb:
            progress_cb(1, 1)
        return dst
    except Exception:
        return None


def refresh_update_state() -> Optional[Dict[str, Any]]:
    """Actualiza update_state.json sin mostrar UI. Devuelve el manifest si hay update nuevo."""
    manifest = _get_best_manifest()
    if not manifest or not manifest.get("version"):
        _clear_pending_update()
        return None

    cur_v = _parse_version(get_current_version())
    new_v = _parse_version(manifest.get("version"))
    if new_v <= cur_v:
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

        # ── ShellExecuteExW con SEE_MASK_NOCLOSEPROCESS ──────────────────────
        SEE_MASK_NOCLOSEPROCESS = 0x00000040

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
        sei.fMask = SEE_MASK_NOCLOSEPROCESS
        sei.hwnd = None
        sei.lpVerb = "runas"
        sei.lpFile = exe_path
        sei.lpParameters = "/S"  # NSIS silent install
        sei.lpDirectory = None
        sei.nShow = 0  # SW_HIDE
        sei.hProcess = None

        ok = ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(sei))
        if not ok or not sei.hProcess:
            # Usuario canceló UAC
            logger.warning("ShellExecuteExW: UAC cancelado o error")
            return False

        # Cerramos el handle y salimos YA, antes de que NSIS intente copiar
        # los archivos. Si esperamos a que termine, Manarey.exe sigue bloqueado
        # y Windows no puede sobreescribirlo (usa "reemplazar al reiniciar").
        ctypes.windll.kernel32.CloseHandle(sei.hProcess)
        os._exit(0)
        return True

    except Exception as e:
        logger.error(f"Error en instalador: {e}")
        # Si algo falló intentar igual
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


def _start_update_from_manifest(manifest: Dict[str, Any], parent_widget=None) -> bool:
    """Descarga el instalador (.exe) y lo ejecuta."""
    src = manifest.get("path") or manifest.get("url")
    if not src:
        return False

    try:
        # Descargar y ejecutar instalador
        if src.lower().startswith(("http://", "https://")):
            success = _download_and_install_with_progress(src, parent_widget)
        else:
            success = _run_installer(src)

        if not success:
            try:
                from PyQt5.QtWidgets import QMessageBox

                QMessageBox.warning(
                    parent_widget,
                    "Actualización",
                    "No se pudo instalar la actualización.",
                )
            except Exception:
                pass

        return success
    except Exception as e:
        logger.error(f"Error en actualización: {e}")
        return False


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
