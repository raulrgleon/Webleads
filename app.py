import csv, functools, hashlib, io, json, math, os, re, secrets, sqlite3, time, urllib.error, urllib.parse, urllib.request, zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape
from flask import Flask, request, jsonify, g, send_from_directory, Response
from werkzeug.security import generate_password_hash, check_password_hash

ROOT=Path(__file__).parent
DATA=Path(os.environ.get('DATA_DIR','./data'));DATA.mkdir(parents=True,exist_ok=True)
DB=DATA/'webleads.sqlite'
BASE=os.environ.get('APP_URL','http://localhost:3210').rstrip('/')
OWNER=os.environ.get('OWNER_EMAIL','raulrgleon@gmail.com')
app=Flask(__name__,static_folder='static');app.config['MAX_CONTENT_LENGTH']=2*1024*1024
STAGES=['detectado','revisado','contactado','propuesta','ganado','perdido']
CATEGORIES={
 'dentistas':[('amenity','dentist')], 'fisioterapeutas':[('healthcare','physiotherapist')],
 'clinicas':[('amenity','clinic'),('healthcare','clinic')], 'restaurantes':[('amenity','restaurant')],
 'cafeterias':[('amenity','cafe')], 'peluquerias':[('shop','hairdresser')],
 'talleres':[('shop','car_repair')], 'abogados':[('office','lawyer')],
 'contables':[('office','accountant')], 'gimnasios':[('leisure','fitness_centre')],
 'inmobiliarias':[('office','estate_agent')], 'hoteles':[('tourism','hotel')],
 'tiendas':[('shop','.*')], 'veterinarios':[('amenity','veterinary')],
 'mudanzas':[('office','moving_company')], 'construccion':[('office','construction_company')]
}
class UpstreamError(Exception):pass
def db():
 if 'db' not in g:
  g.db=sqlite3.connect(DB,timeout=15);g.db.row_factory=sqlite3.Row;g.db.execute('PRAGMA foreign_keys=ON')
 return g.db
@app.teardown_appcontext
def close(error):
 if 'db' in g:g.db.close()
def initialize():
 c=sqlite3.connect(DB);c.execute('PRAGMA journal_mode=WAL');c.executescript('''
 CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,email TEXT UNIQUE,name TEXT,password TEXT,role TEXT,active INTEGER DEFAULT 1);
 CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id),csrf TEXT,expires INTEGER);
 CREATE TABLE IF NOT EXISTS invites(token TEXT PRIMARY KEY,email TEXT,role TEXT,expires INTEGER,used INTEGER DEFAULT 0);
 CREATE TABLE IF NOT EXISTS leads(id TEXT PRIMARY KEY,data TEXT,stage TEXT,notes TEXT,assignee TEXT,updated INTEGER);
 CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,user_id TEXT,action TEXT,entity TEXT,created INTEGER);
 CREATE TABLE IF NOT EXISTS cache(k TEXT PRIMARY KEY,data TEXT,expires INTEGER);
 CREATE TABLE IF NOT EXISTS limits(k TEXT PRIMARY KEY,n INTEGER,start INTEGER);
 CREATE TABLE IF NOT EXISTS external(k TEXT PRIMARY KEY,at REAL);
 ''');c.commit();c.close()
initialize()
def token_hash(t):return hashlib.sha256(t.encode()).hexdigest()
def rate(key,limit,seconds):
 c=db();now=int(time.time());c.execute('BEGIN IMMEDIATE');row=c.execute('SELECT n,start FROM limits WHERE k=?',(key,)).fetchone()
 if not row or now-row['start']>=seconds:c.execute('INSERT OR REPLACE INTO limits VALUES(?,?,?)',(key,1,now));ok=True
 else:
  ok=row['n']<limit
  if ok:c.execute('UPDATE limits SET n=n+1 WHERE k=?',(key,))
 c.commit();return ok
@app.before_request
def before():
 token=request.cookies.get('wl_session','');row=db().execute('SELECT u.*,s.csrf,s.expires FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=?',(token_hash(token),)).fetchone() if token else None
 g.user=dict(row) if row and row['active'] and row['expires']>time.time() else None
 if request.path.startswith('/api/') and request.method not in ('GET','HEAD','OPTIONS'):
  if request.headers.get('Origin')!=BASE:return jsonify(error='Origen no autorizado.'),403
  if request.path not in ('/api/login','/api/activate'):
   if not g.user or not secrets.compare_digest(request.headers.get('X-CSRF',''),g.user['csrf']):return jsonify(error='Actualiza la página e inicia sesión.'),403
@app.after_request
def headers(resp):
 resp.headers['X-Content-Type-Options']='nosniff';resp.headers['Referrer-Policy']='no-referrer';resp.headers['X-Frame-Options']='DENY'
 resp.headers['Content-Security-Policy']="default-src 'self'; script-src 'self' https://unpkg.com; style-src 'self' 'unsafe-inline' https://unpkg.com; img-src 'self' data: https://*.tile.openstreetmap.org; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
 if BASE.startswith('https:'):resp.headers['Strict-Transport-Security']='max-age=31536000'
 if request.path.startswith('/api/'):resp.headers['Cache-Control']='no-store'
 return resp
