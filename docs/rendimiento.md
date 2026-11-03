# Auditoría de rendimiento — 2 de noviembre de 2026

Contexto: Vercel, 8–10 usuarios simultáneos. Se revisaron las rutas, configuración,
plantillas y recursos del repositorio, junto con metadatos, índices, funciones y
estadísticas de rendimiento del proyecto StellarTools en Supabase. Las consultas
a producción fueron de lectura; no se modificaron datos, funciones ni índices.
No se midieron aún TTFB, LCP o INP de la aplicación desplegada.

## Cambios aplicados

| Área | Cambio | Efecto esperado |
| --- | --- | --- |
| Todas las pantallas | Tailwind 3.4.17 compilado y minificado antes del despliegue | Elimina la descarga y ejecución del compilador CSS en cada apertura |
| Estilos generados | Escaneo de HTML, JavaScript y clases definidas en Python | Conserva utilidades de filas, modales, estados y contenido dinámico |
| Vercel | `tool.vercel.fastapi.static.cdn = true` | Permite servir `/static` desde el CDN pese a los middlewares globales |
| Respuestas de la función | GZip nivel 5 a partir de 1.000 bytes | Reduce transferencia cuando el cliente admite gzip; respeta respuestas ya comprimidas |
| Recursos versionados | Caché HTTP de un año con `immutable` cuando pasan por FastAPI | Evita revalidaciones de URLs que ya cambian por despliegue y revisión |
| Recursos sin versión | Revalidación HTTP y conservación de ETag/304 | Permite actualizar URLs antiguas |
| Service worker | Caché primero para recursos con revisión; los demás se revalidan | Evita que una visita lance de nuevo todas las descargas en segundo plano |
| Sesiones | Los archivos públicos omiten lectura/renovación de sesión | Evita asociar cookies de sesión a respuestas estáticas |
| Arranque | pandas y pdfplumber se importan al utilizarlos | Las pantallas comunes no cargan los motores de planillas/PDF |
| Análisis | SDK Supabase del navegador eliminado: no tenía consumidores | Elimina descarga e inicialización sin uso; conserva las llamadas al backend |
| Análisis e inventario nuevo | Una sola carga del componente de modales | Conserva su posición original antes de los scripts de cada pantalla |
| Perfil | Una sola carga de Alpine | Evita inicializaciones duplicadas |
| Login | Fondo con URL versionada | Reutiliza la misma política de caché que las otras pantallas |

Las páginas privadas y APIs mantienen `no-store`. La validación de usuario, rol y
tienda continúa en cada petición; no se introdujo una caché de autorizaciones.
La primera importación de planillas o PDF asume el coste de cargar su motor.

## Tamaños reproducibles

Ejecutar `python scripts/auditar_recursos.py`. Ejemplos de compresión local:

| Fuente | Bytes originales | Bytes gzip nivel 5 |
| --- | ---: | ---: |
| inventario_nuevo.html | 263.839 | 35.164 |
| inventario.html | 128.570 | 23.114 |
| analisis_pedido.html | 80.067 | 14.442 |
| ordenes.html | 73.059 | 15.607 |
| CSS compilado | ~58.000 | ~10.300 |

Son tamaños de fuentes, no respuestas HTML renderizadas. Los datos y el contexto
Jinja cambian el tamaño final. Tampoco demuestran una mejora porcentual del tiempo
total de navegación. Vercel puede comprimir ya parte de las respuestas.

## Evidencia real de Supabase

`pg_stat_user_tables` estima 3.319.872 filas en ventas_kardex, 14.498 productos,
11.965 detalles de inventario, 9.889 detalles de órdenes, 1.499 órdenes y
703 proveedores. Son estimaciones de estadísticas, no conteos exactos.

Las estadísticas de `pg_stat_statements` se acumulan desde el 7 de agosto de 2026.
Incluyen versiones anteriores, diagnósticos y mantenimiento. No equivalen a la
latencia actual de una pantalla, ni permiten deducir el percentil 95.

| RPC observada | Llamadas | Media histórica en BD | Máximo histórico |
| --- | ---: | ---: | ---: |
| obtener_demanda_kardex | 2.439 | 824 ms | 7.951 ms |
| obtener_demanda_comercial_kardex | 185 | 2.320 ms | 7.747 ms |
| obtener_cobertura_kardex | 613 | 1.076 ms | 7.944 ms |
| obtener_ventas_semanales_sugeridos_lote | 143 | 491 ms | 2.508 ms |

La definición **actual** de cobertura ya lee una tabla resumen de seis sedes;
su media histórica no demuestra que esa versión siga siendo lenta. La demanda
simple ya exige códigos y dispone de un índice parcial por código/fecha con
columnas incluidas. La demanda comercial todavía calcula días cubiertos a partir
de las ventas de todos los productos del período y expande pares sede/producto por
calendario. Esa cobertura forma parte del cálculo: restringirla a los productos
seleccionados cambiaría resultados y no es una optimización equivalente.

