import logging
from datetime import datetime
from typing import Any, Dict

from models.db import get_connection, is_postgres, put_connection

logger = logging.getLogger(__name__)


def add_user_dual(user_data: Dict[str, Any]) -> bool:
    """
    Agrega un usuario en SQL (PostgreSQL/Supabase). Firestore fue removido.
    """
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        username = user_data["username"]
        password = user_data["password"]
        role = user_data["role"]
        local = user_data.get("local")

        cur.execute(
            "INSERT INTO usuarios (username, password, role, local) VALUES (%s, %s, %s, %s)"
            if is_postgres()
            else "INSERT INTO usuarios (username, password, role, local) VALUES (?, ?, ?, ?)",
            (username, password, role, local),
        )
        conn.commit()
        logger.info("Usuario %s agregado a SQL", username)
        return True
    except Exception as e:
        logger.error("Error agregando usuario a SQL: %s", e)
        return False
    finally:
        if conn:
            try:
                put_connection(conn)
            except Exception:
                pass


def get_user_by_username(username: str):
    """Obtiene un usuario por username desde SQL."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        query = (
            "SELECT username, password, role, local FROM usuarios WHERE username = %s LIMIT 1"
            if is_postgres()
            else "SELECT username, password, role, local FROM usuarios WHERE username = ? LIMIT 1"
        )
        cur.execute(query, (username,))
        row = cur.fetchone()
        if not row:
            return None
        return {
            "username": row[0],
            "password": row[1],
            "role": row[2],
            "local": row[3],
        }
    except Exception as e:
        logger.error("Error obteniendo usuario %s: %s", username, e)
        return None
    finally:
        if conn:
            try:
                put_connection(conn)
            except Exception:
                pass


def update_user_dual(username: str, user_data: Dict[str, Any]) -> bool:
    """
    Actualiza un usuario en SQL (PostgreSQL/Supabase).
    """
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        fields = []
        values = []

        if "password" in user_data and user_data["password"]:
            fields.append("password")
            values.append(user_data["password"])
        if "role" in user_data:
            fields.append("role")
            values.append(user_data["role"])
        if "local" in user_data:
            fields.append("local")
            values.append(user_data["local"])

        if fields:
            set_clause = ", ".join(
                [f"{f} = %s" if is_postgres() else f"{f} = ?" for f in fields]
            )
            values.append(username)
            query = f"UPDATE usuarios SET {set_clause} WHERE username = {'%s' if is_postgres() else '?'}"
            cur.execute(query, tuple(values))
            conn.commit()
            logger.info("Usuario %s actualizado en SQL", username)
        return True
    except Exception as e:
        logger.error("Error actualizando usuario en SQL: %s", e)
        try:
            if conn:
                conn.rollback()
        except Exception:
            pass
        return False
    finally:
        if conn:
            try:
                put_connection(conn)
            except Exception:
                pass


def delete_user_dual(username: str) -> bool:
    """Elimina usuario de SQL (PostgreSQL/Supabase)."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        query = (
            "DELETE FROM usuarios WHERE username = %s"
            if is_postgres()
            else "DELETE FROM usuarios WHERE username = ?"
        )
        cur.execute(query, (username,))
        conn.commit()
        return True
    except Exception as e:
        logger.error("Error eliminando usuario SQL: %s", e)
        try:
            if conn:
                conn.rollback()
        except Exception:
            pass
        return False
    finally:
        if conn:
            try:
                put_connection(conn)
            except Exception:
                pass


def update_last_seen(username: str) -> bool:
    """Actualiza el campo last_seen del usuario con la hora local."""
    if not username:
        return False
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        ph = "%s" if is_postgres() else "?"
        now_str = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute(
            f"UPDATE usuarios SET last_seen = {ph} WHERE username = {ph}",
            (now_str, username),
        )
        conn.commit()
        return True
    except Exception as e:
        logger.warning("No se pudo actualizar last_seen para %s: %s", username, e)
        try:
            if conn:
                conn.rollback()
        except Exception:
            pass
        return False
    finally:
        if conn:
            try:
                put_connection(conn)
            except Exception:
                pass