@app.errorhandler(413)
def large(e):return jsonify(error='El archivo supera 2 MB.'),413
@app.errorhandler(404)
def missing(e):return send_from_directory(ROOT/'static','404.html'),404
@app.errorhandler(500)
def failure(e):return jsonify(error='No se pudo completar la operación. Intenta nuevamente.'),500
def auth(role=None):
 def deco(fn):
  @functools.wraps(fn)
  def wrap(*a,**k):
   if not g.user:return jsonify(error='Inicia sesión.'),401
   if role and g.user['role'] not in role:return jsonify(error='No tienes permiso para esta acción.'),403
   return fn(*a,**k)
  return wrap
 return deco
def clean(s,n=200):return str(s or '').strip()[:n]
def safe_url(value):
 v=clean(value,1000)
 if not v:return ''
 if not re.match(r'^https?://',v,re.I):v='https://'+v
 try:
  p=urllib.parse.urlparse(v);p.port
 except ValueError:return ''
 return v if p.scheme in ('http','https') and p.hostname and not p.username and not any(c in p.hostname for c in ' <>\"') else ''
def audit(action,entity):db().execute('INSERT INTO audit(user_id,action,entity,created) VALUES(?,?,?,?)',(g.user['id'],action,entity,int(time.time())))
def login_user(user):
 t=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(24);db().execute('INSERT INTO sessions VALUES(?,?,?,?)',(token_hash(t),user['id'],csrf,int(time.time()+604800)));db().commit()
 r=jsonify(ok=True);r.set_cookie('wl_session',t,httponly=True,secure=BASE.startswith('https:'),samesite='Lax',max_age=604800);return r
@app.get('/')
def home():return send_from_directory(ROOT/'static','index.html')
@app.get('/favicon.svg')
def icon():return send_from_directory(ROOT/'static','favicon.svg')
@app.get('/robots.txt')
def robots():return Response('User-agent: *\nDisallow: /\n',mimetype='text/plain')
@app.get('/health')
def health():db().execute('SELECT 1');return jsonify(ok=True)
@app.get('/api/me')
def me():return jsonify(user={k:g.user[k] for k in ('id','email','name','role','csrf')} if g.user else None,categories=list(CATEGORIES),stages=STAGES)
@app.get('/api/integrations')
@auth()
def integrations():return jsonify(apollo={'configured':bool(os.environ.get('APOLLO_API_KEY','').strip())},samGov={'configured':bool(os.environ.get('SAM_GOV_API_KEY','').strip())},openStreetMap={'configured':True})
@app.post('/api/login')
def login():
 # Cloudflare supplies this header through the loopback-only published port.
 ip=request.headers.get('CF-Connecting-IP',request.remote_addr)
 if not rate('login:'+ip,10,900):return jsonify(error='Demasiados intentos; espera 15 minutos.'),429
 x=request.get_json() or {};u=db().execute('SELECT * FROM users WHERE email=? AND active=1',(clean(x.get('email')).lower(),)).fetchone()
 if not u or not check_password_hash(u['password'],str(x.get('password',''))):return jsonify(error='Correo o contraseña incorrectos.'),401
 return login_user(u)
@app.post('/api/logout')
@auth()
def logout():db().execute('DELETE FROM sessions WHERE token=?',(token_hash(request.cookies.get('wl_session','')),));db().commit();r=jsonify(ok=True);r.delete_cookie('wl_session');return r
@app.post('/api/activate')
def activate():
 if not rate('activate:'+request.headers.get('CF-Connecting-IP',request.remote_addr),15,900):return jsonify(error='Espera antes de intentar nuevamente.'),429
 x=request.get_json() or {};password=str(x.get('password',''));token=str(x.get('token',''))
 if not 12<=len(password)<=200:return jsonify(error='Usa una contraseña de entre 12 y 200 caracteres.'),400
 c=db();c.execute('BEGIN IMMEDIATE');inv=c.execute('SELECT * FROM invites WHERE token=? AND used=0 AND expires>?',(token_hash(token),int(time.time()))).fetchone()
 if not inv:c.rollback();return jsonify(error='La invitación no es válida o ha vencido.'),400
 if c.execute('SELECT 1 FROM users WHERE email=?',(inv['email'],)).fetchone():c.rollback();return jsonify(error='La cuenta ya existe. Inicia sesión.'),409
 uid=secrets.token_hex(12);c.execute('INSERT INTO users VALUES(?,?,?,?,?,1)',(uid,inv['email'],clean(x.get('name'),100) or inv['email'].split('@')[0],generate_password_hash(password,method='pbkdf2:sha256:1000000'),inv['role']));c.execute('UPDATE invites SET used=1 WHERE token=?',(inv['token'],));c.commit();return login_user({'id':uid})
@app.get('/api/team')
@auth()
def team():return jsonify(users=[dict(r) for r in db().execute('SELECT id,email,name,role,active FROM users')])
@app.post('/api/invites')
@auth(['Owner'])
def invite():
 x=request.get_json() or {};email=clean(x.get('email')).lower();role=x.get('role','Member')
 if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or role not in ('Member','Viewer'):return jsonify(error='Revisa el correo y el permiso.'),400
 if db().execute('SELECT 1 FROM users WHERE email=?',(email,)).fetchone():return jsonify(error='La cuenta ya existe.'),409
 t=secrets.token_urlsafe(32);db().execute('INSERT INTO invites VALUES(?,?,?,?,0)',(token_hash(t),email,role,int(time.time()+604800)));audit('invite',email);db().commit();return jsonify(url=BASE+'/#invite='+t)
