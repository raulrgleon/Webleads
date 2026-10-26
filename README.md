# WebLeads · DNET

Herramienta privada de captación de clientes en **https://webleads.dnet.llc**. Encuentra negocios locales, revisa sus datos y organiza oportunidades compartidas con el equipo. Marca una ausencia de web como **por verificar**; no presume que el negocio carece de página ni que está abierto.

## Funciones

- Botón «Encontrarme» con permiso del navegador y búsqueda por coordenadas reales. Alternativamente escribe cualquier ciudad, estado y país; si hay varias coincidencias, elige la correcta antes de buscar. La interfaz muestra la ubicación seleccionada y elimina resultados antiguos al cambiarla o fallar una consulta.
- Búsqueda de 16 sectores por ubicación y radios de 2, 5, 10 o 20 km. Dentistas y fisioterapeutas tienen consultas específicas; shop/office/healthcare/leisure/tourism no se confunden con amenity.
- Búsqueda opcional de responsables de empresa con Apollo: ubicación, cargos, tamaño y palabras clave. La búsqueda no consume créditos de enriquecimiento, oculta parte del apellido y no entrega correos/teléfonos. La solicitud individual de correo se confirma antes de usarla y puede consumir entre 1 y 9 créditos según los datos encontrados; no solicita móvil ni hace enriquecimiento masivo.
- Oportunidades federales de SAM.gov con fecha, agencia, identificador, NAICS y datos de contacto del funcionario de contratación cuando la fuente los publica. Los avisos son oportunidades, no clientes ganados. Requiere `SAM_GOV_API_KEY` en el servidor.
- Hasta 200 negocios de OpenStreetMap con mapa, teléfono, correo, página web, perfiles sociales y enlace a la ficha cuando esos datos fueron publicados. No crea ni adivina contactos. Cobertura variable y actividad pendiente de revisión.
- Fuentes adicionales para revisión humana: Google Maps, cámaras de comercio, LinkedIn, empleos, eventos, SBA y referidos. Se abren consultas filtradas en sus sitios; WebLeads no extrae datos de áreas restringidas ni hace scraping oculto.
- Filtro de web encontrada/por verificar. Comprobación manual: sin web confirmada o web deficiente. No analiza automáticamente las webs ni comprueba su rendimiento.
- Prospectos compartidos y persistentes, sin duplicados por ID, responsables, notas y etapas detectado/revisado/contactado/propuesta/ganado/perdido.
- Registro manual y migración de hasta 200 registros de localStorage del **mismo dominio/navegador**, siempre como datos no verificados. No puede leer historial privado de otros dominios.
- Descarga CSV o Excel de todos los prospectos guardados, aunque la lista esté filtrada. Excel incluye teléfonos, correos, sitios, redes, cargos, etapas, responsable, fuente y campos federales de SAM.gov; las celdas se exportan como texto para evitar fórmulas.
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

Variables: `APP_URL` (origen exacto, obligatorio para CSRF y cookies), `OWNER_EMAIL` (identidad administrativa documentada), `DATA_DIR` (ruta SQLite) y, opcionalmente, `APOLLO_API_KEY` y `SAM_GOV_API_KEY`. Compose lee `/data/webleads/runtime.env`. Configura secretos solo en ese archivo protegido, nunca en Git, HTML, JavaScript, URLs del navegador, logs o capturas. Sin estas claves, OSM y las fuentes externas abiertas a revisión manual siguen disponibles; Apollo/SAM.gov se muestran como pendientes de conexión. Apollo People Search no consume créditos de enriquecimiento y devuelve datos limitados; solicitar datos de una persona puede consumir créditos, por lo que la UI requiere confirmación por contacto y no hace lotes.

