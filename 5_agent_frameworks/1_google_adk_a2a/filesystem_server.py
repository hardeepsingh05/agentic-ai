from mcp.server.fastmcp import FastMCP
from fastapi import FastAPI

from pathlib import Path
import shutil
import os
import fnmatch
import base64
import mimetypes
from typing import List

ROOT = Path(os.environ.get("MCP_ROOT", ".")).resolve()

mcp = FastMCP("filesystem")


def resolve(path: str) -> Path:
    p = (ROOT / path).resolve()

    if ROOT != p and ROOT not in p.parents:
        raise ValueError("Access outside sandbox is not allowed.")

    return p


@mcp.tool()
def allowed_paths() -> List[str]:
    return [str(ROOT)]


@mcp.tool()
def pwd() -> str:
    return str(ROOT)


@mcp.tool()
def file_exists(path: str) -> bool:
    return resolve(path).exists()


@mcp.tool()
def list_directory(path: str = "."):
    p = resolve(path)

    return [
        {
            "name": x.name,
            "is_dir": x.is_dir(),
            "size": x.stat().st_size,
        }
        for x in sorted(p.iterdir())
    ]


@mcp.tool()
def directory_tree(path: str = "."):
    p = resolve(path)

    def walk(folder):
        children = []

        for f in sorted(folder.iterdir()):
            node = {
                "name": f.name,
                "type": "directory" if f.is_dir() else "file",
            }

            if f.is_dir():
                node["children"] = walk(f)

            children.append(node)

        return children

    return walk(p)


@mcp.tool()
def create_directory(path: str):
    resolve(path).mkdir(parents=True, exist_ok=True)
    return "OK"


@mcp.tool()
def delete_directory(path: str):
    shutil.rmtree(resolve(path))
    return "OK"


@mcp.tool()
def read_file(path: str):
    return resolve(path).read_text(encoding="utf-8")


@mcp.tool()
def write_file(path: str, content: str):
    p = resolve(path)

    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")

    return "OK"


@mcp.tool()
def append_file(path: str, content: str):
    p = resolve(path)

    p.parent.mkdir(parents=True, exist_ok=True)

    with open(p, "a", encoding="utf-8") as f:
        f.write(content)

    return "OK"


@mcp.tool()
def delete_file(path: str):
    resolve(path).unlink()
    return "OK"


@mcp.tool()
def move(src: str, dst: str):
    shutil.move(resolve(src), resolve(dst))
    return "OK"


@mcp.tool()
def copy(src: str, dst: str):
    s = resolve(src)
    d = resolve(dst)

    if s.is_dir():
        shutil.copytree(s, d, dirs_exist_ok=True)
    else:
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(s, d)

    return "OK"


@mcp.tool()
def stat(path: str):
    p = resolve(path)
    st = p.stat()

    return {
        "name": p.name,
        "path": str(p),
        "size": st.st_size,
        "is_dir": p.is_dir(),
        "modified": st.st_mtime,
        "suffix": p.suffix,
        "mime": mimetypes.guess_type(str(p))[0],
    }


@mcp.tool()
def search_files(pattern: str, path: str = "."):
    p = resolve(path)

    matches = []

    for root, dirs, files in os.walk(p):
        for name in files + dirs:
            if fnmatch.fnmatch(name, pattern):
                matches.append(str(Path(root) / name))

    return matches


@mcp.tool()
def grep(pattern: str, path: str = "."):
    p = resolve(path)

    results = []

    for root, dirs, files in os.walk(p):
        for file in files:
            fp = Path(root) / file

            try:
                with open(fp, encoding="utf-8") as f:
                    for i, line in enumerate(f, 1):
                        if pattern in line:
                            results.append(
                                {
                                    "file": str(fp),
                                    "line": i,
                                    "text": line.strip(),
                                }
                            )
            except:
                pass

    return results


@mcp.tool()
def read_binary(path: str):
    data = resolve(path).read_bytes()

    return base64.b64encode(data).decode()


@mcp.tool()
def write_binary(path: str, data: str):
    p = resolve(path)

    p.parent.mkdir(parents=True, exist_ok=True)

    p.write_bytes(base64.b64decode(data))

    return "OK"


@mcp.tool()
def read_multiple(paths: List[str]):
    out = {}

    for p in paths:
        try:
            out[p] = read_file(p)
        except Exception as e:
            out[p] = str(e)

    return out


app = FastAPI()

# Mount MCP over HTTP/SSE
app.mount("/",mcp.sse_app())

# Run command in terminal to start the FastAPI server
# $env:MCP_ROOT="PATH_TO_YOUR_MCP_WORKSPACE_DIRECTORY"
# Replace 'filename' with the actual name of this Python file: 'uvicorn filename:app --host 127.0.0.1 --port 8000'