@app.patch('/api/team/<uid>')
@auth(['Owner'])
def change_user(uid):
 if uid==g.user['id']:return jsonify(error='No puedes desactivar tu propia cuenta.'),400
 x=request.get_json() or {};role=x.get('role','Member')
 if role not in ('Member','Viewer'):return jsonify(error='Permiso no válido.'),400
 db().execute('UPDATE users SET role=?,active=? WHERE id=? AND role!=?',(role,1 if x.get('active',True) else 0,uid,'Owner'));audit('team',uid);db().commit();return jsonify(ok=True)
def cached(k):
 r=db().execute('SELECT data FROM cache WHERE k=? AND expires>?',(k,int(time.time()))).fetchone();return json.loads(r['data']) if r else None
def put_cache(k,data,ttl):db().execute('INSERT OR REPLACE INTO cache VALUES(?,?,?)',(k,json.dumps(data),int(time.time()+ttl)));db().commit()
def external(url,data=None,timeout=35):
 req=urllib.request.Request(url,data=data,headers={'User-Agent':'DNET-WebLeads/2.0 (+https://dnet.llc; contacto: raulrgleon@gmail.com)','Accept':'application/json'})
 try:
  with urllib.request.urlopen(req,timeout=timeout) as r:return json.load(r)
 except (OSError,ValueError,urllib.error.HTTPError) as ex:raise UpstreamError('El proveedor de mapas no respondió. Espera un minuto e inténtalo de nuevo.') from ex

def apollo_search_request(params):
 key=os.environ.get('APOLLO_API_KEY','').strip()
 if not key:raise RuntimeError('Apollo no está configurado. El administrador debe añadir la clave API en el servidor.')
 url='https://api.apollo.io/api/v1/mixed_people/api_search?'+urllib.parse.urlencode(params,doseq=True)
 req=urllib.request.Request(url,data=b'',headers={'x-api-key':key,'Content-Type':'application/json','Cache-Control':'no-cache','Accept':'application/json'})
 try:
  with urllib.request.urlopen(req,timeout=25) as r:
   body=json.load(r)
   if not isinstance(body,dict) or not isinstance(body.get('people'),list):raise ValueError('Respuesta incompleta')
   return body
 except urllib.error.HTTPError as ex:
  if ex.code==401:message='Apollo rechazó la clave API. El administrador debe revisar su configuración.'
  elif ex.code==403:message='La cuenta o la clave de Apollo no tiene acceso a esta búsqueda.'
  elif ex.code==422:message='Apollo no aceptó estos filtros. Revisa los cargos, la ubicación y el tamaño de empresa.'
  elif ex.code==429:message='Apollo alcanzó el límite de búsquedas de tu cuenta. Espera y vuelve a intentarlo.'
  else:message='Apollo no pudo completar la búsqueda. Inténtalo más tarde.'
  raise UpstreamError(message) from ex
 except (OSError,ValueError) as ex:raise UpstreamError('Apollo no respondió con una búsqueda válida. Inténtalo más tarde.') from ex

def apollo_enrich_request(apollo_id):
 key=os.environ.get('APOLLO_API_KEY','').strip()
 if not key:raise RuntimeError('Apollo no está configurado. El administrador debe añadir la clave API al servidor.')
 url='https://api.apollo.io/api/v1/people/match?'+urllib.parse.urlencode({'id':apollo_id,'reveal_personal_emails':'false'})
 req=urllib.request.Request(url,data=b'',headers={'x-api-key':key,'Content-Type':'application/json','Cache-Control':'no-cache','Accept':'application/json'})
 try:
  with urllib.request.urlopen(req,timeout=25) as r:
   body=json.load(r)
   if not isinstance(body,dict):raise ValueError('Respuesta incompleta')
   return body
 except urllib.error.HTTPError as ex:
  if ex.code in (401,403):message='Apollo rechazó la clave o no autorizó el enriquecimiento.'
  elif ex.code==422:message='Apollo no pudo identificar este contacto. No se modificó el prospecto.'
  elif ex.code==429:message='Apollo alcanzó el límite de enriquecimientos. Espera y vuelve a intentarlo.'
  else:message='Apollo no pudo completar el enriquecimiento.'
  raise UpstreamError(message) from ex
 except (OSError,ValueError) as ex:raise UpstreamError('Apollo no respondió con datos válidos. Inténtalo más tarde.') from ex

def sam_search_request(params):
 key=os.environ.get('SAM_GOV_API_KEY','').strip()
 if not key:raise RuntimeError('SAM.gov no está configurado. El administrador debe añadir su clave API al servidor.')
 req=urllib.request.Request('https://api.sam.gov/opportunities/v2/search?'+urllib.parse.urlencode([*params,('api_key',key)]),headers={'User-Agent':'DNET-WebLeads/2.0 (+https://dnet.llc)','Accept':'application/json'})
 try:
  with urllib.request.urlopen(req,timeout=25) as r:
   body=json.load(r)
   if not isinstance(body,dict) or not isinstance(body.get('opportunitiesData'),list):raise ValueError('Respuesta incompleta')
   return body
 except urllib.error.HTTPError as ex:
  if ex.code in (401,403):message='SAM.gov rechazó la clave o no autorizó esta búsqueda.'
  elif ex.code==429:message='SAM.gov alcanzó su límite de consultas. Espera y vuelve a intentarlo.'
  elif ex.code==400:message='SAM.gov no aceptó los filtros. Revisa las fechas y la ubicación.'
  else:message='SAM.gov no pudo completar la búsqueda.'
  raise UpstreamError(message) from ex
 except (OSError,ValueError) as ex:raise UpstreamError('SAM.gov no respondió con una búsqueda válida. Inténtalo más tarde.') from ex

