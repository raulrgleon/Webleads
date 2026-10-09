import os,tempfile,unittest,json,sqlite3,time
from unittest.mock import patch
_tmp=tempfile.TemporaryDirectory();os.environ['DATA_DIR']=_tmp.name
os.environ['APP_URL']='http://localhost:3210'
import app as m
class Tests(unittest.TestCase):
 def setUp(self):
  self.c=m.app.test_client()
  with m.app.app_context():
   for table in ('sessions','users','invites','leads','audit','limits','cache','external'):m.db().execute('DELETE FROM '+table)
   m.db().commit()
 def activate(self,role='Owner',email='owner@example.test'):
  t='one-use-test-token'
  with m.app.app_context():m.db().execute('INSERT INTO invites VALUES(?,?,?,?,0)',(m.token_hash(t),email,role,int(time.time()+1000)));m.db().commit()
  r=self.c.post('/api/activate',json={'token':t,'name':'Persona','password':'test-password-long-123'},headers={'Origin':m.BASE});self.assertEqual(r.status_code,200)
  self.csrf=self.c.get('/api/me').json['user']['csrf']
 def post(self,path,data,method='POST'):return self.c.open(path,method=method,json=data,headers={'Origin':m.BASE,'X-CSRF':getattr(self,'csrf','')})
 def test_unauthenticated(self):self.assertEqual(self.c.get('/api/leads').status_code,401)
 def test_activation_replay(self):
  self.activate();self.assertEqual(self.post('/api/activate',{'token':'one-use-test-token','password':'test-password-long-123'}).status_code,400)
 def test_origin(self):self.assertEqual(self.c.post('/api/login',json={},headers={'Origin':'https://evil.test'}).status_code,403)
 def test_csrf(self):self.activate();self.assertEqual(self.c.post('/api/leads',json={},headers={'Origin':m.BASE}).status_code,403)
 def test_viewer_denied(self):self.activate('Viewer');self.assertEqual(self.post('/api/leads',{'leads':[]}).status_code,403);self.assertEqual(self.post('/api/search',{'city':'Omaha','category':'dentistas'}).status_code,403)
 def test_member_invite_denied(self):self.activate('Member');self.assertEqual(self.post('/api/invites',{'email':'other@example.test'}).status_code,403)
 def test_leads_dedup(self):
  self.activate();x={'leads':[{'id':'x','name':'Clínica','website':'https://ejemplo.test','phone':'+14021234567'}]}
  self.assertEqual(self.post('/api/leads',x).json['added'],1);self.assertEqual(self.post('/api/leads',x).json['added'],0);r=self.c.get('/api/leads').json['leads'][0];self.assertEqual(r['website'],x['leads'][0]['website']);self.assertEqual(r['phone'],'+14021234567')
 def test_notes_stage(self):self.activate();self.post('/api/leads',{'leads':[{'id':'x','name':'Clínica'}]});self.assertEqual(self.post('/api/leads/x',{'stage':'propuesta','notes':'Preparar demo'},'PATCH').status_code,200);self.assertEqual(self.c.get('/api/leads').json['leads'][0]['notes'],'Preparar demo')
 def test_invalid_stage(self):self.activate();self.post('/api/leads',{'leads':[{'id':'x','name':'Clínica'}]});self.assertEqual(self.post('/api/leads/x',{'stage':'owner'},'PATCH').status_code,400)
 def test_csv_safe(self):self.activate();self.post('/api/leads',{'leads':[{'id':'x','name':'=HYPERLINK("bad")','phone':'+14021234567'}]});text=self.c.get('/api/export').data.decode();self.assertIn("'=HYPERLINK",text);self.assertIn("'+14021234567",text)
 def test_url_safe(self):self.assertEqual(m.safe_url('javascript:alert(1)'), '');self.assertEqual(m.safe_url('https://user:pass@evil.test'),'')
 def test_categories(self):self.assertIn(('amenity','dentist'),m.CATEGORIES['dentistas']);self.assertIn(('healthcare','physiotherapist'),m.CATEGORIES['fisioterapeutas']);self.assertIn(('shop','hairdresser'),m.CATEGORIES['peluquerias'])
 def test_osm_contacts(self):
  x=m.parse_places([{'id':1,'type':'node','lat':41,'lon':-96,'tags':{'name':'Clínica','contact:website':'https://ejemplo.test','contact:email':'info@ejemplo.test','addr:city':'Omaha'}}],'dentistas')[0]
  self.assertEqual(x['websiteStatus'],'encontrada');self.assertEqual(x['email'],'info@ejemplo.test');self.assertEqual(x['city'],'Omaha');self.assertEqual(x['activity'],'sin_verificar')
 def test_closed_excluded(self):self.assertEqual(m.parse_places([{'id':1,'type':'node','lat':41,'lon':-96,'tags':{'name':'Cerrado','disused':'yes'}}],'dentistas'),[])
 def test_unknown_missing_site(self):self.assertEqual(m.parse_places([{'id':1,'type':'node','lat':41,'lon':-96,'tags':{'name':'Negocio'}}],'dentistas')[0]['websiteStatus'],'por_verificar')
 def test_upstream_error(self):
  self.activate()
  with patch.object(m,'geocode',side_effect=m.UpstreamError('Proveedor no disponible')):self.assertEqual(self.post('/api/search',{'city':'Omaha','category':'dentistas','radius':5000}).status_code,502)
 def test_search_cached(self):
  self.activate()
  with m.app.app_context():m.put_cache('search:'+json.dumps(['dentistas','omaha',5000]),{'businesses':[],'location':{'lat':41,'lon':-96},'source':'OpenStreetMap','notice':''},3600)
  self.assertTrue(self.post('/api/search',{'city':'Omaha','category':'dentistas','radius':5000}).json['cached'])
 def test_revocation(self):
  self.activate('Member')
  with m.app.app_context():m.db().execute('UPDATE users SET active=0');m.db().commit()
  self.assertEqual(self.c.get('/api/leads').status_code,401)
 def test_static_private(self):self.assertEqual(self.c.get('/data/webleads.sqlite').status_code,404)
if __name__=='__main__':unittest.main()
