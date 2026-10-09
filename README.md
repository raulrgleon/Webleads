# WebLeads · DNET

Herramienta privada de captación de clientes en **https://webleads.dnet.llc**. Encuentra negocios locales, revisa sus datos y organiza oportunidades compartidas con el equipo. Marca una ausencia de web como **por verificar**; no presume que el negocio carece de página ni que está abierto.

## Funciones

- Búsqueda de 16 sectores por ubicación y radios de 2, 5, 10 o 20 km. Dentistas y fisioterapeutas tienen consultas específicas; shop/office/healthcare/leisure/tourism no se confunden con amenity.
- Hasta 200 resultados de OpenStreetMap con mapa, teléfono, correo, web y fuente cuando estén registrados. Soporta etiquetas `contact:*`. Excluye cierres explícitos en los datos; actividad restante pendiente de revisión. Cobertura variable, sin reseñas, sin Google Maps, sin Hunter y sin correos inventados.
- Filtro de web encontrada/por verificar. Comprobación manual: sin web confirmada o web deficiente. No analiza automáticamente las webs ni comprueba su rendimiento.
- Prospectos compartidos y persistentes, sin duplicados por ID, responsables, notas y etapas detectado/revisado/contactado/propuesta/ganado/perdido.
- Registro manual y migración de hasta 200 registros de localStorage del **mismo dominio/navegador**, siempre como datos no verificados. No puede leer historial privado de otros dominios.
- CSV con correo/fuente/estado y protección de fórmulas. Teléfonos se conservan sin añadir un +1 extra.
- Cuentas reales con contraseña, invitación privada de un solo uso (7 días) y sin registro público. Owner administra, Member busca/edita, Viewer consulta/exporta. Permisos y desactivación efectivos en cada solicitud.
- Sesiones privadas HttpOnly/Secure/SameSite, CSRF/Origin, límites de intentos/búsqueda, contraseñas PBKDF2-SHA256 (1M), CSP y renderizado seguro sin interpolación de HTML ajeno.
- Diseño DNET #2563A6, responsive, estados de carga y errores, favicon propio, 404, manifest instalable. SW solo cachea assets públicos; la búsqueda requiere internet y los datos privados no se guardan en CacheStorage. No se promete operación offline completa.
- Enlace a Workspace. Estado del despliegue registrado allí; **no hay sincronización automática de prospectos con su base de datos todavía**.

## Arquitectura y despliegue

Flask + Gunicorn (2 workers/2 threads), JavaScript/HTML/CSS, Leaflet 1.9.4, SQLite WAL. Cloudflare Tunnel existente DNET-HOME añade únicamente `webleads.dnet.llc → http://localhost:3210`. DNS CNAME proxied. Las demás rutas se conservan; no se reinician otras apps.

Docker Compose `/home/raul/webleads/compose.yaml`, app UID1000, puerto host solo127.0.0.1:3210, filesystem readonly salvo `/data`, cap_drop ALL, no-new-privileges, 256 MB / 0.5 CPU, healthcheck y logs rotados. Imagen `dnet-webleads:current`. Base persistente `/data/webleads/storage/webleads.sqlite`, configuración root600 `/data/webleads/runtime.env`, directorio root700. No datos ni secretos en GitHub ni directorio estático.

```sh
# Desarrollo
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
APP_URL=http://localhost:3210 DATA_DIR=./data python app.py

# Producción (configuración y propietario preparados previamente)
sudo docker compose build
sudo docker compose up -d
```

Variables: `APP_URL` (origen exacto, obligatorio para CSRF y cookies), `OWNER_EMAIL` (identidad administrativa documentada), `DATA_DIR` (ruta SQLite). Plantilla `.env.example`; Compose usa `/data/webleads/runtime.env`. No se requieren API keys para búsqueda OSM.

