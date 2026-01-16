# 🔑 Configuración de Yelp API

## ❌ Error Actual: "Error de autenticación con Yelp"

### 🔍 Diagnóstico
El error 401 indica que la API key de Yelp no es válida o ha expirado.

## 🛠️ Solución

### 1. Verificar API Key Actual
La API key debe configurarse como variable de entorno en el servidor:
```
export YELP_API_KEY="TU_API_KEY"
```

### 2. Obtener Nueva API Key

#### Opción A: Usar API Key Existente
1. Ve a [Yelp Developers](https://www.yelp.com/developers)
2. Inicia sesión con tu cuenta
3. Ve a "Manage App"
4. Copia tu API Key

#### Opción B: Crear Nueva App
1. Ve a [Yelp Developers](https://www.yelp.com/developers)
2. Haz clic en "Create App"
3. Completa el formulario:
   - **App Name**: Webleads
   - **Description**: Business search application
   - **Website**: http://localhost:8000
4. Copia la API Key generada

### 3. Configurar API Key en el servidor
```bash
export YELP_API_KEY="TU_NUEVA_API_KEY"
```

### 4. Verificar API Key
```bash
# Probar API key directamente con Yelp
curl -H "Authorization: Bearer TU_API_KEY" \
     "https://api.yelp.com/v3/businesses/search?term=restaurants&location=Houston"

# Probar proxy local
curl "http://localhost:8000/api/yelp/search?term=restaurants&location=Houston&radius=5000"
```

## 🔧 Solución Temporal

Si no tienes acceso a Yelp API, puedes:

### Opción 1: Usar Mock Data
Activa el checkbox **"Usar datos simulados siempre"** en la app.

### Opción 2: API Alternativa
- **Google Places API** (requiere facturación)
- **Foursquare API** (gratuito con límites)
- **OpenStreetMap Nominatim** (gratuito, sin datos de negocios)

## 📊 Límites de Yelp API

- **Gratuito**: 500 requests/día
- **Pago**: Hasta 25,000 requests/día
- **Rate Limit**: 500 requests/día por IP

## 🚨 Errores Comunes

### 401 - Unauthorized
- API key inválida
- API key expirada
- Formato incorrecto del header

### 429 - Too Many Requests
- Límite diario excedido
- Rate limit excedido

### 500 - Internal Server Error
- Problema temporal de Yelp
- Reintentar en unos minutos

## 💡 Recomendaciones

1. **Usa HTTPS** en producción
2. **Guarda API key** de forma segura
3. **Implementa cache** para reducir requests
4. **Maneja errores** graciosamente
5. **Monitorea uso** de API

---
**Una vez actualizada la API key, la aplicación funcionará con datos reales de Yelp.**
