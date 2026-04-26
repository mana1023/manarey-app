-- ========================================
-- LIMPIAR CONEXIONES EN SUPABASE
-- Ejecutá estas queries en el SQL Editor
-- ========================================

-- 1. Ver cuántas conexiones hay actualmente
SELECT count(*) as total_conexiones FROM pg_stat_activity;

-- 2. Ver detalles de las conexiones (quién está conectado)
SELECT 
    pid,
    usename,
    application_name,
    client_addr,
    state,
    state_change
FROM pg_stat_activity
ORDER BY state_change DESC;

-- 3. TERMINAR conexiones inactivas (idle) que NO sean de Supabase
-- CUIDADO: Solo ejecutá esto si estás seguro
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle'
  AND pid != pg_backend_pid()  -- No terminar tu propia conexión
  AND usename NOT IN ('supabase_admin', 'supabase_storage_admin', 'postgres')
  AND application_name NOT LIKE '%supabase%';

-- 4. Verificar conexiones restantes
SELECT count(*) as conexiones_restantes FROM pg_stat_activity;

-- 5. (OPCIONAL - SOLO SI LO ANTERIOR NO FUNCIONÓ)
-- Terminar TODAS las conexiones que no sean del sistema
-- ⚠️ ADVERTENCIA: Esto puede interrumpir otros servicios
/*
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE pid != pg_backend_pid()
  AND datname = 'postgres'
  AND usename NOT IN ('supabase_admin', 'supabase_storage_admin');
*/
