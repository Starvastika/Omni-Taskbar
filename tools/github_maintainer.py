"""Maintainer-only GitHub API transport via normal Git Credential Manager.
Never prints/stores credentials, never reads VS Code secret databases, and never
ships in the consumer runtime. Git itself supplies existing authentication.
"""
import argparse,json,os,subprocess,urllib.error,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REPO='Starvastika/Omni-Taskbar'
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None
class GitHub:
 def __init__(self):
  remote=subprocess.check_output(['git','remote','get-url','origin'],cwd=ROOT,text=True).strip()
  if remote!='https://github.com/'+REPO+'.git':raise ValueError('Unexpected remote')
  response=subprocess.run(['git','credential','fill'],cwd=ROOT,input='protocol=https\nhost=github.com\npath='+REPO+'.git\n\n',text=True,capture_output=True,timeout=30,env=dict(os.environ,GIT_TERMINAL_PROMPT='0',GCM_INTERACTIVE='never'))
  if response.returncode:raise RuntimeError('Existing Git authentication is unavailable; use official sign-in')
  value=dict(line.split('=',1) for line in response.stdout.splitlines() if '=' in line)
  self._credential=value.get('password')
  if not self._credential:raise RuntimeError('Existing Git helper returned no credential')
  self.opener=urllib.request.build_opener(NoRedirect)
  if self.request('GET','/user')['login']!='Starvastika':raise ValueError('Authenticated account does not own the intended project')
 def request(self,method,path,payload=None):
  if not path.startswith(('/repos/'+REPO,'/user')):raise ValueError('API outside intended repository')
  data=json.dumps(payload).encode() if payload is not None else None
  headers={'Authorization':'Bearer '+self._credential,'User-Agent':'Omni-Taskbar-Maintainer','Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'}
  if data:headers['Content-Type']='application/json'
  with self.opener.open(urllib.request.Request('https://api.github.com'+path,data=data,headers=headers,method=method),timeout=30) as response:
   return json.load(response) if response.status!=204 else {}
 def repository(self):return self.request('GET','/repos/'+REPO)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=('repo','public','preflight','runs','jobs'));p.add_argument('--run',type=int);a=p.parse_args();api=GitHub()
 if a.action=='repo':
  r=api.repository();print(json.dumps({k:r[k] for k in ('full_name','private','default_branch','html_url')}))
 elif a.action=='public':
  r=api.request('PATCH','/repos/'+REPO,{'private':False,'description':'A complete Windows taskbar shell powered by YASB, with Time Center, Weather Center and safe integrated updates.'});print(json.dumps({'full_name':r['full_name'],'private':r['private']}))
 elif a.action=='preflight':api.request('POST','/repos/'+REPO+'/actions/workflows/release.yml/dispatches',{'ref':'main'});print('Preflight dispatched on main; no release publication')
 elif a.action=='runs':
  rows=api.request('GET','/repos/'+REPO+'/actions/workflows/release.yml/runs?per_page=5')['workflow_runs'];print(json.dumps([{k:r[k] for k in ('id','head_sha','event','status','conclusion','html_url')} for r in rows]))
 elif a.action=='jobs':
  rows=api.request('GET','/repos/'+REPO+'/actions/runs/'+str(a.run)+'/jobs')['jobs'];print(json.dumps([{'id':r['id'],'status':r['status'],'conclusion':r['conclusion'],'steps':[{k:s[k] for k in ('name','status','conclusion')} for s in r['steps']]} for r in rows]))
