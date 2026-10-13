"""跨平台开发入口：先安装 Python requirements 和 frontend npm ci。"""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--backend-only",action="store_true")
    args=parser.parse_args()
    processes=[]
    try:
        processes.append(subprocess.Popen([sys.executable,"-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8000"],cwd=ROOT/"backend"))
        if not args.backend_only:
            npm=shutil.which("npm.cmd" if sys.platform=="win32" else "npm")
            if not npm:
                raise RuntimeError("请安装 Node.js 和 npm，或使用 --backend-only")
            processes.append(subprocess.Popen([npm,"run","dev","--","--host","127.0.0.1"],cwd=ROOT/"frontend"))
        url="http://localhost:8000" if args.backend_only else "http://localhost:5173"
        print(f"AdCraft AI：{url}  接口文档：http://localhost:8000/docs",flush=True)
        while all(p.poll() is None for p in processes):
            try:
                processes[0].wait(timeout=1)
            except subprocess.TimeoutExpired:
                pass
    except KeyboardInterrupt:
        pass
    finally:
        for p in processes:
            if p.poll() is None: p.terminate()
        for p in processes:
            try: p.wait(timeout=5)
            except subprocess.TimeoutExpired: p.kill()


if __name__=="__main__":
    main()