def xlsx_safe(value):
 # Write every value as an inline string; spreadsheet formula prefixes stay inert.
 if value is None:return ''
 value=str(value)
 return ''.join(ch for ch in value if ch in '\t\n\r' or ord(ch)>=32)

def build_xlsx(rows):
 headers=['Empresa u oportunidad','Contacto (Apollo puede ocultar parte del apellido)','Cargo','Teléfono','Correo','Estado del correo','Correo disponible en Apollo','Teléfono directo disponible','Dirección','Ciudad','Estado','Web','Redes sociales','Agencia','Estado de la web','Etapa','Responsable','Notas','Fuente','ID Apollo','ID de oportunidad SAM','Número de solicitud','Fecha límite','NAICS','Tipo de registro','Actualizado en Apollo','Añadido a WebLeads']
 fields=('name','contactName','title','phone','email','emailStatus','emailAvailable','directPhoneAvailable','address','city','state','website','socials','agency','websiteStatus','stage','assignee','notes','source','apolloId','opportunityId','solicitationNumber','responseDeadline','naicsCode','dataKind','apolloRefreshedAt','updated')
 def cell(ref,value):return f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{escape(xlsx_safe(value))}</t></is></c>'
 xml_rows=[]
 for rnum,row in enumerate([headers,*rows],1):
  values=row if rnum==1 else [', '.join(f"{item.get('platform')}: {item.get('url')}" for item in row.get(k,[]) if isinstance(item,dict)) if k=='socials' and isinstance(row.get(k),list) else row.get(k,'') for k in fields]
  xml_rows.append('<row r="%d">%s</row>'%(rnum,''.join(cell(f'{column_name(c)}{rnum}',v) for c,v in enumerate(values,1))))
 sheet='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><sheetFormatPr defaultRowHeight="18"/><sheetData>'+''.join(xml_rows)+'</sheetData><autoFilter ref="A1:AA%d"/></worksheet>'%(len(rows)+1)
 files={
  '[Content_Types].xml':'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>',
  '_rels/.rels':'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
  'xl/workbook.xml':'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Leads" sheetId="1" r:id="rId1"/></sheets></workbook>',
  'xl/_rels/workbook.xml.rels':'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
  'xl/worksheets/sheet1.xml':sheet,
 }
 buf=io.BytesIO()
 with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
  for name,content in files.items():z.writestr(name,content)
 return buf.getvalue()

def column_name(number):
 name=''
 while number:
  number,rem=divmod(number-1,26);name=chr(65+rem)+name
 return name
# These public instances allow use in any project; cache and rate limits still apply.
OVERPASS_PROVIDERS=(
 ('VK Maps','https://maps.mail.ru/osm/tools/overpass/api/interpreter',55),
 ('Private.coffee','https://overpass.private.coffee/api/interpreter',20),
)
def business_query(category,lat,lon,radius):
 clauses=[]
 for key,value in CATEGORIES[category]:
  tag='["'+key+'"]' if value=='.*' else '["'+key+'"="'+value+'"]'
  clauses.append('nwr'+tag+'(around:'+str(radius)+','+str(lat)+','+str(lon)+');')
 body=clauses[0] if len(clauses)==1 else '('+''.join(clauses)+');'
 return '[out:json][timeout:45];'+body+'out center tags;'
def fetch_businesses(query):
 payload=urllib.parse.urlencode({'data':query}).encode()
 for name,url,timeout in OVERPASS_PROVIDERS:
  # Brief shared cooldown prevents hammering an unavailable provider.
  if cached('provider-down:'+name):continue
  try:
   data=external(url,payload,timeout=timeout)
   if not isinstance(data,dict) or data.get('remark') or not isinstance(data.get('elements'),list):raise UpstreamError('Respuesta incompleta')
   return data,name
  except UpstreamError:
   put_cache('provider-down:'+name,True,60)
 raise UpstreamError('Los proveedores de negocios no respondieron. Espera un minuto o prueba un radio menor.')
def nominatim(params):
 # Shared throttle for every geocoding request, including candidate lookup.
 c=db();c.execute('BEGIN IMMEDIATE');row=c.execute("SELECT at FROM external WHERE k='geocode'").fetchone();wait=max(0,1.1-(time.time()-row['at'])) if row else 0
 if wait:time.sleep(wait)
 c.execute("INSERT OR REPLACE INTO external VALUES('geocode',?)",(time.time(),));c.commit()
 return external('https://nominatim.openstreetmap.org/search?'+urllib.parse.urlencode(params),timeout=10)
def location_candidates(city):
 key='locations:'+city.lower();found=cached(key)
 if found is not None:return found
 rows=nominatim({'q':city,'format':'json','limit':5})
 vals=[{'lat':float(r['lat']),'lon':float(r['lon']),'name':r['display_name']} for r in rows]
 put_cache(key,vals,604800);return vals
