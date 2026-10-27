"""Read immutable Git objects only; never inspect host/SDK working files."""
import subprocess,json,hashlib
from pathlib import Path
from env import ROOT
PINS=[('sdk',ROOT.parent.parent/'tezbar-extension-sdk-rust','e955911f0bf5b558f9d3eb5183df0adc95c22af2',['Cargo.toml','LICENSE','NOTICE','src/lib.rs','src/context.rs','src/runner.rs','SDK_API.md','PROTOCOL.md','HOST_INTEGRATION.md']),('host',ROOT.parent.parent.parent/'Tezbar','ea100cee3f69711de12485ba061950c5fc65258f',['src/shared/extensionRuntime.ts','src-tauri/src/native_core/extensions/native.rs','src/renderer/ExtensionRuntimeView.tsx','src/renderer/src/raycast-api/list-runtime.tsx','src/renderer/extensionImages.ts','src-tauri/src/native_core/platform.rs','src-tauri/src/native_core/extensions/process_host.rs','schemas/extension-v3.schema.json'])]
def capture():
 out=ROOT/'.qa/contracts';out.mkdir(parents=True,exist_ok=True);records=[]
 for name,repo,rev,files in PINS:
  for file in files:
   data=subprocess.check_output(['git','-C',str(repo),'show',rev+':'+file]);path=out/(name+'-'+Path(file).name);path.write_bytes(data)
   assert data==subprocess.check_output(['git','-C',str(repo),'show',rev+':'+file]);records.append(dict(repo=name,revision=rev,path=file,blob=subprocess.check_output(['git','-C',str(repo),'rev-parse',rev+':'+file],text=True).strip(),sha256=hashlib.sha256(data).hexdigest()))
 (ROOT/'evidence/contracts.json').write_text(json.dumps(records,indent=2)+'\n')
 return out
if __name__=='__main__':capture();print('Pinned host/SDK objects captured and independently rechecked')
