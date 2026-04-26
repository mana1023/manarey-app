"""
Temporary simplified StockView __init__ that works inline
"""

INIT_CODE = '''
    def __init__(self, username: str, role: str, local_name: str, back_command=None):
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
        
        # Cache
        self.categories_cache = []
        self._products_by_id = {}
        
        # Window setup inline
        self.setWindowTitle(f"Stock - {self.local if self.role=='local' else 'Administrador'}")
        self.resize(1400, 800)
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(25, 20, 25, 30)
        main_layout.setSpacing(25)
        
        # Header simple
        header = QLabel(f"Stock de {self.view_local}")
        header.setStyleSheet("color: #ffc107; font-size: 28px; font-weight: 900;")
        main_layout.addWidget(header)
        
        # Tabla (sin filtros por ahora para simplificar)
        from PyQt5.QtWidgets import QTableWidget, QHeaderView
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Nombre", "Cantidad", "Precio"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        main_layout.addWidget(self.table)
        
        # Loading bar
        self.loading_bar = QProgressBar()
        self.loading_bar.setVisible(False)
        main_layout.addWidget(self.loading_bar)
        
        # No Firestore listener (SQL-only mode)
        # No queue workers por ahora para simplificar
        
        # Load data
        self.load_data_simple()
        
    def load_data_simple(self):
        """Simple data loading from PostgreSQL"""
        try:
            from models import stock_model as sm
            products = sm.get_stock_filtered(self.view_local, "", "", "")
            self.populate_table_simple(products)
        except Exception as e:
            import logging
            logging.error(f"Error loading data: {e}")
            
    def populate_table_simple(self, products):
        """Simple table population"""
        self.table.setRowCount(len(products))
        for i, p in enumerate(products):
            from PyQt5.QtWidgets import QTableWidgetItem
            self.table.setItem(i, 0, QTableWidgetItem(str(p.get('nombre', ''))))
            self.table.setItem(i, 1, QTableWidgetItem(str(p.get('cantidad', 0))))
            self.table.setItem(i, 2, QTableWidgetItem(f"${p.get('precio_venta', 0)}"))
'''

print(INIT_CODE)