@app.post('/api/locations')
@auth(['Owner','Member'])
def locations():
 x=request.get_json() or {}
 if not isinstance(x,dict):return jsonify(error='Solicitud inválida.'),400
 city=x.get('city')
 if not isinstance(city,str) or not 2<=len(city.strip())<=150:return jsonify(error='Escribe ciudad, estado y país (2 a 150 caracteres).'),400
 if not rate('locations:global',10,60) or not rate('locations:'+g.user['id'],5,60):return jsonify(error='Espera un minuto antes de buscar otra ciudad.'),429
 try:return jsonify(locations=location_candidates(city.strip()))
 except UpstreamError as ex:return jsonify(error=str(ex)),502
def coordinate_location(value):
 if not isinstance(value,dict):raise ValueError('Ubicación inválida')
 lat=value.get('lat');lon=value.get('lon')
 if any(isinstance(n,bool) or not isinstance(n,(int,float)) or not math.isfinite(n) for n in (lat,lon)):raise ValueError('Coordenadas inválidas')
 if not -90<=lat<=90 or not -180<=lon<=180:raise ValueError('Coordenadas fuera de rango')
 return {'lat':lat,'lon':lon,'name':clean(value.get('name'),200) or 'Mi ubicación'}
def geocode(city):
 key='geo:'+city.lower();found=cached(key)
 if found:return found
 rows=nominatim({'q':city,'format':'json','limit':1})
 if not rows:raise UpstreamError('No encontramos esa ubicación. Añade ciudad, estado y país.')
 val={'lat':float(rows[0]['lat']),'lon':float(rows[0]['lon']),'name':rows[0]['display_name']};put_cache(key,val,604800);return val
SOCIAL_HOSTS={'facebook':('facebook.com','fb.com','fb.me'),'instagram':('instagram.com',),'linkedin':('linkedin.com',),'x':('x.com','twitter.com'),'tiktok':('tiktok.com',),'youtube':('youtube.com','youtu.be'),'whatsapp':('whatsapp.com','wa.me','api.whatsapp.com')}
def safe_socials(values):
 if not isinstance(values,list):return []
 out=[]
 for item in values[:10]:
  if not isinstance(item,dict):continue
  platform=clean(item.get('platform'),20).lower();url=safe_url(item.get('url'))
  if platform not in SOCIAL_HOSTS or not url:continue
  host=(urllib.parse.urlparse(url).hostname or '').lower().rstrip('.')
  if not any(host==domain or host.endswith('.'+domain) for domain in SOCIAL_HOSTS[platform]):continue
  if url not in [entry['url'] for entry in out]:out.append({'platform':platform,'url':url})
 return out[:8]
def parse_socials(tags):
 values=[]
 for platform in SOCIAL_HOSTS:
  for key in ('contact:'+platform,platform):
   if platform=='x':keys=('contact:x','x','contact:twitter','twitter')
   else:keys=(key,)
   for candidate in keys:
    if tags.get(candidate):values.append({'platform':platform,'url':tags[candidate]})
 return safe_socials(values)
def parse_places(elements,category):
 out=[]
 for el in elements:
  t=el.get('tags',{});name=t.get('name','').strip();center=el.get('center',el)
  if not name or 'lat' not in center or 'lon' not in center:continue
  if t.get('disused')=='yes' or t.get('abandoned')=='yes' or t.get('end_date') or t.get('opening_hours')=='closed':continue
  website=safe_url(t.get('website') or t.get('contact:website'));phone=clean(t.get('phone') or t.get('contact:phone'));email=clean(t.get('email') or t.get('contact:email'))
  out.append({'id':'osm_'+el['type']+'_'+str(el['id']),'name':clean(name),'category':category,'address':clean(t.get('addr:full') or ' '.join(filter(None,[t.get('addr:street'),t.get('addr:housenumber')]))),'city':clean(t.get('addr:city')),'state':clean(t.get('addr:state')),'phone':phone,'email':email,'website':website,'socials':parse_socials(t),'websiteStatus':'encontrada' if website else 'por_verificar','activity':'sin_verificar','lat':float(center['lat']),'lon':float(center['lon']),'source':'OpenStreetMap','sourceUrl':'https://www.openstreetmap.org/'+el['type']+'/'+str(el['id']),'collectedAt':int(time.time())})
 return out[:200]
@app.post('/api/search')
@auth(['Owner','Member'])
def search():
 x=request.get_json() or {}
 if not isinstance(x,dict):return jsonify(error='Solicitud inválida.'),400
 category=x.get('category');city=clean(x.get('city'),150)
 try:radius=int(x.get('radius',5000))
 except (ValueError,TypeError):radius=0
 if not isinstance(category,str) or category not in CATEGORIES or (not city and 'location' not in x) or radius not in (2000,5000,10000,20000):return jsonify(error='Selecciona sector, ubicación y radio válidos.'),400
 try:chosen=coordinate_location(x['location']) if 'location' in x else None
 except ValueError:return jsonify(error='La ubicación no es válida. Elige otra ciudad o vuelve a usar Encontrarme.'),400
 target=['coordinates',chosen['lat'],chosen['lon']] if chosen else city.lower()
 key='search:'+json.dumps([category,target,radius]);results=cached(key)
 if results:return jsonify(**results,cached=True)
 if not rate('search:global',10,60) or not rate('search:'+g.user['id'],5,60):return jsonify(error='Espera un minuto antes de otra búsqueda.'),429
 try:
  location=chosen or geocode(city);lat,lon=location['lat'],location['lon']
  data,provider=fetch_businesses(business_query(category,lat,lon,radius))
  results={'businesses':parse_places(data['elements'],category),'location':location,'source':'OpenStreetMap','provider':provider,'notice':'Una web no registrada no significa que el negocio no tenga página. La actividad requiere revisión manual.'};put_cache(key,results,3600);return jsonify(**results,cached=False)
 except UpstreamError as ex:return jsonify(error=str(ex)),502
