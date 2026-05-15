# app.py - Aplicacion principal de Manarey

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone


def _bootstrap_qt_paths():
    """Asegura rutas de plugins/Qt cuando se ejecuta desde instalador (onedir)."""
    try:
        if not getattr(sys, "frozen", False):
            return
        base_dir = os.path.dirname(sys.executable)
        internal = os.path.join(base_dir, "_internal")
        if not os.path.isdir(internal):
            return
        qt_root = os.path.join(internal, "PyQt5", "Qt5")
        plugins = os.path.join(qt_root, "plugins")
        platforms = os.path.join(plugins, "platforms")
        bin_dir = os.path.join(qt_root, "bin")

        # Asegurar que el loader encuentre DLLs empaquetadas en _internal
        os.environ["PATH"] = internal + os.pathsep + os.environ.get("PATH", "")
        # En Python 3.8+ en Windows, agregar explícitamente directorios de DLL
        try:
            if hasattr(os, "add_dll_directory"):
                os.add_dll_directory(internal)
                if os.path.isdir(bin_dir):
                    os.add_dll_directory(bin_dir)
        except Exception:
            pass
        if os.path.isdir(plugins):
            os.environ["QT_PLUGIN_PATH"] = plugins
        if os.path.isdir(platforms):
            os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = platforms
        if os.path.isdir(bin_dir):
            os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
        # Fallback para drivers problemáticos
        os.environ.setdefault("QT_OPENGL", "software")
    except Exception:
        pass


_bootstrap_qt_paths()

from PyQt5.QtCore import QCoreApplication, QSharedMemory, Qt, QTimer
from PyQt5.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PyQt5.QtWidgets import QApplication, QMessageBox, QSplashScreen

from styles import STYLE_SHEET
from version import __version__

try:
    from logging_config import setup_logging
except Exception:
    setup_logging = None

logger = logging.getLogger("manarey")


def _logs_dir():
    try:
        if getattr(sys, "frozen", False):
            return os.path.join(os.path.dirname(sys.executable), "logs")
        return os.path.join(os.path.dirname(__file__), "logs")
    except Exception:
        return os.path.join(os.getcwd(), "logs")


def _install_crash_monitor(days: int = 2):
    """Activa monitoreo de crashes por N dias y luego se desactiva solo."""
    try:
        os.makedirs(_logs_dir(), exist_ok=True)
        meta_path = os.path.join(_logs_dir(), "crash_monitor.json")
        now = int(time.time())
        start_ts = None
        try:
            if os.path.exists(meta_path):
                with open(meta_path, "r", encoding="utf-8") as f:
                    data = json.load(f) or {}
                start_ts = int(data.get("start_ts") or 0) or None
        except Exception:
            start_ts = None
        if not start_ts:
            start_ts = now
            try:
                with open(meta_path, "w", encoding="utf-8") as f:
                    json.dump({"start_ts": start_ts}, f, indent=2)
            except Exception:
                pass
        if now - start_ts > int(days) * 86400:
            return  # desactivado por tiempo

        crash_log = os.path.join(_logs_dir(), "crash.log")

        def _log_crash(prefix: str, exctype, value, tb):
            try:
                ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                with open(crash_log, "a", encoding="utf-8") as f:
                    f.write(f"{ts} {prefix}\n")
                    f.write(
                        "".join(
                            logging.Formatter().formatException((exctype, value, tb))
                        )
                        + "\n\n"
                    )
                # También anexar al log principal si existe
                main_log = os.path.join(_logs_dir(), "manarey.log")
                try:
                    with open(main_log, "a", encoding="utf-8") as mf:
                        mf.write(f"{ts} {prefix}\n")
                        mf.write(
                            "".join(
                                logging.Formatter().formatException(
                                    (exctype, value, tb)
                                )
                            )
                            + "\n\n"
                        )
                except Exception:
                    pass
            except Exception:
                pass

        def _excepthook(exctype, value, tb):
            _log_crash("Unhandled exception", exctype, value, tb)
            try:
                logger.error("Unhandled exception", exc_info=(exctype, value, tb))
            except Exception:
                pass
            sys.__excepthook__(exctype, value, tb)

        sys.excepthook = _excepthook

        try:
            import threading

            if hasattr(threading, "excepthook"):

                def _thread_hook(args):
                    _log_crash(
                        "Thread exception",
                        args.exc_type,
                        args.exc_value,
                        args.exc_traceback,
                    )

                threading.excepthook = _thread_hook
        except Exception:
            pass
    except Exception:
        pass