El primer acceso del propietario está en `/data/webleads/owner-activation.url` (root600): enlace privado de un solo uso hacia su correo, válido7d. Abrirlo y elegir nombre/contraseña≥12 caracteres. Las invitaciones de equipo se crean en **Equipo** y se comparten manualmente; la aplicación no envía emails de invitación ni tiene recuperación de contraseña automática. Si se pierde el acceso, un administrador del servidor debe preparar una recuperación controlada; no cambiar contraseñas directamente en producción sin autorización. No divulgar enlaces de activación ni ponerlos en Workspace/GitHub.

## Servicios externos y límites

Nominatim público identifica la ubicación: caché7d, serialización persistente entre workers y al menos1.1s entre solicitudes de la app. Búsquedas manuales, nunca barrido automático. Cumplir https://operations.osmfoundation.org/policies/nominatim/ (máximo1request/s sumando usuarios, atribución y caché). Overpass público consulta negocios, caché1h, límites de búsqueda por usuario y globales, timeout35s y error visible si proveedor falla. Proveedores públicos sin SLA; mantenerlos dentro de uso moderado y migrar a proveedor contratado o instancia propia si crece la demanda. Tiles públicos OSM con atribución; no descargar en masa. Leaflet servido desde CDN versionado; no envía datos privados a un servicio IA.

No confundir datos públicos con permiso para contactar. Revisar las preferencias del destinatario y las reglas de comunicaciones comerciales según el país. No se envían campañas ni se realizan llamadas automáticamente. La herramienta no ofrece métricas de ventas garantizadas ni inventa reseñas/testimonios/contactos.

## Backups y operación

`deploy/webleads-backup.service`/`.timer`: diariamente03:15UTC como root. `scripts/backup.py` usa SQLite backup API (snapshot consistente), empaqueta DB/config/enlace inicial y respaldo de túnel, cifra AES256CBC/PBKDF2 con `/data/webleads/backup.key` root600; guarda en `/data/webleads/backups`, conserva14archivos propios. Proteger y guardar la clave separada: no está dentro del archivo cifrado. Respaldos **locales**; copia externa sigue pendiente.

```sh
sudo systemctl start webleads-backup.service
sudo journalctl -u webleads-backup.service
sudo docker compose logs --tail=100 app
curl https://webleads.dnet.llc/health
```

Restauración: descifrar con `openssl enc -d -aes-256-cbc -pbkdf2 -pass file:/data/webleads/backup.key` a un directorio privado, validar SQLite `PRAGMA integrity_check`, detener **solo WebLeads**, restaurar DB y configuración con propietarios/permisos correctos, iniciar y verificar health/login. No sobrescribir DB en marcha. Para rollback de código conservar imagen anterior antes de actualizar. Cambios de esquema futuros requieren migración y backup previo.

## Validación y estructura

```sh
python -m unittest test_app -v
node --check static/app.js
node --check static/sw.js
```

19 pruebas de contrato OSM, categorías, contactos, ausencia/actividad desconocidas, cierres explícitos, caché, errores de proveedores, activación única, sesiones, permisos, CSRF/Origin, deduplicación, notas, CSV y archivos privados. Pruebas de navegador con datos ficticios exclusivamente en contenedor QA: búsqueda, web preservada, guardado, edición, persistencia, invitación, responsive390px, logout/error de contraseña y ausencia de errores JS. Las pruebas QA no modifican la DB de producción. CI en GitHub Actions ejecuta pruebas y chequeos JS; publicar en GitHub no despliega automáticamente.

- `app.py`: servidor/API/autenticación/SQLite/proveedores.
- `static/`: UI, estilos, favicon, manifest, SW y404.
- `requirements.txt`, `Dockerfile`, `compose.yaml`: entorno aislado.
- `test_app.py`, `.github/workflows/ci.yml`: validación.
- `scripts/backup.py`, `deploy/`: backups.
- Archivos históricos `server.py`, `index.html`, `sw.js` originales: referencia de la versión antigua, **no se sirven en producción**.
