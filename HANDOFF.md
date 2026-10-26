# WebLeads — checkpoint Codex, 2026-10-10

## Tarea autorizada
Reparar ubicación, añadir «Encontrarme», permitir elegir cualquier ciudad y comprobar búsqueda de leads. El 2026-10-11 el propietario autorizó resolver el proveedor y desplegar en DNET. No hacer push ni modificar la memoria global.

## Fuente inspeccionada
Clon local `/Users/raul/AI/Webleads`, rama `main`, commit inicial `9f4384c7a3a619290fd9efd4e89d16eeb0b13fd0`. Sin cambios previos en este clon. No existían AGENTS.md ni HANDOFF.md. Producción responde en https://webleads.dnet.llc; el README identifica Flask y `static/` como versión activa. Las otras copias antiguas no se modifican.

## Hallazgos y plan
La versión actual solo acepta texto de ciudad y toma el primer resultado geocodificado; no tiene geolocalización. El mapa arranca en Omaha aunque no haya ubicación elegida. Al fallar una consulta conserva resultados anteriores, y con cero resultados puede dejar marcadores/conteo anteriores. Añadir ubicación explícita, coordenadas validadas, selección de ciudades y estados coherentes; preservar autenticación, CSRF, permisos y límites. Preparar pruebas aisladas sin datos de producción.

## Resultado actual — 2026-10-11
Desplegado y comprobado en https://webleads.dnet.llc. Salud del contenedor `healthy`, `/health` responde `{"ok":true}` y los seis archivos de ejecución coinciden por SHA256 con la copia local.

- Búsqueda real por Omaha: **7 negocios**.
- Botón «Encontrarme» con coordenadas de QA ficticias: **7 negocios**; se envía el centro exacto.
- Ciudad manual Madrid, España: **200 negocios** devueltos, que es el máximo de resultados mostrado/guardable por búsqueda.
- Inicio/cierre de sesión, mapa, diseño de 390px, ausencia de errores JS, guardado y persistencia tras recargar: aprobados. Se borraron la cuenta QA temporal, su sesión y el único lead QA; ningún lead real existente se editó ni eliminó.
- Backup cifrado previo a cambios en `/data/webleads/backups`, imagen inicial de rollback `dnet-webleads:before-location-20261010` y copia de código `/home/raul/webleads-code-before-location-20261010.tar.gz`.
- 33 pruebas de contrato OSM/permisos/proveedor aprobadas dentro del contenedor desplegable. QA local de Playwright pasó y `git diff --check` y `node --check` pasaron.

No se hizo commit ni push. El contenedor desplegado usa `dnet-webleads:current` con SHA de imagen actual comprobado al terminar; el código local continúa en la rama `main`, base `9f4384c7a3a619290fd9efd4e89d16eeb0b13fd0`, con cambios locales descritos abajo.

## Estado actual y cambios sin commit
- Implementados «Encontrarme» (permiso explícito del navegador, timeout y precisión visible), ciudad libre con hasta cinco coincidencias seleccionables y búsquedas por coordenadas exactas validadas en servidor.
- Se muestra la ubicación elegida; ya no se asume Omaha al iniciar. Cambiar ciudad invalida coordenadas previas. Se descartan respuestas atrasadas tras cambiar ubicación. Se limpian resultados, conteo y marcadores antes de consultar y ante cero resultados o errores.
- `/api/locations` conserva autenticación Owner/Member, CSRF/Origin, límites por usuario/globales, caché y serialización de Nominatim. No hay autocompletado con llamadas en cada pulsación. No se envían coordenadas para geocodificación inversa: se consulta Overpass cuando el usuario busca.
- Flask actualizado de 3.1.2 a 3.1.3 por el aviso PYSEC-2026-2151 detectado; sin cambios de esquema ni datos de producción.
- Archivos modificados: `app.py`, `static/app.js`, `static/index.html`, `static/style.css`, `static/sw.js`, `test_app.py`, `requirements.txt`, `README.md`. Nuevos: `HANDOFF.md`, `test_browser.py`. Rama y commit siguen siendo los iniciales; sin commit/push/deploy. Entorno `.venv/` local ignorado.

