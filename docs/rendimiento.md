# Auditoría de rendimiento — 2 de noviembre de 2026

Contexto: Vercel, 8–10 usuarios simultáneos. Se revisaron las rutas, configuración,
plantillas y recursos del repositorio, junto con metadatos, índices, funciones y
estadísticas de rendimiento del proyecto StellarTools en Supabase. La primera
auditoría fue de lectura. En la continuación del 3 de noviembre se optimizó la
función de demanda comercial, con pruebas de equivalencia y respaldo; no se
modificaron registros ni índices.
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

Estado actualizado del 3 de noviembre: los cuatro frentes principales (Órdenes,
Inventario, Perfil y demanda comercial de Kardex) ya se trabajaron. El detalle
y las limitaciones están en la sección siguiente. Las otras filas de esta tabla
son oportunidades condicionadas a mediciones, no cambios pendientes obligatorios.

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

El usuario confirmó posteriormente que la aplicación ya funciona en Vercel.
Los cambios de la continuación requieren otro despliegue del repositorio;
la función SQL de demanda comercial ya está aplicada en Supabase.

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

- 110 pruebas JavaScript y 69 pruebas Python aprobadas en la continuación.
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

## Continuación aplicada — 3 de noviembre de 2026

### Órdenes

El listado solicita únicamente cabeceras y devuelve 20 documentos por página.
Los detalles de productos se solicitan al desplegar cada orden, se conservan
mientras esa fila siga en pantalla y permiten cerrar/reintentar si hay un error.
El fragmento reutiliza el HTML y las fórmulas Jinja originales de cantidades,
presentaciones, empaques, costos y subtotales. El nuevo endpoint exige identidad
y filtra tanto por ID de orden como por usuario.

La búsqueda y la paginación actualizan solo el listado, conservando el buscador,
los badges y el modo de selección. Las solicitudes anteriores se cancelan y sus
respuestas tardías no reemplazan resultados nuevos. Escribir mantiene el filtro
visual inmediato y espera 350 ms antes de consultar. Seleccionar todo y eliminar
se limitan a las filas visibles de la página actual; la confirmación vuelve a
validar la selección si el listado cambió.

Límite de la primera etapa, resuelto en la etapa SQL descrita más abajo:
para conservar la búsqueda en todos los campos visuales,
incluidos vencimiento calculado y monto formateado, el servidor lee las cabeceras
del usuario en bloques de 1.000 y filtra antes de paginar. No descarga los productos
de todas las órdenes. Por tanto, la paginación limita HTML/DOM y detalle, pero aún
no limita a 20 las cabeceras leídas de la BD. El caso de más de 1.000 documentos
y la búsqueda fuera de la página inicial están cubiertos por pruebas.

### Inventario

Se extrajeron diez bloques JS y cuatro CSS a recursos versionados, conservando
su texto, orden y ámbito global. No se reescribieron cálculos ni eventos.
Comparación del HTML original y actual excluyendo únicamente scripts/estilos:
idéntica. Checksums de los bloques normalizados en LF registrados en
`tests/inventario-migracion.json`.

Tamaños de fuentes HTML normalizadas en LF:

| Plantilla | Antes | Después |
| --- | ---: | ---: |
| inventario.html | 124.728 bytes | 36.873 bytes |
| inventario_nuevo.html | 255.379 bytes | 48.279 bytes |

La lógica sigue descargándose en la primera visita, pero queda en archivos
reutilizables por caché/CDN entre documentos. Estas cifras no representan el
porcentaje de mejora del tiempo completo de navegación.

### Perfil y categorías

Las consultas síncronas de lectura del perfil/categorías y creación, edición y
eliminación de categorías se ejecutan con `run_in_threadpool`, igual que el
guardado de perfil existente. Conservan filtros por usuario y respuestas.
Las pruebas verifican que las cinco ejecuciones ocurran fuera del hilo del bucle
de eventos y mantengan el usuario en las restricciones de acceso.

### Kardex: cambio ya aplicado en Supabase

`obtener_demanda_comercial_kardex` ya no obtiene días cubiertos recorriendo todas
las ventas del intervalo. Obtiene las sedes de los productos con ventas, recorre
el calendario y comprueba si existe alguna venta positiva de cualquier producto
en esa sede/día, usando el índice existente por sede/fecha. Materializa esa
cobertura una vez por consulta para reutilizarla entre productos. No restringe
los días cubiertos a los códigos seleccionados y no introduce un resumen que
pueda quedar desactualizado tras importar datos.

Se conservaron parámetros, columnas devueltas, validación de fechas, cantidades,
semanas regulares/altas, división, orden, propietario, `search_path` y permisos.
La función sigue siendo invoker y solo postgres/service_role pueden ejecutarla.
No hubo cambios de índices, tablas ni políticas RLS.

Medición comparable de la RPC completa con dos productos y octubre de 2026:

| Métrica | Antes | Después |
| --- | ---: | ---: |
| Tiempo de ejecución en BD | 10.249,500 ms | 733,883 ms |
| Filas devueltas | 7 | 7 |
| Bloques compartidos encontrados en caché | 484.603 | 2.004 |
| Bloques leídos | 3.630 | 233 |

Fue una medición por versión, con estados de caché distintos. Demuestra menor
trabajo en esta muestra, no una garantía de 14× para toda la aplicación ni un p95.
La consulta aislada de cobertura anterior tardó 24.782 ms; no se comparó ese
subcomponente con la RPC completa para calcular la mejora.

La comparación bidireccional con `EXCEPT ALL` dio cero diferencias con datos
reales. Otra prueba con datos sintéticos también dio cero diferencias, incluyendo
días cubiertos por otros productos, productos sin ventas, códigos repetidos,
cantidades cero/negativas, sede nula, nombres de sede distintos y cambio de mes.