@app.post('/api/apollo/search')
@auth(['Owner','Member'])
def apollo_search():
 x=request.get_json() or {}
 if not isinstance(x,dict):return jsonify(error='Solicitud inválida.'),400
 location=x.get('location');title_text=x.get('titles','');keyword_value=x.get('keyword','')
 if not isinstance(location,str) or not 2<=len(location.strip())<=120:return jsonify(error='Escribe la ubicación de la sede de la empresa.'),400
 if not isinstance(title_text,str) or len(title_text)>500:return jsonify(error='Revisa los cargos de contacto.'),400
 if not isinstance(keyword_value,str) or len(keyword_value)>120:return jsonify(error='La palabra clave puede tener hasta 120 caracteres.'),400
 keyword=clean(keyword_value,120)
 titles=[clean(t,80) for t in re.split(r'[;\n]+',title_text) if clean(t,80)]
 if not titles or len(titles)>8:return jsonify(error='Indica entre 1 y 8 cargos, separados por punto y coma.'),400
 size=x.get('size','1,200')
 if size not in ('1,10','11,50','51,200','1,200','201,500'):return jsonify(error='El tamaño de empresa no es válido.'),400
 try:per_page=int(x.get('limit',25))
 except (ValueError,TypeError):per_page=0
 if per_page not in (10,25,50):return jsonify(error='Elige un máximo de 10, 25 o 50 resultados.'),400
 try:page=int(x.get('page',1))
 except (ValueError,TypeError):page=0
 if not 1<=page<=500:return jsonify(error='La página solicitada no es válida.'),400
 if not os.environ.get('APOLLO_API_KEY','').strip():return jsonify(error='Apollo no está configurado. El administrador debe añadir la clave API en el servidor.'),503
 if not rate('apollo:global',10,60) or not rate('apollo:'+g.user['id'],5,60):return jsonify(error='Espera un minuto antes de volver a buscar.'),429
 params=[('person_titles[]',t) for t in titles]+[('organization_locations[]',location.strip()),('organization_num_employees_ranges[]',size),('page',page),('per_page',per_page)]
 if keyword:params.append(('q_keywords',keyword))
 try:
  payload=apollo_search_request(params);prospects=[]
  for person in payload['people'][:per_page]:
   if not isinstance(person,dict) or not person.get('id'):continue
   org=person.get('organization') if isinstance(person.get('organization'),dict) else {}
   contact=' '.join(str(v).strip() for v in (person.get('first_name'),person.get('last_name_obfuscated')) if v)
   company=clean(org.get('name'),200)
   if not company and not contact:continue
   prospects.append({'id':'apollo_'+clean(person.get('id'),120),'name':company or contact,'contactName':clean(contact,200),'title':clean(person.get('title'),150),'category':'Contacto de empresa','city':'','state':'','phone':'','email':'','emailAvailable':bool(person.get('has_email')),'directPhoneAvailable':clean(person.get('has_direct_phone'),80),'source':'Apollo','sourceUrl':'https://app.apollo.io/','apolloId':clean(person.get('id'),120),'apolloRefreshedAt':clean(person.get('last_refreshed_at'),60),'websiteStatus':'por_verificar','activity':'sin_verificar','collectedAt':int(time.time())})
  total=payload.get('total_entries',0);total=total if isinstance(total,int) and not isinstance(total,bool) and total>=0 else 0
  return jsonify(prospects=prospects,total=total,shown=len(prospects),page=page,perPage=per_page,source='Apollo',notice='Apollo muestra el apellido parcialmente oculto y no entrega el correo ni el teléfono en esta búsqueda. Revisar disponibilidad no recupera esos datos ni consume créditos de enriquecimiento.')
 except RuntimeError as ex:return jsonify(error=str(ex)),503
 except UpstreamError as ex:return jsonify(error=str(ex)),502
@app.post('/api/apollo/enrich')
@auth(['Owner','Member'])
def apollo_enrich():
 x=request.get_json() or {};apollo_id=x.get('apolloId') if isinstance(x,dict) else None
 if not isinstance(apollo_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,120}',apollo_id):return jsonify(error='El contacto de Apollo no tiene un identificador válido.'),400
 if not os.environ.get('APOLLO_API_KEY','').strip():return jsonify(error='Apollo no está conectado. Falta configurar su clave API en el servidor.'),503
 if not rate('apollo-enrich:global',50,3600) or not rate('apollo-enrich:'+g.user['id'],10,3600):return jsonify(error='Has alcanzado el límite de enriquecimientos de esta hora.'),429
 try:
  payload=apollo_enrich_request(apollo_id);person=payload.get('person') if isinstance(payload.get('person'),dict) else {}
  email=clean(person.get('email'),254);email=email if re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) else ''
  profile_socials=safe_socials([{'platform':'linkedin','url':person.get('linkedin_url')},{'platform':'facebook','url':person.get('facebook_url')},{'platform':'x','url':person.get('twitter_url')}])
  organization=person.get('organization') if isinstance(person.get('organization'),dict) else {}
  website=safe_url(organization.get('website_url') or organization.get('website'))
  return jsonify(contactName=clean(person.get('name') or ' '.join(filter(None,(person.get('first_name'),person.get('last_name')))),200),email=email,emailStatus=clean(person.get('email_status'),40),socials=profile_socials,website=website,matchConfidence=clean(payload.get('match_confidence'),20),found=bool(email or website or profile_socials),creditNote='Apollo puede consumir entre 1 y 9 créditos según los datos devueltos. No se solicitó teléfono móvil ni se activó enriquecimiento en cascada.')
 except RuntimeError as ex:return jsonify(error=str(ex)),503
 except UpstreamError as ex:return jsonify(error=str(ex)),502