## Pruebas reales
- Base inicial: 19 unittest aprobados.
- Después de cambios y parche Flask: `.venv/bin/python -m unittest test_app -q`: **28 aprobados**.
- QA navegador: `test_browser.py`, Chromium/Playwright, servidor estático local y API simulada con datos ficticios: GPS, elección entre ciudades ambiguas, coordenadas enviadas, cero resultados, fallos del proveedor, permiso denegado y ancho móvil 390px aprobados; sin errores JavaScript. No prueba obtención real de leads ni la sesión de producción.
- `node --check static/app.js`, `node --check static/sw.js`, `git diff --check` aprobados. `pip check` sin dependencias rotas. `pip-audit -r requirements.txt`: sin vulnerabilidades conocidas tras parche Flask.
- Consulta real Nominatim de Omaha: una coincidencia. El Python local inicialmente falló por certificados del entorno; se verificó de nuevo con `SSL_CERT_FILE=/etc/ssl/cert.pem`, sin desactivar TLS ni modificar el sistema.
- Consulta real Overpass principal: HTTP **406**. Alternativa Private.coffee: HTTP **500**. No se cambiaron proveedores ni se inventaron leads. La documentación actual de Overpass indica que el servicio público principal requiere proveedor propio/contratado para uso comercial: https://wiki.openstreetmap.org/wiki/Overpass_API#Public_Overpass_API_instances.
- El primer ensayo de navegador falló por una función simulada mal definida en el propio test; se corrigió y la ejecución completa pasó.
- Intento SSH de solo lectura a DNET mediante acceso disponible: rechazado por autenticación de clave pública; no se modificó configuración ni se recuperaron credenciales. Por tanto, las fallas del proveedor se comprobaron desde el iMac, no desde DNET.

## Estado pendiente y continuidad
La fuente elegida para negocios es VK Maps; Private.coffee se intenta como respaldo. DNET confirmó búsquedas reales en dos centros, Omaha y Madrid. Los proveedores públicos pueden fallar de manera temporal; la app conserva caché de 1 h, limita consultas por usuario/global, aplica pausa tras error y evita presentar respuestas incompletas como cero resultados. No hay SLA de terceros. El usuario no adquirió proveedor de pago.

Siguiente paso: observar fallos reales reportados y, si la carga o el SLA lo requieren, evaluar un proveedor contratado o un servidor propio; no adquirir servicios sin autorización. Los cambios desplegados no están en GitHub y no hay push autorizado. No actualizar memoria global sin autorización.

## Decisiones y seguridad
Conservar la fuente OSM, los permisos y los prospectos existentes. No usar resultados ficticios como leads reales ni cambiar silenciosamente a otro proveedor. Los 20 criterios de project-security se consideraron según alcance; evidencia específica nueva para validación, permisos, CSRF, límites y escaneo, no auditoría completa. No se modifica la memoria global. Propuesta selectiva de memoria (solo tras autorización): anotar la copia local, correcciones de ubicación verificadas y bloqueo externo/deploy pendiente, sin datos de prospectos ni ubicación personal.


## Continuación autorizada — 2026-10-10, Codex
El usuario autorizó resolver el proveedor y desplegar. SSH correcto mediante alias `dnet.llc` (identidad configurada): acceso exitoso; el intento anterior por IP no usaba esa identidad. Repo DNET limpio, mismo commit inicial, contenedor WebLeads saludable. Consulta real desde DNET al proveedor principal: HTTP 200, siete elementos; Private.coffee continúa con HTTP 500. Se conserva proveedor principal, sin contratación ni cambio de destino. Se añadió rechazo de respuestas parciales/con error del proveedor para no cachearlas como cero resultados.

Checkpoint previo al despliegue: ejecutar pruebas, respaldo cifrado SQLite/config mediante script existente y conservar imagen y código actuales para rollback. Desplegar solo servicio WebLeads, preservando volumen de datos y cuentas. Verificar búsqueda autenticada y guardado con datos de QA aislados; eliminar exclusivamente los registros temporales creados por la verificación. No hacer push ni modificar memoria global.

### Ajuste durante verificación publicada
Primer despliegue pasó 30 pruebas dentro del contenedor y health; la búsqueda publicada reveló una falla intermitente del proveedor principal aunque consultas directas funcionaban. Se conserva el respaldo anterior al primer despliegue. Nueva decisión: VK Maps como proveedor de negocios (HTTP 200 con siete elementos desde DNET), Private.coffee como alternativa acotada; ambos listados por OSM como disponibles para cualquier proyecto. Se mantienen caché/límites y se introduce cooldown de 60 s tras fallo. Consultas con igualdad exacta, nombres obligatorios y salida limitada a 500 elementos (máximo 200 leads devueltos). Dos intentos de hasta 25 s; errores parciales no se cachean. La UI identifica proveedores y maneja respuestas no JSON del proxy. No se envían cuentas, contraseñas ni prospectos guardados a proveedores, solo categoría/centro/radio de búsqueda. Se limpiaron todos los datos temporales de la primera prueba de producción.


