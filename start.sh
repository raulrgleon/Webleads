#!/bin/bash

echo "🚀 Iniciando Webleads PWA Server..."
echo ""

# Verificar si Python está instalado
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 no está instalado"
    echo "💡 Instala Python3 desde https://python.org"
    exit 1
fi

# Verificar que todo esté listo
echo "✅ Usando datos gratuitos de OpenStreetMap"
echo "💡 No se requiere configuración adicional"

# Verificar si el puerto está en uso
if lsof -Pi :8001 -sTCP:LISTEN -t >/dev/null ; then
    echo "⚠️  Puerto 8001 ya está en uso"
    echo "💡 Deteniendo proceso anterior..."
    pkill -f "python3 server.py"
    sleep 2
fi

echo "✅ Iniciando servidor en puerto 8001..."
echo "🌐 Abre tu navegador en: http://localhost:8001"
echo "⏹️  Presiona Ctrl+C para detener"
echo ""

# Iniciar servidor
python3 server.py