@app.post('/api/sam/search')
@auth(['Owner','Member'])
def sam_search():
 x=request.get_json() or {}
 if not isinstance(x,dict):return jsonify(error='Solicitud inválida.'),400
 title=x.get('title','');state=x.get('state','');start=x.get('postedFrom','');end=x.get('postedTo','')
 if not isinstance(title,str) or not 2<=len(title.strip())<=120:return jsonify(error='Escribe un tipo de servicio o palabra clave.'),400
 if not isinstance(state,str) or (state and not re.fullmatch(r'[A-Z]{2}',state)):return jsonify(error='Elige un estado de EE. UU. válido.'),400
 try:
  from_date=datetime.strptime(start,'%m/%d/%Y').date() if isinstance(start,str) and '/' in start else datetime.strptime(start,'%Y-%m-%d').date()
  to_date=datetime.strptime(end,'%m/%d/%Y').date() if isinstance(end,str) and '/' in end else datetime.strptime(end,'%Y-%m-%d').date()
 except (TypeError,ValueError):return jsonify(error='Indica un intervalo de fechas válido.'),400
 if to_date<from_date or (to_date-from_date).days>365:return jsonify(error='El intervalo debe ser de hasta un año y en orden correcto.'),400
 try:limit=int(x.get('limit',25));offset=int(x.get('offset',0))
 except (TypeError,ValueError):return jsonify(error='Revisa la página y cantidad de resultados.'),400
 if limit not in (10,25,50) or not 0<=offset<=500:return jsonify(error='Elige 10, 25 o 50 resultados y una página entre 1 y 501.'),400
 if not os.environ.get('SAM_GOV_API_KEY','').strip():return jsonify(error='SAM.gov no está conectado. Falta configurar su clave API como secreto del servidor.'),503
 if not rate('sam:global',10,60) or not rate('sam:'+g.user['id'],5,60):return jsonify(error='Espera un minuto antes de otra búsqueda.'),429
 params=[('title',title.strip()),('postedFrom',from_date.strftime('%m/%d/%Y')),('postedTo',to_date.strftime('%m/%d/%Y')),('limit',limit),('offset',offset)]
 if state:params.append(('state',state))
 try:
  payload=sam_search_request(params);leads=[]
  for item in payload['opportunitiesData'][:limit]:
   if not isinstance(item,dict) or not item.get('noticeId'):continue
   contacts=item.get('pointOfContact') or item.get('pointofContact') or item.get('point_of_contact');contacts=contacts if isinstance(contacts,list) else [contacts] if isinstance(contacts,dict) else []
   contact=next((c for c in contacts if isinstance(c,dict) and any(c.get(k) for k in ('email','phone','fullName','fullname'))),{})
   place=item.get('placeOfPerformance') if isinstance(item.get('placeOfPerformance'),dict) else {}
   city=place.get('city') if isinstance(place.get('city'),dict) else {};region=place.get('state') if isinstance(place.get('state'),dict) else {}
   agency=clean(item.get('organizationName') or item.get('fullParentPathName') or '.'.join(filter(None,(item.get('department'),item.get('subTier'),item.get('office')))),250)
   source_url=safe_url(item.get('uiLink') or '')
   leads.append({'id':'sam_'+clean(item.get('noticeId'),120),'name':clean(item.get('title'),200) or 'Oportunidad de contrato público','category':'Oportunidad federal','agency':agency,'contactName':clean(contact.get('fullName') or contact.get('fullname'),200),'title':clean(contact.get('title'),150),'phone':clean(contact.get('phone'),100),'email':clean(contact.get('email'),200),'address':'','city':clean(city.get('name'),150),'state':clean(region.get('code') or region.get('name'),80) or state,'website':'','websiteStatus':'por_verificar','activity':'sin_verificar','source':'SAM.gov','sourceUrl':source_url,'opportunityId':clean(item.get('noticeId'),120),'solicitationNumber':clean(item.get('solicitationNumber'),120),'responseDeadline':clean(item.get('responseDeadLine') or item.get('reponseDeadLine'),50),'naicsCode':clean(item.get('naicsCode'),20),'dataKind':'government_opportunity','collectedAt':int(time.time())})
  total=payload.get('totalRecords',0);total=total if isinstance(total,int) and not isinstance(total,bool) and total>=0 else 0
  return jsonify(leads=leads,total=total,shown=len(leads),offset=offset,limit=limit,source='SAM.gov',notice='Oportunidades de compra del gobierno; la información de contacto pertenece al responsable público de contratación cuando está publicada.')
 except RuntimeError as ex:return jsonify(error=str(ex)),503
 except UpstreamError as ex:return jsonify(error=str(ex)),502