### Continuación 2026-10-11
La prueba de producción de la segunda imagen aún falló: la consulta con filtro de nombre/grupo/límite devolvía 504 en VK Maps y Private.coffee 500. Se simplificó la consulta para una categoría individual (sin agrupación ni filtro adicional de nombre; se filtra al procesar). La consulta exacta con coordenadas completas de Omaha devolvió HTTP 200 y siete elementos en 16,6 s desde DNET. No dar por concluido hasta pasar el recorrido publicado. Se preservan los 33 tests y el respaldo original; se actualizará la evidencia final tras pruebas reales. Todos los usuarios/leads temporales de QA se eliminaron al finalizar cada intento.


### Ajuste de tiempos del proveedor
Con las coordenadas exactas de la app, la consulta con timeout de 15 s falló; la misma consulta con 45 s de presupuesto devolvió HTTP 200 y siete elementos en 15,7 s. Se da al proveedor principal un timeout HTTP de 55 s, a la alternativa 20 s y a Nominatim 10 s; el flujo legado completo queda acotado a unos 85 s, por debajo del timeout de Gunicorn (90 s). La UI informa hasta un minuto y medio. Mantener coordenadas exactas; no redondearlas para forzar una respuesta ni reutilizar negocios de otra ubicación.


## Cierre verificado por Codex — 2026-10-11
Prueba end-to-end real en `https://webleads.dnet.llc` con cuenta QA temporal. Búsqueda de ciudad y de ubicación del navegador produjeron 7 resultados cada una; ciudad Madrid produjo 200 (límite de endpoint). Guardado sintético comprobado mediante API y tras recargar el navegador. Cuenta, sesión y lead QA eliminados con script de limpieza de alcance exacto. Auth, cierre de sesión, mapa, móvil y consola JS correctos. Health healthy, SHA256 runtime local = DNET, 33 pruebas en imagen final aprobadas. Inicio de sesión y búsqueda no exponen credenciales en logs.

## Apollo y descarga Excel — 2026-10-26, Codex
- Base actual de Webleads: rama `main`, commit `9f4384c7a3a619290fd9efd4e89d16eeb0b13fd0`. Al iniciar, se conservaron los cambios locales previos de ubicación/proveedores y los archivos `HANDOFF.md` y `test_browser.py`; no se descartó ni se publicó trabajo anterior.
- Añadida búsqueda de responsables de empresas con Apollo en `/api/apollo/search`: ubicación de sede, cargos, tamaño, palabra clave, 10/25/50 resultados y paginación. Clave únicamente en `APOLLO_API_KEY` del servidor; autenticación Owner/Member, validación de filtros y límite local de solicitudes. Los contactos se guardan de forma explícita y aparecen en Mis prospectos.
- Descarga `/api/export.xlsx` protegida por sesión: exporta todos los leads guardados, sin respetar filtros actuales, con empresa/contacto/cargo, estado, responsable, notas, origen e identificadores de Apollo. Celdas como texto XML escapado; hoja con cabecera congelada y filtros. El CSV anterior se conserva.
- Apollo People Search no devuelve email ni teléfono, y oculta parte del apellido; no se implementó enriquecimiento, que puede consumir créditos. API key no figura en el registro de credenciales. No se realizó ninguna consulta real de Apollo ni se crearon leads reales durante QA. El secreto no se guardó en archivos, Git o memoria.
- Verificación local: `.venv/bin/python -m unittest test_app -q` — 38 aprobados; `node --check static/app.js`; `node --check static/sw.js`; `.venv/bin/python test_browser.py` — búsqueda Apollo simulada, paginación, guardado, flujo OSM, móvil 390 px y sin errores JS; `git diff --check` aprobado. Prueba de Excel revisa autenticación, integridad ZIP, XML, campos y que una cadena tipo fórmula no se convierta en fórmula. Una advertencia `ResourceWarning` preexistente aparece al probar la ruta 404, sin fallos.
- Archivos del alcance nuevo: `app.py`, `static/index.html`, `static/app.js`, `static/style.css`, `static/sw.js`, `test_app.py`, `test_browser.py`, `README.md`, `.env.example`; los cambios preexistentes en `requirements.txt` y demás se mantienen. Sin commit, push ni deploy: esta solicitud no incluyó autorización de publicación y el API key requerido no está disponible.
- Siguiente paso concreto: agregar `APOLLO_API_KEY` al archivo de entorno protegido del servidor usando un canal secreto; luego autorizar el despliegue y probar Apollo real y la descarga desde sesión autenticada. No usar enriquecimiento hasta decidir cómo se autoriza el consumo de créditos.

