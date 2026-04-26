"""
Completar el __init__ de StockView con toda la interfaz
Basado en estructura de otros views que funcionan
"""

COMPLETE_INIT = '''
    def __init__(self, username: str, role: str, local_name: str, back_command=None):
        super().__init__()
        self.username = username
        self.role = role
        self.local = local_name
        self.view_local = self.local
        self.read_only = False
        self.back_command = back_command
        
        # Estado
        self.loading_thread = None
        self.last_search_time = 0
        self.categories_cache = []
        self._products_by_id = {}
        
        # Window
        self.setWindowTitle(f"Stock - {self.local if self.role=='local' else 'Administrador'}")
        self.resize(1400, 800)
        self.setStyleSheet(f"""
            QMainWindow {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(26,32,44,0.97), stop:1 rgba(45,55,72,0.95));
            }}
            {MAIN_STYLE_SHEET}
        """)
        
        # Central
        central = QWidget()
        self.setCentralWidget(central)
        self.main_layout = QVBoxLayout(central)
        self.main_layout.setContentsMargins(25, 20, 25, 30)
        self.main_layout.setSpacing(25)
        
        # Header
        self.create_header()
        
        # Filtros
        self.create_filters()
        
        # Tabla
        self.create_table()
        
        # Formulario agregar
        if not self.read_only:
            self.create_form()
        
        # Cargar datos
        self.load_data()
        
    def create_header(self):
        """Crea el header con título"""
        header = QLabel(f"Stock de {self.view_local}")
        header.setStyleSheet("color: #ffc107; font-size: 28px; font-weight: 900;")
        self.main_layout.addWidget(header)
        
    def create_filters(self):
        """Crea la sección de filtros"""
        filters_frame = QFrame()
        filters_frame.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255,255,255,0.12), stop:1 rgba(255,255,255,0.08));
                border: 1px solid rgba(255,255,255,0.15);
                border-radius: 20px;
                padding: 25px;
            }}
        """)
        
        layout = QVBoxLayout(filters_frame)
        
        # Título
        title = QLabel("🔍 Filtros de Búsqueda")
        title.setStyleSheet("color: #ffc107; font-size: 18px; font-weight: 900;")
        layout.addWidget(title)
        
        # Fila de filtros
        row = QHBoxLayout()
        
        # Búsqueda
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar producto...")
        self.search_input.setFixedWidth(300)
        self.search_input.textChanged.connect(self.on_search_changed)
        row.addWidget(self.search_input)
        
        # Categoría
        self.category_combo = QComboBox()
        self.category_combo.addItem("Todas las categorías")
        self.update_categories()
        self.category_combo.setFixedWidth(240)
        self.category_combo.currentIndexChanged.connect(self.load_data)
        row.addWidget(self.category_combo)
        
        # Medida
        self.size_combo = QComboBox()
        self.size_combo.addItems(["Medida"] + sm.ALLOWED_MEDIDAS)
        self.size_combo.setFixedWidth(160)
        self.size_combo.currentIndexChanged.connect(self.load_data)
        row.addWidget(self.size_combo)
        
        # Botón buscar
        btn = QPushButton("🔎 Buscar")
        btn.clicked.connect(self.load_data)
        btn.setFixedWidth(130)
        row.addWidget(btn)
        
        row.addStretch()
        layout.addLayout(row)
        
        self.main_layout.addWidget(filters_frame)
        
    def create_table(self):
        """Crea la tabla de productos"""
        self.loading_bar = QProgressBar()
        self.loading_bar.setVisible(False)
        self.main_layout.addWidget(self.loading_bar)
        
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Nombre", "Cantidad", "Categoría", "Medida", "Precio", "Acciones"])
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.resizeSection(1, 100)
        header.resizeSection(2, 180)
        header.resizeSection(3, 120)
        header.resizeSection(4, 130)
        header.resizeSection(5, 150)
        
        self.table.cellDoubleClicked.connect(self.on_cell_double_click)
        self.main_layout.addWidget(self.table)
        
    def create_form(self):
        """Crea el formulario para agregar productos"""
        form_frame = QFrame()
        form_frame.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255,255,255,0.12), stop:1 rgba(255,255,255,0.08));
                border: 1px solid rgba(255,255,255,0.15);
                border-radius: 20px;
                padding: 25px;
            }}
        """)
        
        layout = QVBoxLayout(form_frame)
        
        title = QLabel("➕ Agregar Producto")
        title.setStyleSheet("color: #ffc107; font-size: 18px; font-weight: 900;")
        layout.addWidget(title)
        
        row = QHBoxLayout()
        
        self.form_fields = {}
        
        # Nombre
        self.form_fields['nombre'] = QLineEdit()
        self.form_fields['nombre'].setPlaceholderText("Nombre")
        self.form_fields['nombre'].setFixedWidth(260)
        row.addWidget(self.form_fields['nombre'])
        
        # Categoría
        self.form_fields['categoria'] = QLineEdit()
        self.form_fields['categoria'].setPlaceholderText("Categoría")
        self.form_fields['categoria'].setFixedWidth(190)
        row.addWidget(self.form_fields['categoria'])
        
        # Medida
        self.form_fields['medida'] = QComboBox()
        self.form_fields['medida'].addItems(["Medida"] + sm.ALLOWED_MEDIDAS)
        self.form_fields['medida'].setFixedWidth(140)
        row.addWidget(self.form_fields['medida'])
        
        # Estado
        self.form_fields['estado'] = QComboBox()
        self.form_fields['estado'].addItems(ESTADOS)
        self.form_fields['estado'].setFixedWidth(160)
        row.addWidget(self.form_fields['estado'])
        
        # Cantidad
        self.form_fields['cantidad'] = QSpinBox()
        self.form_fields['cantidad'].setRange(1, 9999)
        self.form_fields['cantidad'].setFixedWidth(90)
        row.addWidget(self.form_fields['cantidad'])
        
        # Precio
        self.form_fields['precio'] = QLineEdit()
        self.form_fields['precio'].setPlaceholderText("Precio")
        self.form_fields['precio'].setFixedWidth(190)
        row.addWidget(self.form_fields['precio'])
        
        # Botón agregar
        self.add_btn = QPushButton("➕ Agregar")
        self.add_btn.clicked.connect(self.add_product)
        self.add_btn.setFixedWidth(130)
        row.addWidget(self.add_btn)
        
        row.addStretch()
        layout.addLayout(row)
        
        self.main_layout.addWidget(form_frame)
'''

print("Template created")