@app.get('/api/leads')
@auth()
def leads():return jsonify(leads=[dict(json.loads(r['data']),stage=r['stage'],notes=r['notes'],assignee=r['assignee'],updated=r['updated']) for r in db().execute('SELECT * FROM leads ORDER BY updated DESC')])
@app.post('/api/leads')
@auth(['Owner','Member'])
def save_leads():
 x=request.get_json() or {};rows=x.get('leads',[])
 if not isinstance(rows,list) or len(rows)>200:return jsonify(error='Máximo 200 prospectos por operación.'),400
 count=0
 for row in rows:
  if not isinstance(row,dict) or not clean(row.get('name')):continue
  lead={k:clean(row.get(k),1000 if k in ('website','sourceUrl') else 200) for k in ['id','name','category','address','city','state','phone','email','emailStatus','website','source','sourceUrl','websiteStatus','activity','contactName','title','apolloId','apolloRefreshedAt','directPhoneAvailable','agency','opportunityId','solicitationNumber','responseDeadline','naicsCode','dataKind']}
  lead['socials']=safe_socials(row.get('socials'))
  lead['emailAvailable']=bool(row.get('emailAvailable'))
  lead['website']=safe_url(lead['website']);lead['sourceUrl']=safe_url(lead['sourceUrl']);lead['id']=clean(lead['id'],150) or 'manual_'+secrets.token_hex(12)
  lead['websiteStatus']=lead['websiteStatus'] if lead['websiteStatus'] in ('encontrada','sin_web_confirmada','por_verificar','deficiente') else ('encontrada' if lead['website'] else 'por_verificar')
  for k in ('lat','lon'):
   try:
    value=float(row.get(k));lead[k]=value if math.isfinite(value) and abs(value)<=(90 if k=='lat' else 180) else None
   except (TypeError,ValueError):lead[k]=None
  lead['collectedAt']=int(time.time())
  c=db().execute('INSERT OR IGNORE INTO leads VALUES(?,?,?,?,?,?)',(lead['id'],json.dumps(lead),'detectado','','',int(time.time())));count+=c.rowcount
 audit('save_leads',str(count));db().commit();return jsonify(added=count)
@app.patch('/api/leads/<lid>')
@auth(['Owner','Member'])
def edit_lead(lid):
 r=db().execute('SELECT * FROM leads WHERE id=?',(lid,)).fetchone()
 if not r:return jsonify(error='Prospecto no encontrado.'),404
 x=request.get_json() or {};stage=x.get('stage',r['stage']);assignee=clean(x.get('assignee',r['assignee']),100);data=json.loads(r['data'])
 if stage not in STAGES or (assignee and not db().execute('SELECT 1 FROM users WHERE id=? AND active=1',(assignee,)).fetchone()):return jsonify(error='Etapa o responsable no válido.'),400
 if 'websiteStatus' in x:
  if x['websiteStatus'] not in ('encontrada','sin_web_confirmada','por_verificar','deficiente'):return jsonify(error='Estado de web no válido.'),400
  data['websiteStatus']=x['websiteStatus']
 if 'activity' in x:data['activity']='confirmada' if x['activity']=='confirmada' else 'sin_verificar'
 if 'website' in x:data['website']=safe_url(x['website'])
 db().execute('UPDATE leads SET data=?,stage=?,notes=?,assignee=?,updated=? WHERE id=?',(json.dumps(data),stage,clean(x.get('notes',r['notes']),6000),assignee,int(time.time()),lid));audit('edit_lead',lid);db().commit();return jsonify(ok=True)
@app.get('/api/export')
@auth()
def export():
 buf=io.StringIO();writer=csv.writer(buf);writer.writerow(['Empresa u oportunidad','Contacto','Cargo','Teléfono','Correo','Estado del correo','Dirección','Ciudad','Estado','Web','Redes sociales','Agencia','Estado web','Etapa','Número de solicitud','Fecha límite','Notas','Fuente'])
 for r in db().execute('SELECT * FROM leads'):
  d=json.loads(r['data']);socials=', '.join(f"{s.get('platform')}: {s.get('url')}" for s in d.get('socials',[]) if isinstance(s,dict));fields=[d.get(k,'') for k in ('name','contactName','title','phone','email','emailStatus','address','city','state','website')]+[socials,d.get('agency',''),d.get('websiteStatus',''),r['stage'],d.get('solicitationNumber',''),d.get('responseDeadline',''),r['notes'],d.get('sourceUrl') or d.get('source','')]
  writer.writerow([("'"+str(v)) if str(v).lstrip().startswith(('=','+','-','@','\t','\r')) else str(v) for v in fields])
 return Response('\ufeff'+buf.getvalue(),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename="webleads.csv"'})
@app.get('/api/export.xlsx')
@auth()
def export_xlsx():
 rows=[]
 for r in db().execute('SELECT leads.*,users.name AS assignee_name FROM leads LEFT JOIN users ON users.id=leads.assignee ORDER BY leads.updated DESC'):
  d=json.loads(r['data']);rows.append({**d,'stage':r['stage'],'notes':r['notes'],'assignee':r['assignee_name'] or '', 'updated':datetime.fromtimestamp(r['updated'],timezone.utc).isoformat(timespec='seconds')})
 data=build_xlsx(rows)
 return Response(data,mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':'attachment; filename="webleads-leads.xlsx"','Content-Length':str(len(data))})
if __name__=='__main__':app.run(host='127.0.0.1',port=3210)
