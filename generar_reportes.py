#!/usr/bin/env python3
"""
Genera un reporte legible del análisis de duplicados en HTML y Markdown
"""

import json
import os


def generar_reporte_html(
    json_file="ANALISIS_DUPLICADOS.json", output_file="REPORTE_DUPLICADOS.html"
):
    """Genera un reporte HTML a partir del JSON."""
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error leyendo {json_file}: {e}")
        return

    html = (
        """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Análisis de Productos Duplicados - Manarey</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            color: #333;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.3);
            padding: 30px;
        }
        header {
            text-align: center;
            border-bottom: 3px solid #667eea;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }
        h1 {
            color: #667eea;
            margin-bottom: 10px;
            font-size: 2.5em;
        }
        .summary {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }
        .stat-card h3 {
            font-size: 2em;
            margin-bottom: 5px;
        }
        .stat-card p {
            font-size: 0.9em;
            opacity: 0.9;
        }
        .grupos {
            display: grid;
            gap: 20px;
        }
        .grupo {
            background: #f8f9fa;
            border-left: 5px solid #667eea;
            border-radius: 5px;
            padding: 20px;
            transition: all 0.3s ease;
        }
        .grupo:hover {
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.3);
            transform: translateY(-2px);
        }
        .grupo-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            border-bottom: 2px solid #e0e0e0;
            padding-bottom: 10px;
        }
        .grupo-titulo {
            font-size: 1.3em;
            font-weight: bold;
            color: #667eea;
        }
        .grupo-badge {
            background: #667eea;
            color: white;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 0.9em;
        }
        .info-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 15px;
            margin-bottom: 15px;
        }
        .info-item {
            background: white;
            padding: 12px;
            border-radius: 5px;
            border-left: 3px solid #764ba2;
        }
        .info-label {
            font-weight: bold;
            color: #666;
            font-size: 0.85em;
            text-transform: uppercase;
            margin-bottom: 5px;
        }
        .info-value {
            color: #333;
            font-size: 1em;
        }
        .productos-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }
        .productos-table th {
            background: #f0f0f0;
            padding: 10px;
            text-align: left;
            border-bottom: 2px solid #667eea;
            font-weight: 600;
            font-size: 0.9em;
        }
        .productos-table td {
            padding: 10px;
            border-bottom: 1px solid #e0e0e0;
        }
        .productos-table tr:hover {
            background: #f9f9f9;
        }
        .nombre {
            min-width: 200px;
        }
        .footer {
            text-align: center;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 2px solid #e0e0e0;
            color: #999;
            font-size: 0.9em;
        }
        .alerta {
            background: #fff3cd;
            border-left: 5px solid #ffc107;
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 5px;
        }
        .alerta strong {
            color: #856404;
        }
        @media print {
            body { background: white; }
            .container { box-shadow: none; }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🔍 Análisis de Duplicados de Productos</h1>
            <p>Manarey - Sistema de Inventario</p>
            <p style="font-size: 0.9em; color: #999;">Generado: """
        + data["timestamp"]
        + """</p>
        </header>
        
        <div class="alerta">
            <strong>⚠️ Importancia:</strong> Se encontraron """
        + str(data["total_grupos"])
        + """ grupos de productos que parecen ser los mismos pero con nombres diferentes o duplicados. 
            Esto puede causar inconsistencia en el inventario. Se recomienda revisar y consolidar.
        </div>
        
        <div class="summary">
            <div class="stat-card">
                <h3>"""
        + str(data["total_grupos"])
        + """</h3>
                <p>Grupos de Duplicados</p>
            </div>
            <div class="stat-card">
                <h3>"""
        + str(sum([len(g["productos_detalle"]) for g in data["grupos"]]))
        + """</h3>
                <p>Productos Involucrados</p>
            </div>
            <div class="stat-card">
                <h3>"""
        + str(
            len(
                set(
                    [p["local"] for g in data["grupos"] for p in g["productos_detalle"]]
                )
            )
        )
        + """</h3>
                <p>Locales Afectados</p>
            </div>
        </div>
        
        <div class="grupos">
"""
    )

    # Agregar grupos
    for grupo in data["grupos"][:100]:  # Limitar a 100 para no hacer HTML muy grande
        html += f"""
        <div class="grupo">
            <div class="grupo-header">
                <span class="grupo-titulo">Grupo {grupo['grupo_id']}</span>
                <span class="grupo-badge">{grupo['cantidad_productos']} productos</span>
            </div>
            
            <div class="info-grid">
                <div class="info-item">
                    <div class="info-label">📦 Nombres</div>
                    <div class="info-value">{', '.join(grupo['nombres_diferentes']) if grupo['nombres_diferentes'] else 'Sin nombre'}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">📂 Categorías</div>
                    <div class="info-value">{', '.join(grupo['categorias'])}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">🏪 Locales</div>
                    <div class="info-value">{', '.join(grupo['locales'])}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">📊 Stock Total</div>
                    <div class="info-value">{grupo['cantidad_total']} unidades</div>
                </div>
                <div class="info-item">
                    <div class="info-label">💰 Rango de Precios</div>
                    <div class="info-value">${min([p['precio'] for p in grupo['productos_detalle']]):.2f} - ${max([p['precio'] for p in grupo['productos_detalle']]):.2f}</div>
                </div>
            </div>
            
            <table class="productos-table">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th class="nombre">Nombre</th>
                        <th>Local</th>
                        <th>Categoría</th>
                        <th>Stock</th>
                        <th>Precio</th>
                        <th>Fabricante</th>
                    </tr>
                </thead>
                <tbody>
"""
        for prod in grupo["productos_detalle"]:
            html += f"""
                    <tr>
                        <td>{prod['id']}</td>
                        <td class="nombre"><strong>{prod['nombre']}</strong></td>
                        <td>{prod['local']}</td>
                        <td>{prod['categoria']}</td>
                        <td>{prod['cantidad']}</td>
                        <td>${prod['precio']:.2f}</td>
                        <td>{prod['fabricante'] or '-'}</td>
                    </tr>
"""
        html += """
                </tbody>
            </table>
        </div>
"""

    html += """
        </div>
        
        <div class="footer">
            <p>Este análisis utiliza similitud de strings (72%) para identificar productos potencialmente duplicados.</p>
            <p>Revisar manualmente antes de consolidar productos.</p>
        </div>
    </div>
</body>
</html>
"""

    try:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"✅ Reporte HTML generado: {output_file}")
    except Exception as e:
        print(f"Error generando HTML: {e}")


