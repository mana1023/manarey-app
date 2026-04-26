import logging

from models import db

logger = logging.getLogger(__name__)


def normalize_categories_to_lower() -> int:
    """Normaliza categorias en productos a minuscula. Devuelve filas afectadas."""
    conn = None
    try:
        conn = db.get_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE productos SET categoria = LOWER(TRIM(categoria)) WHERE categoria IS NOT NULL"
        )
        affected = cur.rowcount or 0
        conn.commit()
        return affected
    except Exception as e:
        try:
            if conn:
                conn.rollback()
        except Exception:
            pass
        logger.error("Error normalizando categorias: %s", e)
        return 0
    finally:
        try:
            if conn:
                db.put_connection(conn)
        except Exception:
            pass


if __name__ == "__main__":
    count = normalize_categories_to_lower()
    print(f"OK. Filas actualizadas: {count}")