El asesor de rendimiento informa tres claves foráneas sin índice:
analisis_pedidos.proveedor_id, analisis_pedidos_detalle.producto_id y
programacion_reposicion.usuario_id. Afectan tablas pequeñas; no son evidencia del
principal cuello de botella. También informa que ventas_kardex no tiene clave
primaria, aunque sí tiene un índice único compuesto. No corresponde añadir una
clave nueva automáticamente sin revisar nulabilidad, duplicados y escritura.
Referencias de los avisos: [FK sin índice](https://supabase.com/docs/guides/database/database-linter?lint=0001_unindexed_foreign_keys)
y [sin clave primaria](https://supabase.com/docs/guides/database/database-linter?lint=0004_no_primary_key).

## Siguientes mejoras, por prioridad

| Prioridad | Pantalla/área | Hallazgo y trabajo concreto |
| --- | --- | --- |
| Alta | Kardex/comparaciones | Medir planes actuales con rangos y cantidades representativas; evaluar cobertura diaria por sede precalculada, actualizada junto a las importaciones. Comparar resultados exactos de demanda regular/alta y días cubiertos antes de cambiar la RPC |
| Alta | Órdenes | El listado trae todos los documentos y sus productos. Cargar detalles al abrirlos y paginar en servidor reducirá consulta, HTML y DOM. Requiere conservar filtros, selección visible y eliminación del subconjunto seleccionado |
| Alta | Perfil/categorías | Hay `.execute()` síncronos dentro de handlers async. Pasar esas operaciones a cliente async o a un hilo evitaría bloquear otras peticiones; conservar las restricciones por usuario y cubrir lectura/escritura con pruebas |
| Media | Inventario nuevo e inventario | Las fuentes pesan ~264 KB y ~129 KB. Extraer JS/CSS inline a recursos versionados permitiría reutilizarlos entre documentos. Hacerlo por bloques con pruebas de fórmulas, guardado, importaciones y permisos; no minificar o reescribir lógica manualmente |
| Media | Proveedores | La interfaz muestra 20, pero el servidor lee y filtra los 703 proveedores. Trasladar paginación/búsqueda a BD manteniendo búsqueda sin acentos, categorías y criterios acumulados. Con el volumen actual no es la primera prioridad |
| Media | Productos | Ya pagina 20 en servidor; cada badge añade búsquedas auxiliares de proveedor y cada petición vuelve a cargar opciones del formulario. Medir antes de agrupar consultas o separar fragmento de listado/ficha |
| Media | Dashboard/notificaciones | Recorren órdenes y grupos para calcular reposición. Ya existe caché de cliente por usuario/tienda y actualización cada minuto. Un resumen en servidor debe invalidarse al cambiar órdenes y al avanzar la fecha, preservando reaparición y descarte de avisos |
| Media | Región | Supabase está en us-west-2. Verificar la región efectiva de la función en Vercel y medir red función–BD antes de trasladarla. No se cambió región ni plan |
| Baja | Calendario | El rango del API ya está limitado a 62 días; revisar coste real de recurrencias al crecer programaciones |
| Baja | Usuarios/inicio/login | Consultas iniciales reducidas; reciben las mejoras globales. Mantener permisos administrativos y aislamiento de sesión |
| Baja | Recursos externos/fondo | Font Awesome y Alpine siguen externos; considerar versiones locales tras medir la red. El fondo JPEG pesa ~308 KB; evaluar una variante optimizada conservando su aspecto |

No se agregaron índices a ciegas ni caché global de clientes autenticados. El
siguiente paso de medición debe separar autenticación, red, consulta, render Jinja,
transferencia y trabajo del navegador: reducir bytes no elimina un RPC lento.

## Compilación y despliegue

Corrección del 3 de noviembre: Vercel selecciona `pyproject.toml` para instalar
dependencias cuando está presente. Este archivo declara ahora las mismas
dependencias que `requirements.txt`, Python 3.12 y `tool.uv.package = false`.
El manifiesto anterior solo contenía ajustes del build y podía dejar fuera las
dependencias necesarias para importar la aplicación y recopilar sus estáticos.
La confirmación de la recopilación CDN requiere un nuevo build en Vercel.

El CSS generado está incluido en el repositorio. Para modificar clases:

```sh
npm ci --include=dev --ignore-scripts
npm run build:css
```

En PowerShell usar `npm.cmd` si la política local bloquea `npm.ps1`.
El script de build de `pyproject.toml` instala las herramientas y recompila antes
del despliegue. Un Build Command configurado en Vercel o vercel.json tiene
precedencia: comprobar que no omita este paso. Mantener el preset FastAPI.
No se realizó un despliegue desde esta sesión. Conservar `exclude = false`:
`asset_url` necesita leer metadatos de los archivos dentro de la función.

Después de desplegar: comprobar CDN/cache y `Content-Encoding` de recursos;
medir primera visita y visita repetida, escritorio y móvil, con 8–10 sesiones de
prueba. Registrar TTFB, LCP, INP, solicitudes y bytes, y latencias p50/p95 de APIs.
Usar documentos de prueba para operaciones de escritura.

## Verificación

- 108 pruebas JavaScript y 61 pruebas Python aprobadas.
- Edge con HTML real y API local simulada: CSS compilado, colores, espaciado,
  visibilidad, proveedor, productos, cálculos, tiendas, sugeridos, guardado,
  restauración, XML/TXT, importador, comparación, confirmaciones y filas manuales.
- Pruebas de gzip, ETag/304, caché versionada, recursos inexistentes, sesión privada,
  actualización de revisión y fallo de almacenamiento del service worker.
- Limitación local: NumPy instalado falla por requisito de CPU X86_V2. Impide
  comprobar el motor pandas/lectura de planillas y medir su coste de arranque en
  este equipo; no se cambió la instalación global ni se afirma validación de ese flujo.

Fuentes: [Tailwind: configuración de contenido](https://v3.tailwindcss.com/docs/content-configuration),
[Vercel: FastAPI, build y recursos estáticos](https://vercel.com/docs/frameworks/backend/fastapi),
[Supabase: optimización y planes](https://supabase.com/docs/guides/database/query-optimization).
