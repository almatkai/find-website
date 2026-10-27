"""All child QA caches and user/temp roots stay under this clone."""
import os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
def environment(toolchain='stable', cargo_home='cargo', target='target'):
    env = dict(os.environ)
    home = ROOT/'.qa/home'; tmp = ROOT/'.qa/tmp'
    for p in [home, tmp, home/'local', home/'roaming', ROOT/'.qa'/cargo_home]: p.mkdir(parents=True, exist_ok=True)
    bins = Path('/Users/almat/.rustup/toolchains') / (toolchain+'-aarch64-apple-darwin') / 'bin'
    env.update(HOME=str(home), USERPROFILE=str(home), TMPDIR=str(tmp), TMP=str(tmp), TEMP=str(tmp), LOCALAPPDATA=str(home/'local'), APPDATA=str(home/'roaming'), CARGO_HOME=str(ROOT/'.qa'/cargo_home), CARGO_TARGET_DIR=str(ROOT/target), RUSTUP_HOME='/Users/almat/.rustup', npm_config_cache=str(ROOT/'.qa/npm'), XDG_CACHE_HOME=str(ROOT/'.qa/cache'), PATH=str(bins)+':'+env['PATH'], TZ='UTC', PYTHONDONTWRITEBYTECODE='1', PYTHONPYCACHEPREFIX=str(ROOT/'.qa/pycache'))
    return env
if __name__=='__main__':
    import subprocess,sys
    args=sys.argv[1:]; chain='stable'
    if args and args[0].startswith('+'): chain=args.pop(0)[1:]
    raise SystemExit(subprocess.call(args,env=environment(chain),cwd=ROOT))
