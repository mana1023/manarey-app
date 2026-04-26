# 🧪 TEST DEL INSTALADOR - ANTES DE DISTRIBUIR

## ⚠️ IMPORTANTE: Probá el instalador en tu PC primero

Antes de enviar el instalador a otras PCs, verificá que funcione correctamente.

---

## 📋 Pasos para Probar

### 1. **Cerrar Manarey** (si está abierto)

### 2. **Desinstalar versión actual** (si la tenés)
   - Panel de Control → Programas y características
   - Buscar "Manarey" y desinstalar

### 3. **Instalar la versión nueva**
   - Ejecutar `Manarey-Setup-1.0.1.exe`
   - Seguir el asistente (Next → Install → Finish)

### 4. **Abrir Manarey desde el escritorio**

### 5. **Verificar mensaje de consola** (si aparece ventana cmd)
   - Debe decir: `✓ Configurado para usar PostgreSQL/Supabase`
   - **NO** debe decir: `✓ Configurado para usar SQLite local`

### 6. **Iniciar sesión con**:
   ```
   Usuario: Administrador
   Contraseña: lautaro10
   ```

### 7. **Verificar que entra correctamente**

---

## ✅ Si Funciona

**Resultado esperado:**
- ✅ Login exitoso
- ✅ Puedes ver productos/ventas (si ya tenías datos)
- ✅ Puedes agregar/editar sin problemas

**Próximo paso:**
→ Distribuir `Manarey-Setup-1.0.1.exe` a otras PCs

---

## ❌ Si NO Funciona

**Síntoma:** Dice "Usuario o contraseña incorrectos"

**Causas posibles:**

### A) No está usando Supabase

**Verificar:**
1. Ir a: `%LOCALAPPDATA%\Manarey\`
2. Abrir `config.json`
3. Debe decir:
   ```json
   {
     "database_type": "postgresql",
     "database_url": "postgresql://postgres.bcdgkbptzogowbexcybn:Manarey10@..."
   }
   ```

**Si NO dice eso:**
→ Ejecutar `CONFIGURAR_SUPABASE.bat`
→ Reintentar login

### B) Supabase no tiene usuarios

**Verificar:**
```bash
cd C:\Users\USUARIO\Desktop\Manarey
.venv\Scripts\python.exe listar_usuarios.py
```

**Debe mostrar:**
- Administrador
- cane
- vidriera
- longchamps

**Si NO aparecen:**
→ Ejecutar:
```bash
.venv\Scripts\python.exe inicializar_supabase.py
```

### C) Sin internet

Supabase necesita conexión a internet.

**Verificar:**
- Abrir cualquier página web
- Si funciona, el problema es otro

---

## 🔍 Debug Avanzado

Si ninguna de las anteriores funciona:

### Opción 1: Verificar logs

Cuando abras Manarey, debe aparecer una ventana de consola (cmd) con mensajes.

**Buscar:**
- `✓ Configurado para usar PostgreSQL/Supabase` → BIEN
- `✓ Configurado para usar SQLite local` → MAL (no está usando Supabase)
- `Base Postgres detectada` → BIEN

### Opción 2: Probar conexión manual

```bash
cd C:\Users\USUARIO\Desktop\Manarey
.venv\Scripts\python.exe prueba_conexion.py
```

Debe decir `✅ CONEXIÓN EXITOSA!`

---

## 📊 Checklist Final

Antes de distribuir, verificar:

- [ ] Instalador ejecuta sin errores
- [ ] Manarey abre correctamente
- [ ] Login con "Administrador" / "lautaro10" funciona
- [ ] Login con "cane" / "Manarey10" funciona
- [ ] Puedes agregar un producto de prueba
- [ ] El producto se guarda correctamente
- [ ] `config.json` existe en `%LOCALAPPDATA%\Manarey\`
- [ ] `config.json` tiene la URL de Supabase correcta

Si TODOS están ✓ → **Listo para distribuir!**

---

## 🎯 Después de Verificar

Una vez que confirmaste que funciona en tu PC:

1. **Distribuir archivos:**
   - `Manarey-Setup-1.0.1.exe` (principal)
   - `CONFIGURAR_SUPABASE.bat` (por si acaso)
   - `LEEME_IMPORTANTE.txt` (instrucciones)

2. **Enviar por:**
   - Google Drive / Dropbox (recomendado)
   - WhatsApp (puede corromper archivo grande)
   - Pen drive USB
   - Red local compartida

3. **Instrucciones para el destinatario:**
   - Ejecutar el instalador
   - Abrir Manarey
   - Iniciar sesión con sus credenciales

---

## 💡 Tip

Si vas a instalar en muchas PCs, hacé el test completo en 2-3 PCs diferentes primero para estar seguro.

---

**¡Éxito!** 🚀
