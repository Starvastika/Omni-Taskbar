"""Bake one versioned release's metadata into its user-facing bootstrap asset."""
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def build():
 metadata=json.loads((ROOT/'version.json').read_text('utf-8'))
 repository=metadata.get('repository')
 if not repository:repository='REPOSITORY_NOT_CONFIGURED'
 elif not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repository):raise ValueError('Invalid repository')
 source=(ROOT/'distribution/install.ps1').read_text('utf-8')
 output=ROOT/'dist';output.mkdir(exist_ok=True)
 (output/'install.ps1').write_text(source.replace('RELEASE_REPOSITORY',repository).replace('RELEASE_VERSION',metadata['version']),'utf-8')
 (output/'install.cmd').write_text('@echo off\r\npowershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "%~dp0install.ps1"\r\n','utf-8')
if __name__=='__main__':build()