def generar_reporte_markdown(
    json_file="ANALISIS_DUPLICADOS.json", output_file="REPORTE_DUPLICADOS.md"
):
    """Genera un reporte Markdown."""
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error leyendo {json_file}: {e}")
        return

    md = f"""# 🔍 Análisis de Productos Duplicados - Manarey

**Fecha:** {data['timestamp']}  
**Total de Grupos:** {data['total_grupos']}  
**Total de Productos Involucrados:** {sum([len(g['productos_detalle']) for g in data['grupos']])}

---

## 📊 Resumen

Se encontraron **{data['total_grupos']} grupos** de productos que parecen ser los mismos pero con:
- Nombres diferentes o variaciones
- Presentes en múltiples locales
- Precios distintos
- Potencialmente duplicados en el sistema

## ⚠️ Recomendaciones

1. Revisar cada grupo de productos
2. Consolidar o enladrillar productos duplicados
3. Mantener un solo registro por producto único
4. Sincronizar precios entre locales

---

## 📋 Grupos Identificados

"""

    for grupo in data["grupos"][:50]:  # Primeros 50 grupos para el markdown
        md += f"""
### Grupo {grupo['grupo_id']} - {grupo['cantidad_productos']} Productos

**Nombres encontrados:** {', '.join(grupo['nombres_diferentes']) if grupo['nombres_diferentes'] else 'Sin nombre'}

| Atributo | Valores |
|----------|---------|
| **Categorías** | {', '.join(grupo['categorias'])} |
| **Locales** | {', '.join(grupo['locales'])} |
| **Stock Total** | {grupo['cantidad_total']} unidades |
| **Rango Precios** | ${min([p['precio'] for p in grupo['productos_detalle']]):.2f} - ${max([p['precio'] for p in grupo['productos_detalle']]):.2f} |

#### Detalle de Productos:

| ID | Nombre | Local | Categoría | Stock | Precio | Fabricante |
|----|--------|-------|-----------|-------|--------|-----------|
"""
        for prod in grupo["productos_detalle"]:
            md += f"| {prod['id']} | {prod['nombre']} | {prod['local']} | {prod['categoria']} | {prod['cantidad']} | ${prod['precio']:.2f} | {prod['fabricante'] or '-'} |\n"

        md += "\n"

    md += f"""
---

## 📁 Archivos Generados

- **ANALISIS_DUPLICADOS.json** - Datos completos en formato JSON
- **REPORTE_DUPLICADOS.html** - Reporte interactivo en HTML
- **REPORTE_DUPLICADOS.md** - Este documento

---

*Análisis generado automáticamente por el sistema Manarey*
"""

    try:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"✅ Reporte Markdown generado: {output_file}")
    except Exception as e:
        print(f"Error generando Markdown: {e}")


if __name__ == "__main__":
    os.chdir(os.path.dirname(__file__) or ".")

    print("Generando reportes...")
    generar_reporte_html()
    generar_reporte_markdown()
    print("\n✅ Todos los reportes han sido generados exitosamente")
