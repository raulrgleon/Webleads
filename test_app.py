import io,os,tempfile,unittest,json,sqlite3,time
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
 def test_xlsx_export_is_authenticated_and_contains_all_lead_fields(self):
  self.activate();self.post('/api/leads',{'leads':[{'id':'apollo_person1','name':'Empresa & Co','contactName':'Ana A***z','title':'Owner','source':'Apollo','apolloId':'person1','emailAvailable':True,'emailStatus':'verified','socials':[{'platform':'linkedin','url':'https://linkedin.com/company/example'}],'phone':'=1+1'}]})
  response=self.c.get('/api/export.xlsx');self.assertEqual(response.status_code,200);self.assertEqual(response.mimetype,'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
  import zipfile
  import xml.etree.ElementTree as ET
  with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
   self.assertEqual(archive.testzip(),None)
   for name in archive.namelist():
    if name.endswith('.xml'):ET.fromstring(archive.read(name))
   sheet=archive.read('xl/worksheets/sheet1.xml').decode()
   self.assertIn('Empresa &amp; Co',sheet);self.assertIn('Ana A***z',sheet);self.assertIn('person1',sheet);self.assertIn('verified',sheet);self.assertIn('linkedin.com/company/example',sheet);self.assertIn('=1+1',sheet);self.assertIn('A1:AA2',sheet);self.assertNotIn('<f>',sheet)
  self.c.post('/api/logout',json={},headers={'Origin':m.BASE,'X-CSRF':self.csrf});self.assertEqual(self.c.get('/api/export.xlsx').status_code,401)
 def test_apollo_unconfigured(self):
  self.activate()
  with patch.dict(os.environ,{},clear=False):
   os.environ.pop('APOLLO_API_KEY',None)
   self.assertFalse(self.c.get('/api/integrations').json['apollo']['configured'])
   self.assertEqual(self.post('/api/apollo/search',{'location':'United States','titles':'owner'}).status_code,503)
 def test_apollo_search_maps_limited_data_and_filters(self):
  self.activate()
  sample={'total_entries':18,'people':[{'id':'p1','first_name':'Ana','last_name_obfuscated':'Ro***z','title':'Owner','has_email':True,'has_direct_phone':'Yes','last_refreshed_at':'2026-01-02T00:00:00Z','organization':{'name':'Empresa Uno'}}]}
  with patch.dict(os.environ,{'APOLLO_API_KEY':'test-only'}),patch.object(m,'apollo_search_request',return_value=sample) as search:
   response=self.post('/api/apollo/search',{'location':'Florida, US','titles':'owner; founder','size':'1,10','keyword':'IT support','limit':10,'page':2})
  self.assertEqual(response.status_code,200);person=response.json['prospects'][0]
  self.assertEqual(person['name'],'Empresa Uno');self.assertEqual(person['contactName'],'Ana Ro***z');self.assertEqual(person['email'],'');self.assertEqual(person['phone'],'');self.assertTrue(person['emailAvailable']);self.assertEqual(response.json['total'],18)
  self.assertEqual(response.json['page'],2);params=search.call_args.args[0];self.assertIn(('person_titles[]','owner'),params);self.assertIn(('person_titles[]','founder'),params);self.assertIn(('organization_locations[]','Florida, US'),params);self.assertIn(('organization_num_employees_ranges[]','1,10'),params);self.assertIn(('page',2),params);self.assertIn(('q_keywords','IT support'),params)
 def test_apollo_viewer_denied(self):
  self.activate('Viewer');self.assertEqual(self.post('/api/apollo/search',{'location':'US','titles':'owner'}).status_code,403)
 def test_apollo_enrich_is_single_contact_and_maps_public_contacts(self):
  self.activate();sample={'person':{'name':'Ana Rivera','email':'ana@example.test','email_status':'verified','twitter_url':'https://x.com/ana','organization':{'website_url':'https://example.test'}}}
  with patch.dict(os.environ,{'APOLLO_API_KEY':'test-only'}),patch.object(m,'apollo_enrich_request',return_value=sample) as upstream:
   response=self.post('/api/apollo/enrich',{'apolloId':'person_12345'})
  self.assertEqual(response.status_code,200);self.assertEqual(response.json['email'],'ana@example.test');self.assertEqual(response.json['emailStatus'],'verified');self.assertEqual(response.json['website'],'https://example.test');self.assertEqual(response.json['socials'][0]['platform'],'x');self.assertNotIn('phone',response.json);upstream.assert_called_once_with('person_12345')
 def test_apollo_enrich_viewer_denied(self):
  self.activate('Viewer');self.assertEqual(self.post('/api/apollo/enrich',{'apolloId':'person_12345'}).status_code,403)
 def test_sam_requires_key_and_role(self):
  self.activate()
  with patch.dict(os.environ,{},clear=False):
   os.environ.pop('SAM_GOV_API_KEY',None);self.assertFalse(self.c.get('/api/integrations').json['samGov']['configured']);self.assertEqual(self.post('/api/sam/search',{'title':'IT support','postedFrom':'01/01/2026','postedTo':'01/15/2026'}).status_code,503)
  with m.app.app_context():m.db().execute("UPDATE users SET role='Viewer'");m.db().commit()
  self.assertEqual(self.post('/api/sam/search',{'title':'IT support'}).status_code,403)
 def test_sam_validates_dates_and_page_before_upstream(self):
  self.activate()
  with patch.dict(os.environ,{'SAM_GOV_API_KEY':'test-only'}):
   for payload in ({'title':'IT','postedFrom':'2025-01-01','postedTo':'2026-02-01'},{'title':'IT','postedFrom':'2026-03-01','postedTo':'2026-02-01'},{'title':'IT','postedFrom':'2026-01-01','postedTo':'2026-01-02','state':'California'}):
    with patch.object(m,'sam_search_request') as upstream:self.assertEqual(self.post('/api/sam/search',payload).status_code,400);upstream.assert_not_called()
 def test_sam_maps_opportunity_and_public_contact(self):
  self.activate();sample={'totalRecords':21,'opportunitiesData':[{'noticeId':'notice_123','title':'IT support contract','organizationName':'Agency One','solicitationNumber':'SOL-1','responseDeadLine':'2026-12-01','naicsCode':'541512','pointofContact':[{'fullName':'Jane Doe','title':'Contracting Officer','email':'jane@example.test','phone':'202-555-0100'}],'placeOfPerformance':{'city':{'name':'Auburn'},'state':{'code':'NE'}},'uiLink':'https://sam.gov/opp/123'}]}
  with patch.dict(os.environ,{'SAM_GOV_API_KEY':'test-only'}),patch.object(m,'sam_search_request',return_value=sample) as upstream:
   response=self.post('/api/sam/search',{'title':'IT support','state':'NE','postedFrom':'2026-01-01','postedTo':'2026-01-31','limit':10,'offset':10})
  self.assertEqual(response.status_code,200);lead=response.json['leads'][0];self.assertEqual(lead['email'],'jane@example.test');self.assertEqual(lead['phone'],'202-555-0100');self.assertEqual(lead['agency'],'Agency One');self.assertEqual(lead['dataKind'],'government_opportunity');self.assertEqual(response.json['total'],21);self.assertIn(('offset',10),upstream.call_args.args[0]);self.assertNotIn('test-only',str(upstream.call_args.args[0]))
 def test_apollo_validation(self):
  self.activate()
  for payload in ({'location':'US','titles':''},{'location':'US','titles':'owner','size':'0,999'},{'location':'US','titles':'owner','limit':100},{'location':'US','titles':'owner','page':501}):
   with patch.object(m,'apollo_search_request') as upstream:self.assertEqual(self.post('/api/apollo/search',payload).status_code,400);upstream.assert_not_called()
 def test_url_safe(self):self.assertEqual(m.safe_url('javascript:alert(1)'), '');self.assertEqual(m.safe_url('https://user:pass@evil.test'),'')
 def test_categories(self):self.assertIn(('amenity','dentist'),m.CATEGORIES['dentistas']);self.assertIn(('healthcare','physiotherapist'),m.CATEGORIES['fisioterapeutas']);self.assertIn(('shop','hairdresser'),m.CATEGORIES['peluquerias'])
 def test_osm_contacts(self):
  x=m.parse_places([{'id':1,'type':'node','lat':41,'lon':-96,'tags':{'name':'Clínica','contact:website':'https://ejemplo.test','contact:email':'info@ejemplo.test','contact:instagram':'https://instagram.com/clinica','addr:city':'Omaha'}}],'dentistas')[0]
  self.assertEqual(x['websiteStatus'],'encontrada');self.assertEqual(x['email'],'info@ejemplo.test');self.assertEqual(x['city'],'Omaha');self.assertEqual(x['activity'],'sin_verificar');self.assertEqual(x['socials'],[{'platform':'instagram','url':'https://instagram.com/clinica'}])
 def test_social_links_allowlist_and_lead_save(self):
  self.activate();socials=[{'platform':'linkedin','url':'https://linkedin.com/company/example'},{'platform':'instagram','url':'https://evil.test/profile'},{'platform':'x','url':'javascript:alert(1)'}]
  self.post('/api/leads',{'leads':[{'id':'socials','name':'Empresa','socials':socials}]});saved=self.c.get('/api/leads').json['leads'][0]['socials'];self.assertEqual(saved,[{'platform':'linkedin','url':'https://linkedin.com/company/example'}])
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
 def test_coordinate_search_uses_exact_location(self):
  self.activate()
  with patch.object(m,'geocode') as geo,patch.object(m,'external',return_value={'elements':[{'id':42,'type':'node','lat':40.4,'lon':-3.7,'tags':{'name':'Negocio de prueba','amenity':'dentist'}}]}) as upstream:
   r=self.post('/api/search',{'location':{'lat':40.4,'lon':-3.7,'name':'Madrid'},'category':'dentistas','radius':5000})
   self.assertEqual(r.status_code,200);self.assertEqual(r.json['location']['lat'],40.4);self.assertEqual(len(r.json['businesses']),1);geo.assert_not_called()
   query=upstream.call_args.args[1].decode();self.assertIn('40.4%2C-3.7',query)
 def test_invalid_coordinates_denied(self):
  self.activate()
  for loc in (None,{}, {'lat':91,'lon':0},{'lat':0,'lon':181},{'lat':'40','lon':0},{'lat':True,'lon':0},{'lat':float('inf'),'lon':0}):
   with self.subTest(location=loc),patch.object(m,'external') as upstream:
    self.assertEqual(self.post('/api/search',{'location':loc,'category':'dentistas','radius':5000}).status_code,400);upstream.assert_not_called()
 def test_coordinate_cache_separates_places(self):
  self.activate()
  with patch.object(m,'external',return_value={'elements':[]}) as upstream:
   first={'location':{'lat':40,'lon':-3},'category':'dentistas','radius':5000}
   self.assertFalse(self.post('/api/search',first).json['cached']);self.assertTrue(self.post('/api/search',first).json['cached'])
   first['location']['lat']=41;self.assertFalse(self.post('/api/search',first).json['cached']);self.assertEqual(upstream.call_count,2)
 def test_locations_candidates_and_cache(self):
  self.activate()
  rows=[{'lat':'40','lon':'-3','display_name':'Madrid, España'},{'lat':'41','lon':'-4','display_name':'Madrid, otra región'}]
  with patch.object(m,'nominatim',return_value=rows) as upstream:
   r=self.post('/api/locations',{'city':'Madrid'});self.assertEqual(r.status_code,200);self.assertEqual(len(r.json['locations']),2)
   self.assertEqual(self.post('/api/locations',{'city':'Madrid'}).json,r.json);upstream.assert_called_once()
 def test_locations_permissions(self):
  self.activate('Viewer');self.assertEqual(self.post('/api/locations',{'city':'Madrid'}).status_code,403)
 def test_locations_csrf(self):
  self.activate();self.assertEqual(self.c.post('/api/locations',json={'city':'Madrid'},headers={'Origin':m.BASE}).status_code,403)
 def test_locations_validation(self):
  self.activate()
  for city in ('','x','x'*151,[],123):self.assertEqual(self.post('/api/locations',{'city':city}).status_code,400)
 def test_locations_provider_failure(self):
  self.activate()
  with patch.object(m,'nominatim',side_effect=m.UpstreamError('Proveedor no disponible')):self.assertEqual(self.post('/api/locations',{'city':'Madrid'}).status_code,502)
 def test_locations_rate_limit(self):
  self.activate()
  with patch.object(m,'location_candidates',return_value=[]):
   for _ in range(5):self.assertEqual(self.post('/api/locations',{'city':'Madrid'}).status_code,200)
   self.assertEqual(self.post('/api/locations',{'city':'Madrid'}).status_code,429)
 def test_incomplete_provider_response_not_cached(self):
  self.activate()
  with patch.object(m,'external',return_value={'elements':[], 'remark':'runtime error: timeout'}):
   r=self.post('/api/search',{'location':{'lat':40,'lon':-3},'category':'dentistas','radius':5000})
   self.assertEqual(r.status_code,502)
  with m.app.app_context():self.assertEqual(m.db().execute("SELECT count(*) FROM cache WHERE k LIKE 'search:%'").fetchone()[0],0)
 def test_malformed_provider_response(self):
  self.activate()
  with patch.object(m,'external',return_value={}):self.assertEqual(self.post('/api/search',{'location':{'lat':40,'lon':-3},'category':'dentistas','radius':5000}).status_code,502)
 def test_business_provider_fallback(self):
  self.activate()
  with patch.object(m,'external',side_effect=[m.UpstreamError('No disponible'),{'elements':[]}]) as upstream:
   r=self.post('/api/search',{'location':{'lat':40,'lon':-3},'category':'dentistas','radius':5000})
   self.assertEqual(r.status_code,200);self.assertEqual(r.json['provider'],'Private.coffee');self.assertEqual(upstream.call_count,2)
 def test_provider_cooldown(self):
  with m.app.app_context(),patch.object(m,'external',side_effect=m.UpstreamError('No disponible')) as upstream:
   for _ in range(2):
    with self.assertRaises(m.UpstreamError):m.fetch_businesses('query')
   self.assertEqual(upstream.call_count,2)
 def test_query_exact_categories(self):
  q=m.business_query('dentistas',40,-3,5000);self.assertIn('["amenity"="dentist"]',q);self.assertNotIn('~',q)
  self.assertIn('["shop"]',m.business_query('tiendas',40,-3,5000))
if __name__=='__main__':unittest.main()