## Buscador ampliado y publicación solicitada — 2026-10-26, Codex
- Raúl pidió ampliar fuentes de prospección, priorizar teléfono, correo, web y redes sociales, y publicar el resultado. Se conserva el trabajo local de ubicación/Apollo/Excel descrito arriba; rama `main`, base `9f4384c7a3a619290fd9efd4e89d16eeb0b13fd0`.
- Terminada interfaz de fuentes de revisión manual (Maps, cámaras, LinkedIn, empleos, eventos, SBA y referidos), búsqueda SAM.gov con contactos públicos cuando estén en el aviso, enlaces sociales permitidos de OSM y formularios manuales con datos de contacto y fuente. El enriquecimiento Apollo es por contacto, requiere confirmación de créditos y no pide teléfono móvil ni realiza lotes. Las exportaciones CSV/XLSX incluyen contactos, redes y campos federales; se conserva escape de fórmulas.
- Seguridad revisada en alcance: las claves siguen siendo variables solo del servidor; rol Owner/Member, CSRF y límites cubren endpoints; campos de redes se restringen por dominio permitido; resultados se dibujan como texto seguro y enlaces HTTP(S). No se usa scraping restringido ni se etiqueta como verificado lo que no lo es.
- Pruebas locales: `python -m unittest test_app -q` — 44 OK; `python test_browser.py` con API simulada — OK (Apollo, confirmación de enriquecimiento, SAM, búsqueda OSM, fuentes, guardado y móvil de 390 px); `node --check` para JS/SW y `git diff --check` — OK; `pip-audit -r requirements.txt` — sin vulnerabilidades conocidas.
- No hay credenciales Apollo ni SAM disponibles en el runtime DNET; no se pudo ejecutar búsqueda real ni validar entregabilidad de correos. Las fuentes manuales/OSM quedan utilizables y los controles Apollo/SAM aparecen desactivados hasta que se agreguen sus claves al archivo protegido. No guardar claves en Git ni en este HANDOFF.
- Estado de este checkpoint: código aún local sin commit; despliegue no iniciado. Próximo paso autorizado: crear respaldo con el mecanismo existente, copiar solo Webleads al checkout DNET, compilar/recrear únicamente `webleads-app-1` preservando `/data`, y comprobar health + rutas + login/export sin alterar prospectos existentes. Después reportar el SHA y el estado real de GitHub por separado.

### Cierre de publicación — 2026-10-26
- Commit `ba52cab986b9dda08c4288a3c76cd6f64337d09d` enviado a `origin/main`; workflow GitHub Actions `WebLeads checks` terminó `success` (run 40318138631).
- Antes del cambio se creó respaldo cifrado `/data/webleads/backups/webleads-20261026T114940Z.tar.gz.enc` (18,464 bytes, modo 600), se conservó la imagen `dnet-webleads:before-lead-intelligence-20261026` (`sha256:b11438c6…`) y no se modificó el volumen de datos.
- Desplegado solo `webleads-app-1`; imagen actual `sha256:09f16169a697fba1bf45a5e0b2424f9c4ba499c4bb7cb322fe4e137a2edc1dff`, estado `running`, health `healthy`. Los SHA256 del app.py, HTML, JS, CSS y service worker en DNET coinciden con el commit local publicado.
- Prueba HTTPS pública: `/`, `/static/app.js`, `/static/style.css`, `/static/sw.js` y `/health` HTTP 200; exportación Excel y `/api/integrations` sin sesión HTTP 401. API de integración protegida, sin filtrar sus secretos.
- No hay `APOLLO_API_KEY` ni `SAM_GOV_API_KEY` en runtime.env; no se ejecutó ninguna consulta externa ni se consumieron créditos. Los paneles de esos proveedores informan la configuración pendiente. OSM/fuentes manuales siguen disponibles. No se tocaron prospectos ni se efectuó QA autenticado en producción por falta de credencial WebLeads registrada.
- Sin tareas de código pendientes para publicar. Para habilitar Apollo y SAM.gov, el administrador debe ingresar las claves en `/data/webleads/runtime.env` con permisos root 600; verificar luego mediante una búsqueda real por proveedor y una revisión de la procedencia de sus contactos.
