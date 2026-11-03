# shop-calendar
Calendario de Compras COMEVAL.

Los estilos Tailwind se compilan antes del despliegue. Al agregar o modificar
clases en HTML, JavaScript o Python, ejecutar `npm ci` y `npm run build:css`
(en PowerShell, `npm.cmd` si la política bloquea `npm.ps1`). Incluir el CSS
generado en el commit. Conservar nombres completos de clases en las fuentes.

La configuración de Vercel recompila los estilos y habilita CDN para `/static`.
La auditoría, mediciones, pruebas y siguientes mejoras están en
[docs/rendimiento.md](docs/rendimiento.md).
