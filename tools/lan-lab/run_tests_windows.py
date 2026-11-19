"""Compile and run the isolated LAN laboratory tests on Windows."""
import argparse,os,pathlib,subprocess,sys
root=pathlib.Path(__file__).resolve().parents[2]; lab=root/'tools/lan-lab'
p=argparse.ArgumentParser();p.add_argument('--clang',default=r'C:\msys64\mingw64\bin\clang.exe');p.add_argument('--output',default=r'C:\NX2Apple\Work\SpplechOS-LAN-lab\lan_frame.dll');a=p.parse_args()
out=pathlib.Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
sources=sorted((lab/'src').glob('*.c'))+[lab/'tests/fake_dns/fake_dns.c']
cmd=[a.clang,'-std=c11','-Wall','-Wextra','-Werror','-shared','-static','-I',str(lab/'tests/fake_dns'),'-I',str(root/'engine/dm/host'),'-o',str(out),*[str(s) for s in sources],'-lws2_32','-lbcrypt','-pthread']
subprocess.run(cmd,check=True,cwd=root)
env=os.environ.copy();env['SPPLE_LAN_TEST_LIBRARY']=str(out);env['SPPLE_TEST_CLANG']=a.clang
subprocess.run([sys.executable,'-m','unittest','discover','-s',str(lab/'tests')],check=True,cwd=root,env=env)
