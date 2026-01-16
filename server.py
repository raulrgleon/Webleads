#!/usr/bin/env python3
"""
Servidor HTTP simple para Webleads PWA
Necesario para que el Service Worker funcione correctamente
"""

import http.server
import socketserver
import os
import webbrowser
import json
import urllib.parse
import urllib.request
from pathlib import Path

# Puerto del servidor (cambiado para forzar nueva sesión)
PORT = 8001

# Directorio actual
DIRECTORY = Path(__file__).parent

class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)
    
    def end_headers(self):
        # Headers básicos para desarrollo (sin COEP/COOP)
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        # NO enviar COEP/COOP para permitir recursos externos como tiles de mapas
        super().end_headers()

    def do_GET(self):
        if self.path.startswith('/api/yelp/search'):
            self.handle_yelp_search()
            return
        super().do_GET()

    def handle_yelp_search(self):
        api_key = os.environ.get('YELP_API_KEY')
        if not api_key:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'error': 'YELP_API_KEY no configurada en el servidor',
                'businesses': []
            }).encode('utf-8'))
            return

        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        term = (params.get('term') or [''])[0]
        location = (params.get('location') or [''])[0]
        radius = (params.get('radius') or [''])[0]

        if not term or not location:
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'error': 'Parámetros requeridos: term y location',
                'businesses': []
            }).encode('utf-8'))
            return

        query = {
            'term': term,
            'location': location,
            'radius': radius or '5000',
            'limit': '100',
            'sort_by': 'distance'
        }
        url = f"https://api.yelp.com/v3/businesses/search?{urllib.parse.urlencode(query)}"

        request = urllib.request.Request(url, headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        })

        try:
            with urllib.request.urlopen(request) as response:
                data = response.read()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(data)
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else ''
            self.send_response(e.code)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'error': f'Yelp API error: {e.code}',
                'details': error_body,
                'businesses': []
            }).encode('utf-8'))
        except Exception as e:
            self.send_response(502)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'error': 'No se pudo conectar con Yelp',
                'details': str(e),
                'businesses': []
            }).encode('utf-8'))

def start_server():
    """Inicia el servidor HTTP"""
    try:
        with socketserver.TCPServer(("", PORT), CustomHTTPRequestHandler) as httpd:
            print(f"🚀 Servidor Webleads iniciado en:")
            print(f"   http://localhost:{PORT}")
            print(f"   http://127.0.0.1:{PORT}")
            print(f"\n📁 Sirviendo archivos desde: {DIRECTORY}")
            print(f"\n💡 Abre tu navegador en: http://localhost:{PORT}")
            print(f"\n⏹️  Presiona Ctrl+C para detener el servidor")
            
            # Abrir automáticamente en el navegador
            webbrowser.open(f'http://localhost:{PORT}')
            
            # Iniciar servidor
            httpd.serve_forever()
            
    except KeyboardInterrupt:
        print(f"\n🛑 Servidor detenido")
    except OSError as e:
        if e.errno == 48:  # Address already in use
            print(f"❌ Error: Puerto {PORT} ya está en uso")
            print(f"💡 Intenta con otro puerto o detén el proceso que lo usa")
        else:
            print(f"❌ Error al iniciar servidor: {e}")

if __name__ == "__main__":
    start_server()
