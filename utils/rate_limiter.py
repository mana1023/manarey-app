"""
Rate limiter y token bucket para proteger la API de cola y la DB.

Evita que picos de operaciones causen exhaustión de conexiones/recursos
en Supabase free o en el sqlite local.
"""

import logging
import time

logger = logging.getLogger(__name__)


class TokenBucket:
    """Token bucket simple para rate-limiting.

    Permite hasta `capacity` tokens consumidos al instante (burst),
    y regenera `rate` tokens por segundo.
    """

    def __init__(self, rate: float, capacity: int):
        """
        Args:
            rate: tokens por segundo a regenerar.
            capacity: máximo de tokens acumulables (burst limit).
        """
        self.rate = rate
        self.capacity = capacity
        self._tokens = float(capacity)
        self._last_update = time.time()

    def consume(self, n: int = 1) -> bool:
        """Intenta consumir n tokens. Devuelve True si se logró, False si no hay suficientes."""
        now = time.time()
        elapsed = now - self._last_update
        self._last_update = now

        # Regenerar tokens según tiempo transcurrido
        self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)

        # Intentar consumo
        if self._tokens >= n:
            self._tokens -= n
            return True
        return False

    def available(self) -> int:
        """Devuelve número aproximado de tokens disponibles."""
        now = time.time()
        elapsed = now - self._last_update
        available = min(self.capacity, self._tokens + elapsed * self.rate)
        return int(available)


class BackpressureManager:
    """Gestiona backpressure: detecta si la cola está saturada y aplica throttling."""

    def __init__(self, queue_size_threshold: int = 100, retry_delay_sec: float = 5.0):
        """
        Args:
            queue_size_threshold: si op_queue tiene más items que esto, aplicar backpressure.
            retry_delay_sec: tiempo de espera antes de reintentar tras backpressure.
        """
        self.queue_size_threshold = queue_size_threshold
        self.retry_delay_sec = retry_delay_sec
        self._backpressure_until = 0.0

    def is_active(self) -> bool:
        """Devuelve True si actualmente hay backpressure activo."""
        return time.time() < self._backpressure_until

    def activate(self):
        """Activa backpressure por retry_delay_sec segundos."""
        self._backpressure_until = time.time() + self.retry_delay_sec
        logger.warning(f"Backpressure activated for {self.retry_delay_sec}s")

    def deactivate(self):
        """Desactiva backpressure."""
        self._backpressure_until = 0.0
        logger.info("Backpressure deactivated")
