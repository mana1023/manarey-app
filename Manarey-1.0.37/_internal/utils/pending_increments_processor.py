"""
DISABLED: Procesador de pending_increments deshabilitado para compatibilidad con Firestore/PostgreSQL.
El sistema de cola de Firestore maneja todas las operaciones automáticamente.
"""

import logging
from typing import Dict, Tuple

logger = logging.getLogger(__name__)


def process_pending_increments() -> Tuple[int, int]:
    """
    DISABLED: Función deshabilitada. Retorna 0, 0.
    Sistema de cola de Firestore maneja todo automáticamente.
    """
    return 0, 0


def get_pending_increments_stats() -> Dict:
    """DISABLED: Función deshabilitada. Retorna dict vacío."""
    return {"total_items": 0, "num_productos": 0, "total_delta": 0}
