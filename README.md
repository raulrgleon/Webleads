# 🚀 Webleads PWA - Motor de Búsqueda Inteligente

[![GitHub](https://img.shields.io/badge/GitHub-raulrgleon/Webleads-blue?logo=github)](https://github.com/raulrgleon/Webleads)

## 📋 Descripción
Aplicación web progresiva (PWA) para buscar negocios locales usando **datos de OpenStreetMap (gratuitos y sin API key)**. Incluye mapa interactivo, exportación a CSV para EspoCRM y funcionalidad offline.

## 🎯 Características
- ✅ **Datos Gratuitos** - OpenStreetMap (sin API key requerida)
- ✅ **PWA Instalable** - Funciona como app nativa
- ✅ **Mapa Interactivo** - Leaflet con marcadores
- ✅ **Exportación EspoCRM** - CSV optimizado
- ✅ **Funcionalidad Offline** - Cache automático
- ✅ **30+ Tipos de Negocios** - Categorías completas

## 🚀 Instalación y Uso

### 0. Clonar desde GitHub
```bash
git clone https://github.com/raulrgleon/Webleads.git
cd Webleads
```

### 0.1 ¡Sin configuración adicional!
No se requiere API key. Los datos provienen de OpenStreetMap (gratuito).

### Opción 1: Script Automático (Recomendado)
```bash
./start.sh
```

### Opción 2: Python Manual
```bash
python3 server.py
```

### Opción 3: Servidor HTTP Simple
```bash
# Python 3
python3 -m http.server 8000

# Python 2
python -m SimpleHTTPServer 8000
```

## 🌐 Acceso
Una vez iniciado el servidor, abre tu navegador en:
- **http://localhost:8001**
- **http://127.0.0.1:8001**

## 📱 Instalación PWA
1. Abre la aplicación en Chrome/Edge
2. Haz clic en el botón "📱 Instalar App"
3. Confirma la instalación
4. La app aparecerá en tu escritorio/aplicaciones

## 🔧 Requisitos
- **Python 3.x** (para el servidor)
- **Navegador moderno** (Chrome, Firefox, Safari, Edge)
- **Conexión a internet** (para API de Yelp)

## 📊 Uso
1. **Selecciona ubicación** - Escribe ciudad, estado
2. **Elige tipo de negocio** - 30+ categorías disponibles
3. **Ajusta radio** - 1km a 40km
4. **Busca** - Datos reales de Yelp
5. **Exporta** - CSV para EspoCRM

## 🗂️ Estructura de Archivos
```
webleads-html/
├── index.html          # Aplicación principal
├── manifest.json       # Configuración PWA
├── sw.js              # Service Worker
├── server.py          # Servidor Python
├── start.sh           # Script de inicio
├── generate-icons.html # Generador de iconos
├── icons/             # Iconos PWA
└── README.md          # Este archivo
```

## ⚠️ Notas Importantes
- **NO abras index.html directamente** - Usa el servidor
- **Service Worker requiere HTTPS** en producción
- **Datos de OpenStreetMap** - Gratuitos y sin límites de uso
- **Sin API key requerida** - Funciona inmediatamente
- **Cobertura global** - Disponible en todo el mundo
- **API Key** se configura en el servidor (variable `YELP_API_KEY`)

## 🐛 Solución de Problemas

### "Service Worker no disponible"
- ✅ Usa el servidor HTTP (no abras archivo directamente)
- ✅ Verifica que estés en http://localhost:8000

### "Error de API de Yelp"
- ✅ Verifica conexión a internet
- ✅ Revisa límites de API (500 requests/día)
- ✅ Confirma credenciales en sw.js

### "Puerto en uso"
```bash
# Detener proceso
pkill -f "python3 server.py"

# O usar otro puerto
python3 -m http.server 8080
```

## 📞 Soporte
Para problemas o mejoras, revisa:
- Console del navegador (F12)
- Network tab para errores de API
- Service Worker en DevTools

---
**Desarrollado con ❤️ para búsqueda profesional de negocios**
