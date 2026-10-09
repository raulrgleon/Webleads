import csv, functools, hashlib, io, json, math, os, re, secrets, sqlite3, time
import urllib.request, urllib.parse, urllib.error
from pathlib import Path
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
def external(url,data=None):
 req=urllib.request.Request(url,data=data,headers={'User-Agent':'DNET-WebLeads/2.0 (+https://dnet.llc; contacto: raulrgleon@gmail.com)','Accept':'application/json'})
 try:
  with urllib.request.urlopen(req,timeout=35) as r:return json.load(r)
 except (OSError,ValueError,urllib.error.HTTPError) as ex:raise UpstreamError('El proveedor de mapas no respondió. Espera un minuto e inténtalo de nuevo.') from ex
def geocode(city):
 key='geo:'+city.lower();found=cached(key)
 if found:return found
 # Cross-worker throttle; persistent cache avoids repeating queries.
 c=db();c.execute('BEGIN IMMEDIATE');row=c.execute("SELECT at FROM external WHERE k='geocode'").fetchone();wait=max(0,1.1-(time.time()-row['at'])) if row else 0
 if wait:time.sleep(wait)
 c.execute("INSERT OR REPLACE INTO external VALUES('geocode',?)",(time.time(),));c.commit()
 rows=external('https://nominatim.openstreetmap.org/search?'+urllib.parse.urlencode({'q':city,'format':'json','limit':1}))
 if not rows:raise UpstreamError('No encontramos esa ubicación. Añade ciudad, estado y país.')
 val={'lat':float(rows[0]['lat']),'lon':float(rows[0]['lon']),'name':rows[0]['display_name']};put_cache(key,val,604800);return val
def parse_places(elements,category):
 out=[]
 for el in elements:
  t=el.get('tags',{});name=t.get('name','').strip();center=el.get('center',el)
  if not name or 'lat' not in center or 'lon' not in center:continue
  if t.get('disused')=='yes' or t.get('abandoned')=='yes' or t.get('end_date') or t.get('opening_hours')=='closed':continue
  website=safe_url(t.get('website') or t.get('contact:website'));phone=clean(t.get('phone') or t.get('contact:phone'));email=clean(t.get('email') or t.get('contact:email'))
  out.append({'id':'osm_'+el['type']+'_'+str(el['id']),'name':clean(name),'category':category,'address':clean(t.get('addr:full') or ' '.join(filter(None,[t.get('addr:street'),t.get('addr:housenumber')]))),'city':clean(t.get('addr:city')),'state':clean(t.get('addr:state')),'phone':phone,'email':email,'website':website,'websiteStatus':'encontrada' if website else 'por_verificar','activity':'sin_verificar','lat':float(center['lat']),'lon':float(center['lon']),'source':'OpenStreetMap','sourceUrl':'https://www.openstreetmap.org/'+el['type']+'/'+str(el['id']),'collectedAt':int(time.time())})
 return out[:200]
@app.post('/api/search')
@auth(['Owner','Member'])
def search():
 x=request.get_json() or {};category=x.get('category');city=clean(x.get('city'),150)
 try:radius=int(x.get('radius',5000))
 except (ValueError,TypeError):radius=0
 if category not in CATEGORIES or not city or radius not in (2000,5000,10000,20000):return jsonify(error='Selecciona sector, ubicación y radio válidos.'),400
 key='search:'+json.dumps([category,city.lower(),radius]);results=cached(key)
 if results:return jsonify(**results,cached=True)
 if not rate('search:global',10,60) or not rate('search:'+g.user['id'],5,60):return jsonify(error='Espera un minuto antes de otra búsqueda.'),429
 try:
  location=geocode(city);lat,lon=location['lat'],location['lon'];query='[out:json][timeout:25];('+''.join('nwr["'+k+'"~"'+v+'"](around:'+str(radius)+','+str(lat)+','+str(lon)+');' for k,v in CATEGORIES[category])+');out center tags;'
  data=external('https://overpass-api.de/api/interpreter',urllib.parse.urlencode({'data':query}).encode());results={'businesses':parse_places(data.get('elements',[]),category),'location':location,'source':'OpenStreetMap','notice':'Una web no registrada no significa que el negocio no tenga página. La actividad requiere revisión manual.'};put_cache(key,results,3600);return jsonify(**results,cached=False)
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
  lead={k:clean(row.get(k),1000 if k in ('website','sourceUrl') else 200) for k in ['id','name','category','address','city','state','phone','email','website','source','sourceUrl','websiteStatus','activity']}
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
 buf=io.StringIO();writer=csv.writer(buf);writer.writerow(['Nombre','Teléfono','Correo','Dirección','Ciudad','Web','Estado web','Etapa','Notas','Fuente'])
 for r in db().execute('SELECT * FROM leads'):
  d=json.loads(r['data']);fields=[d.get(k,'') for k in ('name','phone','email','address','city','website','websiteStatus')]+[r['stage'],r['notes'],d.get('sourceUrl','')]
  writer.writerow([("'"+str(v)) if str(v).lstrip().startswith(('=','+','-','@','\t','\r')) else str(v) for v in fields])
 return Response('\ufeff'+buf.getvalue(),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename="webleads.csv"'})
if __name__=='__main__':app.run(host='127.0.0.1',port=3210)