def _resource_path(*paths: str) -> str:
    try:
        base = getattr(sys, "_MEIPASS", os.path.dirname(__file__))
    except Exception:
        base = os.path.dirname(__file__)
    return os.path.join(base, *paths)


def _create_splash():
    pix = QPixmap(520, 320)
    pix.fill(QColor("#0f0f14"))
    painter = QPainter(pix)
    painter.setRenderHints(QPainter.Antialiasing)

    # Logo si existe
    try:
        logo_path = _resource_path("assets", "images", "logo_manarey.png")
        if os.path.exists(logo_path):
            logo = QPixmap(logo_path)
            if not logo.isNull():
                logo = logo.scaled(
                    180, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                x = (pix.width() - logo.width()) // 2
                y = 30
                painter.drawPixmap(x, y, logo)
    except Exception:
        pass

    painter.setPen(QColor("#E6B800"))
    painter.setFont(QFont("Segoe UI", 22, QFont.Bold))
    painter.drawText(pix.rect().adjusted(0, 130, 0, 0), Qt.AlignCenter, "Manarey")
    painter.setPen(QColor("#A0A0B0"))
    painter.setFont(QFont("Segoe UI", 11))
    painter.drawText(pix.rect().adjusted(0, 170, 0, 0), Qt.AlignCenter, "Cargando...")
    painter.end()
    return QSplashScreen(pix)


def main():
    """Funcion principal que inicia la aplicacion"""
    # Logging global + excepthook
    try:
        if setup_logging:
            setup_logging()
    except Exception:
        pass
    _install_crash_monitor(days=2)
    # Habilitar escalado HiDPI antes de crear QApplication
    try:
        QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    except Exception:
        pass

    # Crear la aplicacion Qt
    try:
        QCoreApplication.setAttribute(Qt.AA_UseSoftwareOpenGL, True)
    except Exception:
        pass
    app = QApplication(sys.argv)
    app.setApplicationName("Manarey")
    app.setApplicationVersion(__version__)
    app.setQuitOnLastWindowClosed(True)
    # Modo kiosco: fuerza pantalla completa en ventanas principales
    try:
        app.setProperty("manarey_kiosk", True)
        app.setProperty("manarey_auto_fit", True)
    except Exception:
        pass
    try:
        app.lastWindowClosed.connect(app.quit)
    except Exception:
        pass

    def _shutdown_app():
        """Cierra ventanas ocultas/restantes para terminar el proceso de verdad."""
        try:
            for widget in list(app.topLevelWidgets()):
                try:
                    if widget is not None:
                        widget.close()
                except Exception:
                    pass
        except Exception:
            pass

    try:
        app.aboutToQuit.connect(_shutdown_app)
    except Exception:
        pass

    # Instalar manejador global de errores no capturados
    try:
        from utils.error_handler import setup_global_error_handler

        setup_global_error_handler(app)
    except Exception:
        pass

    # Mostrar splash lo antes posible
    splash = _create_splash()
    splash.show()
    app.processEvents()

    try:
        import app_theme as _at

        _at.apply_to_app()
    except Exception:
        from styles import STYLE_SHEET

        try:
            app.setStyleSheet(STYLE_SHEET)
        except Exception:
            pass

    try:
        icon_path = _resource_path("assets", "images", "logo_manarey.png")
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))
    except Exception:
        pass
    try:
        single = QSharedMemory("ManareyAppSingleton_v1")
        if not single.create(1):
            QMessageBox.information(
                None, "Manarey", "El programa ya esta en ejecucion."
            )
            return
        app.setProperty("manarey_single_instance", single)
    except Exception:
        pass

    # Cargar configuracion de base de datos
    exe_dir = (
        os.path.dirname(sys.executable)
        if getattr(sys, "frozen", False)
        else os.path.dirname(__file__)
    )
    config = {}
    if getattr(sys, "frozen", False):
        local_appdata = os.environ.get("LOCALAPPDATA") or os.path.expanduser(
            r"~\AppData\Local"
        )
        config_dir = os.path.join(local_appdata, "Manarey")
        os.makedirs(config_dir, exist_ok=True)
        config_path = os.path.join(config_dir, "config.json")
        bundled_config = os.path.join(exe_dir, "config.json")
        bundled_cfg = None
        if os.path.exists(bundled_config):
            try:
                with open(bundled_config, "r") as f:
                    bundled_cfg = json.load(f)
            except Exception as e:
                print(f"[ERROR] No se pudo leer config.json embebido: {e}")

        # Leer config local existente (si hay)
        local_cfg = None
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    local_cfg = json.load(f)
            except Exception as e:
                print(f"[ERROR] No se pudo leer config.json local: {e}")

        # Si hay config embebido y no hay local, o si el database_url difiere, sobreescribir local
        try:
            if bundled_cfg:
                local_url = ((local_cfg or {}).get("database_url") or "").strip()
                bundled_url = (bundled_cfg.get("database_url") or "").strip()
                if (not local_cfg) or (bundled_url and bundled_url != local_url):
                    with open(config_path, "w") as f:
                        json.dump(bundled_cfg, f, indent=2)
                    config = bundled_cfg
                    print("[OK] config.json actualizado en AppData")
                else:
                    config = local_cfg or {}
            else:
                config = local_cfg or {}
        except Exception as e:
            print(f"[ERROR] No se pudo actualizar config.json: {e}")
    else:
        config_path = os.path.join(os.path.dirname(__file__), "config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    config = json.load(f)
            except Exception as e:
                print(f"[ERROR] No se pudo leer config.json: {e}")

    # Configurar DATABASE_URL (Supabase/Postgres) - obligatorio
    db_url_cfg = (config.get("database_url") or "").strip()
    db_env = os.environ.get("DATABASE_URL")
    if db_env:
        os.environ["DATABASE_URL"] = db_env.strip()
    elif db_url_cfg:
        os.environ["DATABASE_URL"] = db_url_cfg
    else:
        dburl_path = os.path.join(os.path.dirname(__file__), ".dburl")
        if os.path.exists(dburl_path):
            try:
                with open(dburl_path, "r") as f:
                    os.environ["DATABASE_URL"] = f.read().strip()
            except Exception as e:
                print(f"[ADVERTENCIA] No se pudo leer .dburl: {e}")

    if not os.environ.get("DATABASE_URL"):
        print(
            "[ERROR] DATABASE_URL no configurado. Manarey requiere PostgreSQL/Supabase."
        )
        try:
            splash.hide()
        except Exception:
            pass
        sys.exit(1)

    print("[OK] Backend: PostgreSQL/Supabase")

    # Inicializar pool de base de datos
    splash.showMessage(
        "Inicializando base de datos...",
        Qt.AlignBottom | Qt.AlignHCenter,
        QColor("#A0A0B0"),
    )
    app.processEvents()
    try:
        from models import db

        db.init_db()
        print("[OK] Pool de base de datos inicializado")
        # Pre-calentar la conexión para reducir latencia al entrar a stock
        try:
            from models.db import get_connection, put_connection

            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
            cur.close()
            put_connection(conn)
        except Exception as e:
            print(f"[WARN] No se pudo pre-calentar la conexión: {e}")
        # Mantenimiento diario en background (purge historial, noti_buffer, etc.)
        try:
            import threading

            threading.Thread(
                target=db.run_daily_maintenance, daemon=True, name="db-maintenance"
            ).start()
        except Exception as e:
            print(f"[WARN] No se pudo iniciar mantenimiento diario: {e}")
    except Exception as e:
        print(f"[ERROR] Al inicializar base de datos: {e}")

    # Configurar logging centralizado
    splash.showMessage(
        "Configurando sistema...", Qt.AlignBottom | Qt.AlignHCenter, QColor("#A0A0B0")
    )
    app.processEvents()
    try:
        from logging_config import setup_logging

        setup_logging()
    except Exception:
        pass

    # Chequear configuracion/env vars criticas (no fatal)
    try:
        from utils.config_check import check_config

        check_config()
    except Exception:
        pass

    # Diferir la construcción de ventana al primer tick del event loop
    # para que el splash quede visible antes de las importaciones pesadas.
    splash.showMessage(
        "Iniciando...", Qt.AlignBottom | Qt.AlignHCenter, QColor("#A0A0B0")
    )
    app.processEvents()

    _splash_ref = splash  # capturar para el closure

    def _open_main_window():
        window = None
        _needs_prebuild = False  # True si hay auto-login y conocemos usuario/local

        # ── Crear ventana (sin mostrarla todavía) ─────────────────────────────
        try:
            appdata = os.environ.get("APPDATA")
            if appdata:
                prefs_path = os.path.join(appdata, "Manarey", "user_prefs.json")
            else:
                prefs_path = os.path.join(
                    os.path.expanduser("~"), ".manarey_prefs", "user_prefs.json"
                )
            if prefs_path and os.path.exists(prefs_path):
                with open(prefs_path, "r", encoding="utf-8") as f:
                    prefs = json.load(f) or {}
                if prefs.get("remember") and prefs.get("role"):
                    try:
                        role = prefs.get("role")
                        if role == "admin":
                            from views.main_admin import MainAdminWindow

                            window = MainAdminWindow(
                                {
                                    "username": prefs.get("username", ""),
                                    "role": "admin",
                                    "local": prefs.get("local"),
                                }
                            )
                        else:
                            from views.main_local import LocalWindow

                            window = LocalWindow(
                                prefs.get("username", ""),
                                prefs.get("role", "local"),
                                prefs.get("local", ""),
                            )
                        _needs_prebuild = True
                        # ← NO llamamos window.show() todavía
                    except Exception:
                        from views.login_view import LoginWindow

                        window = LoginWindow()
                        window.show()
                else:
                    from views.login_view import LoginWindow

                    window = LoginWindow()
                    window.show()
            else:
                from views.login_view import LoginWindow

                window = LoginWindow()
                window.show()
        except Exception:
            from views.login_view import LoginWindow

            window = LoginWindow()
            window.show()

        # ── Precargar vistas ANTES de mostrar el menú (splash sigue visible) ──
        if _needs_prebuild and window is not None:
            try:
                _prebuild_all_views(window, _splash_ref, app)
            except Exception:
                pass
            # Ahora sí abrimos el menú — todo precargado
            try:
                if _splash_ref:
                    _splash_ref.showMessage(
                        "¡Listo!",
                        Qt.AlignBottom | Qt.AlignHCenter,
                        QColor("#C9A040"),
                    )
                    app.processEvents()
            except Exception:
                pass
            window.show()

        # ── Cerrar splash ──────────────────────────────────────────────────────
        try:
            if _splash_ref and window:
                _splash_ref.finish(window)
        except Exception:
            pass
        return window

    _window_ref = [None]

    def _deferred_start():
        w = _open_main_window()
        _window_ref[0] = w
        _post_window_setup(app, w)

    from PyQt5.QtCore import QTimer

    QTimer.singleShot(50, _deferred_start)

    exit_code = app.exec_()
    sys.exit(exit_code)


def _prebuild_all_views(window, splash, app_instance):
    """
    Pre-construye todas las vistas secundarias mientras el splash está visible,
    para que la navegación sea instantánea (hide/show en vez de construir en cada clic).
    Solo actúa si hay auto-login (window es LocalWindow o MainAdminWindow).
    Las vistas se guardan en window._prebuilt = {key: view_instance}.
    """
    if window is None:
        return

    def _msg(text):
        try:
            if splash:
                splash.showMessage(
                    text, Qt.AlignBottom | Qt.AlignHCenter, QColor("#A0A0B0")
                )
            if app_instance:
                app_instance.processEvents()
        except Exception:
            pass

    try:
        from views.main_local import LocalWindow

        is_local = isinstance(window, LocalWindow)
    except Exception:
        is_local = False

    try:
        from views.main_admin import MainAdminWindow

        is_admin = isinstance(window, MainAdminWindow)
    except Exception:
        is_admin = False

    if not (is_local or is_admin):
        return  # LoginWindow — no hay credenciales todavía

    username = getattr(window, "username", "")
    role = getattr(window, "role", "local")
    local = getattr(window, "local", "") or getattr(window, "user_local", "")
    window._prebuilt = {}

    if is_local:
        builds = [
            (
                "stock",
                "Precargando Gestión de Stock...",
                lambda: __import__(
                    "views.stock_view", fromlist=["StockView"]
                ).StockView(username, role, local),
            ),
            (
                "boleta",
                "Precargando Emisión de Boleta...",
                lambda: __import__(
                    "views.boleta_view", fromlist=["BoletaView"]
                ).BoletaView(username, role, local),
            ),
            (
                "ventas",
                "Precargando Historial de Ventas...",
                lambda: __import__(
                    "views.ventas_history_view", fromlist=["VentasWindow"]
                ).VentasWindow(username, role, local),
            ),
            (
                "history",
                "Precargando Historial de Movimientos...",
                lambda: __import__(
                    "views.history_view", fromlist=["HistoryWindow"]
                ).HistoryWindow(username, role, local),
            ),
            (
                "envios",
                "Precargando Envíos...",
                lambda: __import__(
                    "views.envios_view", fromlist=["EnviosWindow"]
                ).EnviosWindow(username, role, local),
            ),
            (
                "problemas",
                "Precargando Mensajes...",
                lambda: __import__(
                    "views.problemas_view", fromlist=["ProblemasWindow"]
                ).ProblemasWindow(username, role, local),
            ),
        ]
    else:  # admin
        builds = [
            (
                "stock",
                "Precargando Gestión de Stock...",
                lambda: __import__(
                    "views.stock_view", fromlist=["StockView"]
                ).StockView(username, role, local),
            ),
            (
                "ventas",
                "Precargando Historial de Ventas...",
                lambda: __import__(
                    "views.ventas_history_view", fromlist=["VentasWindow"]
                ).VentasWindow(username, role, local or "Todos"),
            ),
            (
                "history",
                "Precargando Historial de Movimientos...",
                lambda: __import__(
                    "views.history_view", fromlist=["HistoryWindow"]
                ).HistoryWindow(username, role, local or ""),
            ),
            (
                "problemas",
                "Precargando Mensajes...",
                lambda: __import__(
                    "views.problemas_view", fromlist=["ProblemasWindow"]
                ).ProblemasWindow(username, role, local or "Todos"),
            ),
        ]

    for key, msg, builder in builds:
        _msg(msg)
        try:
            view = builder()
            view.hide()
            window._prebuilt[key] = view
        except Exception:
            pass  # Si falla una vista, el open_* hace fallback a construcción normal


def _post_window_setup(app, window):
    """Aplica escala y lanza threads de background. Llamado tras crear la ventana principal."""
    try:
        # Aplicar escala global centralizada
        try:
            # Cargar preferencia de escala
            scale_pref = "auto"
            try:
                appdata = os.environ.get("APPDATA")
                if appdata:
                    p_path = os.path.join(appdata, "Manarey", "user_prefs.json")
                else:
                    p_path = os.path.join(
                        os.path.expanduser("~"), ".manarey_prefs", "user_prefs.json"
                    )

                if os.path.exists(p_path):
                    with open(p_path, "r", encoding="utf-8") as f:
                        pd = json.load(f)
                        scale_pref = pd.get("scale_preference", "auto")
            except:
                pass

            from utils.ui_scale import apply_global_scale, install_window_scaler

            scale = apply_global_scale(
                app,
                base=(1600, 900),
                min_scale=0.75,
                max_scale=1.5,
                override_scale=scale_pref,
            )
            # Instalar event filter que escala todas las ventanas cuando se muestran
            try:
                install_window_scaler(app)
            except Exception:
                pass
            # Ajuste inicial segun pantalla para abrir utilizable en chicos y grandes
            try:
                screen = app.primaryScreen()
                if screen:
                    size = screen.size()
                    w, h = size.width(), size.height()
                    if not window.property("manarey_no_autoresize"):
                        target_w = int(max(820, min(w * 0.9, 1440)))
                        target_h = int(max(600, min(h * 0.88, 960)))
                        window.resize(target_w, target_h)
            except Exception:
                pass
        except Exception:
            scale = 1.0

        from updater import refresh_update_state

        # Refrescar estado de actualización en background (sin UI)
        def refresh_updates_thread():
            try:
                import time

                time.sleep(2)
                refresh_update_state()
            except Exception:
                pass

        import threading

        update_thread = threading.Thread(target=refresh_updates_thread, daemon=True)
        update_thread.start()

        # Sincronizar ventas offline en background
        def offline_sync_loop():
            try:
                import time

                from models import offline_store

                while True:
                    try:
                        offline_store.sync_pending()
                    except Exception:
                        pass
                    time.sleep(30)
            except Exception:
                pass

        sync_thread = threading.Thread(target=offline_sync_loop, daemon=True)
        sync_thread.start()
    except Exception:
        pass


if __name__ == "__main__":
    main()
