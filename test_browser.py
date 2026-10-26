"""UI regression with synthetic leads/API; run against a local static server.
Requires Playwright in the development environment, not production.
"""
import json
from playwright.sync_api import sync_playwright, expect


def run():
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True)
  context=browser.new_context(geolocation={'latitude':40.4168,'longitude':-3.7038,'accuracy':25},permissions=['geolocation'],viewport={'width':390,'height':844})
  page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  state={'requests':[], 'empty':False, 'fail':False, 'saved':[], 'apollo_requests':[],'sam_requests':[],'enrich_requests':[]}
  def api(route):
   path=route.request.url.split('/api/')[1];body=route.request.post_data_json if route.request.method=='POST' else {}
   status=200
   if path=='me':data={'user':{'id':'qa','name':'QA','role':'Owner','csrf':'synthetic'},'categories':['dentistas'],'stages':['detectado']}
   elif path=='team':data={'users':[]}
   elif path=='integrations':data={'apollo':{'configured':True},'samGov':{'configured':True}}
   elif path=='leads':
    if route.request.method=='POST':
     new_rows=[{**lead,'stage':'detectado','notes':'','assignee':'','updated':1} for lead in body.get('leads',[])]
     state['saved'].extend(new_rows);data={'added':len(new_rows)}
    else:data={'leads':state['saved']}
   elif path=='apollo/search':
    state['apollo_requests'].append(body);page_no=body.get('page',1)
    name='Empresa QA' if page_no==1 else 'Empresa QA página 2'
    data={'prospects':[{'id':'apollo-qa-'+str(page_no),'apolloId':'person12345','name':name,'contactName':'Ana R***z','title':'Owner','emailAvailable':True,'directPhoneAvailable':'Yes','source':'Apollo','sourceUrl':'https://app.apollo.io/'}],'total':30,'shown':1,'page':page_no,'notice':'Datos de contacto limitados'}
   elif path=='apollo/enrich':
    state['enrich_requests'].append(body);data={'contactName':'Ana Rivera','email':'ana@example.test','emailStatus':'verified','website':'https://example.test','socials':[{'platform':'linkedin','url':'https://linkedin.com/company/example'}],'found':True}
   elif path=='sam/search':
    state['sam_requests'].append(body);data={'leads':[{'id':'sam-qa','name':'IT support opportunity','agency':'Agency QA','contactName':'Jane Doe','title':'Contracting Officer','phone':'202-555-0100','email':'jane@example.test','source':'SAM.gov','sourceUrl':'https://sam.gov/opp/qa','dataKind':'government_opportunity'}],'total':1,'offset':body['offset'],'limit':body['limit'],'notice':'Aviso oficial'}
   elif path=='locations':data={'locations':[{'lat':48.85,'lon':2.35,'name':'París, Francia'},{'lat':33.66,'lon':-95.55,'name':'Paris, Texas, Estados Unidos'}]}
   elif path=='search':
    state['requests'].append(body)
    if state['fail']:status=502;data={'error':'Proveedor no disponible'}
    else:data={'businesses':[] if state['empty'] else [{'id':'qa-lead','name':'Negocio ficticio QA','address':'Calle de prueba','city':'Madrid','websiteStatus':'por_verificar','sourceUrl':'https://www.openstreetmap.org','lat':40.4,'lon':-3.7}], 'location':body['location'],'cached':False}
   else:raise AssertionError(path)
   route.fulfill(status=status,content_type='application/json',body=json.dumps(data))
  page.route('**/api/**',api)
  page.on('dialog',lambda dialog:dialog.accept())
  page.goto('http://localhost:3211/static/index.html');page.wait_for_load_state('networkidle')
  page.locator('[data-view="sources"]').click();page.locator('#sourceLocation').fill('Auburn, Nebraska');assert 'Auburn%2C%20Nebraska' in page.locator('#sourceMaps').get_attribute('href');page.locator('#samSearchForm button').click();expect(page.locator('#samResults')).to_contain_text('IT support opportunity');expect(page.locator('#samResults')).to_contain_text('jane@example.test');page.locator('#samResults button').click();expect(page.locator('#pipeline')).to_contain_text('IT support opportunity');assert state['sam_requests'][0]['postedFrom'].count('/')==2
  page.locator('[data-view="search"]').click();page.locator('#apolloSearchForm button').click();expect(page.locator('#apolloResults')).to_contain_text('Empresa QA');expect(page.locator('#apolloResults')).to_contain_text('Ana R***z');page.locator('#apolloResults').get_by_role('button',name='Solicitar correo').click();expect(page.locator('#apolloResults')).to_contain_text('ana@example.test');assert state['enrich_requests'][0]['apolloId']=='person12345';page.locator('#apolloNext').click();expect(page.locator('#apolloResults')).to_contain_text('Empresa QA página 2');assert state['apollo_requests'][-1]['page']==2
  page.locator('#apolloResults').get_by_role('button',name='Guardar',exact=True).click();expect(page.locator('#pipeline')).to_contain_text('Empresa QA');expect(page.locator('#apolloResults')).to_contain_text('Guardado')
  page.locator('[data-view="pipeline"]').click();page.get_by_role('link',name='Descargar Excel').wait_for();page.locator('[data-view="search"]').click()
  page.locator('#locateButton').click();expect(page.locator('#city')).to_have_value('Mi ubicación actual')
  page.locator('#searchButton').click();expect(page.locator('#results')).to_contain_text('Negocio ficticio QA')
  assert state['requests'][-1]['location']['lat']==40.4168
  state['empty']=True;page.locator('#searchButton').click();expect(page.locator('#resultCount')).to_have_text('0 de 0 negocios · OpenStreetMap');expect(page.locator('#results')).not_to_contain_text('Negocio ficticio QA')
  state['empty']=False;page.locator('#city').fill('Paris');page.locator('#searchButton').click();expect(page.locator('#locationChoicesLabel')).to_be_visible()
  assert len(state['requests'])==2
  page.locator('#locationChoices').select_option(index=2);page.locator('#searchButton').click();expect(page.locator('#results')).to_contain_text('Negocio ficticio QA');assert state['requests'][-1]['location']['lon']==-95.55
  expect(page.locator('#locationStatus')).to_contain_text('Texas')
  state['fail']=True;page.locator('#searchButton').click();expect(page.locator('#resultCount')).to_have_text('La búsqueda no pudo completarse.');expect(page.locator('#results')).not_to_contain_text('Negocio ficticio QA')
  page.evaluate("() => { navigator.geolocation.getCurrentPosition = (ok, fail) => fail({code:1}); }")
  page.locator('#locateButton').click();expect(page.locator('#locationStatus')).to_contain_text('Permiso de ubicación denegado')
  assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Mobile overflow'
  assert not errors,errors
  browser.close()
  print('Browser QA passed: Apollo enrichment confirmation, search, pagination and save; SAM.gov search, public contacts and save; source-link filters; local search, GPS, city selection, empty/error cleanup, permission denial and 390px layout; no JS errors.')

if __name__=='__main__':run()