Archivos reproducibles:

- `scripts/sql/kardex-demanda-comercial.sql`: definición optimizada aplicada.
- `scripts/sql/kardex-demanda-comercial-rollback.sql`: definición anterior.
- `scripts/sql/verificar-demanda-comercial.sql`: comparación con datos sintéticos,
  solo lectura; debe devolver cero diferencias y cuatro días cubiertos en CENTRO.

### Verificación de la continuación

`python tests/optimizaciones_navegador.py` abre Edge y sirve las plantillas y
recursos reales con APIs locales simuladas. Verifica paginación de órdenes,
búsqueda fuera de página, detalle bajo demanda, reutilización y reintento tras
error, selección y cancelación de confirmación; modales de inventario, filas,
duplicados, cantidades por ubicación, guardado y vista móvil. No escribe en BD.

Las pruebas unitarias adicionales cubren respuestas tardías y recuperación del
listado, aislamiento por usuario del detalle, escape HTML y consultas no bloqueantes.
La revisión de asesores de Supabase no exigió cambiar permisos para esta mejora.

## Paginación en la base de datos — 3 de noviembre de 2026

Esta etapa elimina las lecturas completas de cabeceras de Órdenes y del directorio
de Proveedores desde las rutas Python. Ambas rutas llaman una RPC con el JWT del
usuario; SQL aplica los filtros, el orden, el conteo y `LIMIT 20 / OFFSET`.
La respuesta contiene una fila de metadatos con hasta 20 registros en su campo
JSON `registros`. El conteo puede examinar las filas que coinciden en BD, pero
esos registros ya no se transfieren completos al servidor de la aplicación.

Se conservaron:

- Órdenes: texto, badges combinados, coincidencia por fecha de envío o recepción,
  vencimiento calculado, monto con formato latino, orden estable por fecha/ID,
  detalle bajo demanda y selección limitada a filas visibles.
- Proveedores: código, nombre, contacto, teléfono, correo, categorías, búsqueda
  sin acentos, orden ascendente/descendente y desempate por ID. `%` y `_` siguen
  siendo caracteres literales, no comodines SQL.
- La ficha de proveedor puede estar fuera de la página y del filtro. Se devuelve
  solo esa ficha adicional, junto con una lista compacta de etiquetas para el
  buscador. Las categorías editables del usuario siguen en su consulta existente.

La normalización SQL reproduce NFD, eliminación de marcas Mn y `casefold`, con
tablas Unicode generadas por `scripts/generar_normalizacion_listados.py`.
El generador no se ejecuta durante las peticiones ni durante el build de Vercel.
Los nombres habituales en español usan una rama rápida ASCII después de retirar
los acentos. El formato de monto reproduce el redondeo del float binario de
Python, incluidos casos como 2.675, y no modifica montos almacenados ni fórmulas.
Las aperturas sin criterios evitan calcular ese texto de búsqueda para cada orden.

### Verificación real y límites de las mediciones

Con un usuario normal, usando el rol `authenticated` y sus políticas RLS reales:

| Listado | Registros totales visibles | Registros devueltos | Tamaño JSON de esos registros |
| --- | ---: | ---: | ---: |
| Órdenes | 976 | 20 | 6.296 bytes |
| Proveedores | 703 | 20 | 4.921 bytes |

Proveedores devolvió además 44 etiquetas distintas. Un usuario provisional no
obtuvo órdenes. Las RPCs son `SECURITY INVOKER`, tienen `search_path` vacío,
requieren identidad y no permiten ejecución anónima. Órdenes restringe además
explícitamente `usuario_id = auth.uid()`. No se cambiaron datos de clientes,
políticas, tablas ni índices; solo se añadieron funciones de lectura.

Un `EXPLAIN ANALYZE` de la RPC de Órdenes sin filtros dio 18,235 ms después de
evitar el formato de búsqueda innecesario; Proveedores dio 39,749 ms en la muestra.
Son ejecuciones aisladas de BD, con compilación/caché variables, no tiempos de
navegación ni percentiles de producción. Los tamaños JSON tampoco equivalen a
bytes HTTP comprimidos ni incluyen todo el HTML de la página.

Pasaron 70 pruebas Python y 110 JavaScript. El navegador con API local simulada
verificó también Proveedores: paginación, badges por categoría/acento y ficha fuera
del filtro. Las pruebas SQL ejecutaron 1.025 proveedores y 1.025 órdenes sintéticas,
otra identidad y permisos anónimos, dentro de tablas temporales y con `ROLLBACK`.
También compararon normalización Unicode y 111 valores monetarios con Python.
Los stubs de las pruebas de interfaz no sustituyen esa verificación real de SQL.

### Instalación y reversión

Las funciones de esta etapa ya se instalaron y verificaron en el proyecto
StellarTools de Supabase. Falta desplegar las rutas actualizadas en Vercel para
que la aplicación las use. El backend anterior sigue funcionando con estas
funciones adicionales presentes.

Para reproducir la preparación en otro entorno, generar SQL en archivos UTF-8:

```sh
python scripts/verificar_listados_sql.py --tipo verificacion --salida prueba-listados.sql
python scripts/verificar_listados_sql.py --tipo instalacion --salida instalar-listados.sql
```

El script solo genera archivos; no abre conexiones. El archivo de verificación
usa datos temporales y termina en `ROLLBACK`. El de instalación aplica las dos
fuentes SQL y sus permisos en una transacción y notifica la recarga del esquema
a PostgREST. Instalar las funciones antes de desplegar el nuevo backend.
En una reversión, desplegar primero las rutas anteriores; el archivo
`scripts/sql/listados-paginados-rollback.sql` retira únicamente estas funciones
nuevas, sin tocar registros ni la optimización de Kardex.