El primer acceso del propietario está en `/data/webleads/owner-activation.url` (root600): enlace privado de un solo uso hacia su correo, válido7d. Abrirlo y elegir nombre/contraseña≥12 caracteres. Las invitaciones de equipo se crean en **Equipo** y se comparten manualmente; la aplicación no envía emails de invitación ni tiene recuperación de contraseña automática. Si se pierde el acceso, un administrador del servidor debe preparar una recuperación controlada; no cambiar contraseñas directamente en producción sin autorización. No divulgar enlaces de activación ni ponerlos en Workspace/GitHub.

## Servicios externos y límites

Nominatim público identifica la ubicación: caché7d, serialización persistente entre workers y al menos1.1s entre solicitudes de la app. Búsquedas manuales, nunca barrido automático. Cumplir https://operations.osmfoundation.org/policies/nominatim/ (máximo1request/s sumando usuarios, atribución y caché). Los datos OSM se consultan en Overpass de VK Maps, con Private.coffee como alternativa. Caché de 1 h, límites por usuario/globales, máximo dos intentos (55 s para VK Maps y 20 s para la alternativa) y pausa de 60 s por proveedor tras fallo. Las respuestas parciales se rechazan; no se guardan como cero resultados. Las consultas usan etiquetas exactas y evitan agrupaciones innecesarias. Se descartan registros sin nombre y se devuelven hasta 200 negocios. Proveedores públicos sin SLA; mantenerlos dentro de uso moderado y migrar a proveedor contratado o instancia propia si crece la demanda. Tiles públicos OSM con atribución; no descargar en masa. Leaflet servido desde CDN versionado; no envía datos privados a un servicio IA.

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

33 pruebas de contrato OSM, categorías, contactos, ausencia/actividad desconocidas, cierres explícitos, caché, errores de proveedores, activación única, sesiones, permisos, CSRF/Origin, deduplicación, notas, CSV y archivos privados. Pruebas de navegador con datos ficticios exclusivamente en contenedor QA: búsqueda, web preservada, guardado, edición, persistencia, invitación, responsive390px, logout/error de contraseña y ausencia de errores JS. Las pruebas QA no modifican la DB de producción. CI en GitHub Actions ejecuta pruebas y chequeos JS; publicar en GitHub no despliega automáticamente.

- `app.py`: servidor/API/autenticación/SQLite/proveedores.
- `static/`: UI, estilos, favicon, manifest, SW y404.
- `requirements.txt`, `Dockerfile`, `compose.yaml`: entorno aislado.
- `test_app.py`, `.github/workflows/ci.yml`: validación.
- `scripts/backup.py`, `deploy/`: backups.
- Archivos históricos `server.py`, `index.html`, `sw.js` originales: referencia de la versión antigua, **no se sirven en producción**.

## Verificación de ubicación (2026-10-10, copia local)

`python -m unittest test_app -v`: 33 pruebas aprobadas. `test_browser.py` usa Playwright y datos sintéticos para verificar GPS, elección de ciudades ambiguas, coordenadas exactas, cero resultados, errores, permiso denegado y ancho móvil de 390 px. Ejecutar con un servidor estático local en puerto 3211; no apunta a producción:

```sh
python -m http.server 3211 --bind 127.0.0.1
# En otra terminal (Playwright y Chromium instalados en entorno de desarrollo):
python test_browser.py
```

La ubicación se valida con Nominatim y los negocios con las instancias Overpass de VK Maps/Private.coffee. Se eligieron estas instancias porque permiten uso en cualquier proyecto según [la lista de proveedores de OSM](https://wiki.openstreetmap.org/wiki/Overpass_API#Public_Overpass_API_instances). No requieren claves ni contratación; siguen siendo servicios públicos sin SLA. El navegador envía ciudad o coordenadas a WebLeads; el servidor remite únicamente la consulta de ubicación/negocios al proveedor correspondiente, nunca cuentas ni prospectos guardados.

El proveedor principal anterior (`overpass-api.de`) mostró resultados intermitentes al verificar desde DNET. Ver `HANDOFF.md` para evidencia del despliegue y la comprobación real final. No confundir pruebas de navegador con datos simulados y pruebas reales en producción.
