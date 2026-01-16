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
        if self.path.startswith('/api/search'):
            self.handle_business_search()
            return
        super().do_GET()

    def handle_business_search(self):
        """Buscar negocios usando OpenStreetMap Overpass API (gratuita, sin API key)"""
        try:
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            term = (params.get('term') or [''])[0]
            location = (params.get('location') or [''])[0]
            radius = int((params.get('radius') or ['5000'])[0])

            if not term or not location:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'error': 'Parámetros requeridos: term y location',
                    'businesses': []
                }).encode('utf-8'))
                return

            # Geocodificar ubicación
            lat, lon = self.geocode_location(location)
            if not lat or not lon:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'error': 'No se pudo geocodificar la ubicación',
                    'businesses': []
                }).encode('utf-8'))
                return

            # Buscar negocios
            businesses = self.search_overpass_businesses(term, lat, lon, radius)

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'businesses': businesses}).encode('utf-8'))

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'error': f'Error del servidor: {str(e)}',
                'businesses': []
            }).encode('utf-8'))

    def geocode_location(self, location):
        """Convertir ubicación a coordenadas usando Nominatim"""
        try:
            url = f"https://nominatim.openstreetmap.org/search?format=json&q={urllib.parse.quote(location)}&limit=1"
            request = urllib.request.Request(url, headers={'User-Agent': 'Webleads-PWA/1.0'})

            with urllib.request.urlopen(request) as response:
                data = json.loads(response.read().decode('utf-8'))
                if data:
                    return float(data[0]['lat']), float(data[0]['lon'])
        except Exception as e:
            print(f"Geocoding error: {e}")
        return None, None

    def search_overpass_businesses(self, term, lat, lon, radius):
        """Buscar negocios usando OpenStreetMap Overpass API"""
        try:
            # Mapear términos de búsqueda a tipos de amenity de OSM
            amenity_mapping = {
                'restaurants': 'restaurant',
                'restaurant': 'restaurant',
                'food': 'restaurant',
                'restaurantes': 'restaurant',
                'comida': 'restaurant',
                'shopping': 'shop',
                'compras': 'shop',
                'tiendas': 'shop',
                'homeservices': '.*',  # Cualquier amenity
                'auto': 'car_wash|car_rental|vehicle_inspection',
                'automotriz': 'car_wash|car_rental|vehicle_inspection',
                'beautysvc': 'hairdresser|beauty',
                'belleza': 'hairdresser|beauty',
                'health': 'hospital|clinic|doctors|dentist|pharmacy',
                'salud': 'hospital|clinic|doctors|dentist|pharmacy',
                'education': 'school|university|college|kindergarten',
                'educacion': 'school|university|college|kindergarten',
                'financialservices': 'bank|atm',
                'financieros': 'bank|atm',
                'realestate': 'real_estate',
                'bienes_raices': 'real_estate',
                'pets': 'veterinary|pet',
                'mascotas': 'veterinary|pet',
                'fitness': 'gym|fitness',
                'gimnasio': 'gym|fitness',
                'entertainment': 'cinema|theatre',
                'entretenimiento': 'cinema|theatre',
                'professional': 'office|accountant|lawyer',
                'profesional': 'office|accountant|lawyer',
                'retail': 'shop',
                'retail': 'shop',
                'travel': 'travel_agency|hotel',
                'viajes': 'travel_agency|hotel',
                'technology': 'computer|electronics',
                'tecnologia': 'computer|electronics',
                'construction': 'construction',
                'construccion': 'construction',
                'transportation': 'taxi|bus_station|ferry_terminal',
                'transporte': 'taxi|bus_station|ferry_terminal',
                'utilities': 'post_office|telephone',
                'servicios': 'post_office|telephone',
                'legal': 'lawyer|courthouse',
                'legal': 'lawyer|courthouse',
                'marketing': 'office',
                'marketing': 'office',
                'consulting': 'office',
                'consultoria': 'office',
                'security': 'police',
                'seguridad': 'police',
                'cleaning': 'cleaning',
                'limpieza': 'cleaning',
                'maintenance': '.*',
                'mantenimiento': '.*',
                'repair': '.*',
                'reparaciones': '.*',
                'installation': '.*',
                'instalaciones': '.*'
            }

            # Determinar qué amenity buscar
            search_amenity = amenity_mapping.get(term.lower(), 'restaurant')

            # Construir query Overpass
            overpass_query = f"""
            [out:json][timeout:25];
            (
              node["amenity"~"{search_amenity}"](around:{radius},{lat},{lon});
              way["amenity"~"{search_amenity}"](around:{radius},{lat},{lon});
              relation["amenity"~"{search_amenity}"](around:{radius},{lat},{lon});
            );
            out center meta;
            """

            url = "https://overpass-api.de/api/interpreter"
            data = urllib.parse.urlencode({'data': overpass_query}).encode('utf-8')
            request = urllib.request.Request(url, data=data, method='POST')

            with urllib.request.urlopen(request) as response:
                overpass_data = json.loads(response.read().decode('utf-8'))

            businesses = []
            for element in overpass_data.get('elements', [])[:50]:  # Limitar a 50 resultados
                # Calcular distancia
                if 'lat' in element and 'lon' in element:
                    element_lat = element['lat']
                    element_lon = element['lon']
                elif 'center' in element:
                    element_lat = element['center']['lat']
                    element_lon = element['center']['lon']
                else:
                    continue

                distance = self.calculate_distance(lat, lon, element_lat, element_lon)
                tags = element.get('tags', {})
                name = tags.get('name', f"{term.title()} sin nombre")

                businesses.append({
                    'id': f"osm_{element['id']}",
                    'name': name,
                    'category': tags.get('amenity', term).replace('_', ' ').title(),
                    'address': tags.get('addr:full', tags.get('addr:housenumber', '') + ' ' + tags.get('addr:street', '')),
                    'city': tags.get('addr:city', ''),
                    'state': tags.get('addr:state', ''),
                    'phone': tags.get('phone', ''),
                    'website': tags.get('website', ''),
                    'hasWebsite': bool(tags.get('website')),
                    'rating': 0,  # OSM no tiene ratings
                    'reviewCount': 0,  # OSM no tiene reviews
                    'price': '',  # OSM no tiene precios
                    'isClosed': False,  # OSM no tiene estado abierto/cerrado
                    'distance': distance,
                    'imageUrl': '',
                    'osmUrl': f"https://www.openstreetmap.org/{element['type']}/{element['id']}",
                    'coordinates': {
                        'latitude': element_lat,
                        'longitude': element_lon
                    },
                    'email': tags.get('email', ''),
                    'openingHours': tags.get('opening_hours', '')
                })

            # Ordenar por distancia
            businesses.sort(key=lambda x: x['distance'])
            return businesses

        except Exception as e:
            print(f"Error searching Overpass: {e}")
            return []

    def calculate_distance(self, lat1, lon1, lat2, lon2):
        """Calcular distancia aproximada entre dos puntos usando fórmula haversine simplificada"""
        import math

        # Radio de la Tierra en metros
        R = 6371000

        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)

        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad

        a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

        distance = R * c
        return distance

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
