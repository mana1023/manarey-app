"""Script to fix __init__ by finding where it should end"""

with open("views/stock_view.py", "r", encoding="utf-8") as f:
    content = f.read()

# Find the complete __init__ from the Code Interaction Summary I showed earlier
# It should have this structure based on what I viewed earlier:
# Lines 905-959 from my previous view

complete_init = """    def __init__(self, username: str, role: str, local_name: str, back_command=None):
        super().__init__()
        self.username = username
        self.role = role
        self.local = local_name
        self.view_local = self.local
        self.read_only = False
        self.back_command = back_command
        
        # Estado de carga
        self.loading_thread = None
        self.last_search_time = 0
        
        # Cache de categorías para autocompletado
        self.categories_cache = []
        # Cache de productos por id para evitar reconsultas en doble click
        self._products_by_id = {}
        
        self.setup_window()
        self.setup_ui()
        self.setup_shortcuts()
        self.load_data()

        # DISABLED: Listener Firestore (SQL-only mode)
        # self._fs_listener = None
        # try:
        #     self._start_products_listener(self.view_local)
        # except Exception as e:
        #     logger.error(f"No se pudo iniciar listener de Firestore: {e}")
        
        self.notif_timer = QTimer(self)
        self.notif_timer.setInterval(30_000)
        self.notif_timer.timeout.connect(self._poll_notifications)
        self.notif_timer.start()

        # Worker asíncrono para operaciones de stock
        from utils.stock_async import StockAsyncWorker
        
        try:
            # Worker principal para la cola
            self.queue_worker = QueueWorker(interval_ms=3000)
            self.queue_worker.queue_count.connect(self.update_queue_banner)
            self.queue_worker.processing.connect(self._on_queue_processing)
            self.queue_worker.start()
            
            # Worker especializado para operaciones asíncronas
            self.stock_worker = StockAsyncWorker(username, local_name, interval_ms=1000, parent=self)
            self.stock_worker.operation_started.connect(self._on_stock_operation_started)
            self.stock_worker.operation_completed.connect(self._on_stock_operation_completed) 
            self.stock_worker.queue_updated.connect(self._on_stock_queue_updated)
            self.stock_worker.field_updated.connect(self._on_field_updated_confirmed)
            self.stock_worker.execute_callback.connect(self._on_execute_callback)
            self.stock_worker.start()
        except Exception as e:
            logger.error(f"No pudieron iniciarse los workers: {e}")
"""

# Now read up to line 904 (before __init__)
with open("views/stock_view.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

before_init = lines[:904]  # Everything before __init__
after_corrupted_section = lines[924:]  # Everything after the corrupted part

# Write fixed file
with open("views/stock_view.py.new", "w", encoding="utf-8") as out:
    out.writelines(before_init)
    out.write("\n")
    out.write(complete_init)
    out.write("\n")
    out.writelines(after_corrupted_section)

print(f"Fixed file created: stock_view.py.new")
print(f"  Before __init__: {len(before_init)} lines")
print(f"  After corrupted: {len(after_corrupted_section)} lines")
