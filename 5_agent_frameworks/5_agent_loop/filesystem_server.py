"""
The sandboxed filesystem MCP server the framework workers use to read and write the games.

It serves file tools over streamable HTTP at /mcp, confined to the folder named by the MCP_ROOT environment
variable. Start it in its own terminal, rooted at the shared site folder (PowerShell, from this folder):

    $env:MCP_ROOT = "<path to>\\5_agent_loop\\site"
    uvicorn filesystem_server:app --host 127.0.0.1 --port 8000

Every path the tools take is relative to MCP_ROOT. The docstrings below double as the tool descriptions agents see.
"""

from mcp.server.mcpserver import MCPServer  # mcp 2.x renamed FastMCP to MCPServer
from fastapi import FastAPI

from pathlib import Path
import shutil
import os
import fnmatch
import base64
import mimetypes
from typing import List
from contextlib import asynccontextmanager

ROOT = Path(os.environ.get("MCP_ROOT", ".")).resolve()

mcp = MCPServer("filesystem")


def resolve(path: str) -> Path:
    """
    Turn a path relative to the sandbox root into an absolute path, refusing anything that escapes the root.

    Args:
        path: A path relative to MCP_ROOT.

    Returns:
        The resolved absolute path.

    Raises:
        ValueError: If the path resolves outside the sandbox root.
    """
    p = (ROOT / path).resolve()

    if ROOT != p and ROOT not in p.parents:
        raise ValueError("Access outside sandbox is not allowed.")

    return p


@mcp.tool()
def allowed_paths() -> List[str]:
    """
    List the folders these tools may use.

    Returns:
        A list holding the sandbox root folder.
    """
    return [str(ROOT)]


@mcp.tool()
def pwd() -> str:
    """
    Report the sandbox root folder, which every relative path is based on.

    Returns:
        The absolute path of the root folder.
    """
    return str(ROOT)


@mcp.tool()
def file_exists(path: str) -> bool:
    """
    Check whether a file or folder exists.

    Args:
        path: A path relative to the sandbox root.

    Returns:
        True if something exists at the path.

    Raises:
        ValueError: If the path is outside the sandbox.
    """
    return resolve(path).exists()


@mcp.tool()
def list_directory(path: str = "."):
    """
    List the entries of one folder.

    Args:
        path: A folder relative to the sandbox root. Defaults to the root.

    Returns:
        A list of {"name", "is_dir", "size"} entries, sorted by name.

    Raises:
        ValueError: If the path is outside the sandbox.
        FileNotFoundError: If the folder does not exist.
        NotADirectoryError: If the path is a file.
    """
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
    """
    Describe a folder and everything beneath it as a nested tree.

    Args:
        path: A folder relative to the sandbox root. Defaults to the root.

    Returns:
        A list of {"name", "type"} nodes, where folders also carry their "children".

    Raises:
        ValueError: If the path is outside the sandbox.
        FileNotFoundError: If the folder does not exist.
        NotADirectoryError: If the path is a file.
    """
    p = resolve(path)

    def walk(folder):
        """
        Build the nested listing for one folder, descending into its sub-folders.

        Args:
            folder: The folder to describe.

        Returns:
            A list of {"name", "type"} nodes, with "children" added for sub-folders.

        Raises:
            OSError: If a folder cannot be read.
        """
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
    """
    Create a folder, including any missing parent folders. Does nothing if it already exists.

    Args:
        path: A folder relative to the sandbox root.

    Returns:
        "OK" once the folder exists.

    Raises:
        ValueError: If the path is outside the sandbox.
        FileExistsError: If a file already exists at the path.
    """
    resolve(path).mkdir(parents=True, exist_ok=True)
    return "OK"


@mcp.tool()
def delete_directory(path: str):
    """
    Delete a folder and everything inside it.

    Args:
        path: A folder relative to the sandbox root.

    Returns:
        "OK" once the folder is deleted.

    Raises:
        ValueError: If the path is outside the sandbox.
        FileNotFoundError: If the folder does not exist.
        NotADirectoryError: If the path is a file.
    """
    shutil.rmtree(resolve(path))
    return "OK"


@mcp.tool()
def read_file(path: str):
    """
    Read a text file.

    Args:
        path: A file relative to the sandbox root.

    Returns:
        The file's contents as UTF-8 text.

    Raises:
        ValueError: If the path is outside the sandbox.
        FileNotFoundError: If the file does not exist.
        UnicodeDecodeError: If the file is not valid UTF-8 text; use read_binary for other files.
    """
    return resolve(path).read_text(encoding="utf-8")


@mcp.tool()
def write_file(path: str, content: str):
    """
    Write a text file, creating missing parent folders and replacing any existing file.

    Args:
        path: A file relative to the sandbox root.
        content: The text to write, saved as UTF-8.

    Returns:
        "OK" once the file is written.

    Raises:
        ValueError: If the path is outside the sandbox.
        OSError: If the file cannot be written, for example because the path is a folder.
    """
    p = resolve(path)

    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")

    return "OK"


@mcp.tool()
def append_file(path: str, content: str):
    """
    Add text to the end of a file, creating the file and its parent folders if needed.

    Args:
        path: A file relative to the sandbox root.
        content: The text to add, saved as UTF-8.

    Returns:
        "OK" once the text is added.

    Raises:
        ValueError: If the path is outside the sandbox.
        OSError: If the file cannot be written.
    """
    p = resolve(path)

    p.parent.mkdir(parents=True, exist_ok=True)

    with open(p, "a", encoding="utf-8") as f:
        f.write(content)

    return "OK"


@mcp.tool()
def delete_file(path: str):
    """
    Delete one file.

    Args:
        path: A file relative to the sandbox root.

    Returns:
        "OK" once the file is deleted.

    Raises:
        ValueError: If the path is outside the sandbox.
        FileNotFoundError: If the file does not exist.
    """
    resolve(path).unlink()
    return "OK"


@mcp.tool()
def move(src: str, dst: str):
    """
    Move or rename a file or folder.

    Args:
        src: The existing path, relative to the sandbox root.
        dst: The new path, relative to the sandbox root.

    Returns:
        "OK" once it is moved.

    Raises:
        ValueError: If either path is outside the sandbox.
        FileNotFoundError: If the source does not exist.
        OSError: If the move fails, for example because the destination's parent folder does not exist.
    """
    shutil.move(resolve(src), resolve(dst))
    return "OK"


@mcp.tool()
def copy(src: str, dst: str):
    """
    Copy a file, or a whole folder with its contents, creating missing parent folders for a file.

    Args:
        src: The existing path, relative to the sandbox root.
        dst: The path to copy to, relative to the sandbox root.

    Returns:
        "OK" once it is copied.

    Raises:
        ValueError: If either path is outside the sandbox.
        FileNotFoundError: If the source does not exist.
        OSError: If the copy fails.
    """
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
    """
    Describe a file or folder.

    Args:
        path: A path relative to the sandbox root.

    Returns:
        A dictionary with name, path, size, is_dir, modified (a timestamp), suffix and mime type.

    Raises:
        ValueError: If the path is outside the sandbox.
        FileNotFoundError: If nothing exists at the path.
    """
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
    """
    Find files and folders whose name matches a wildcard pattern, searching all folders beneath a starting folder.

    Args:
        pattern: A wildcard pattern such as "*.html".
        path: The folder to search from, relative to the sandbox root. Defaults to the root.

    Returns:
        A list of the matching absolute paths; empty if nothing matches or the folder does not exist.

    Raises:
        ValueError: If the path is outside the sandbox.
    """
    p = resolve(path)

    matches = []

    for root, dirs, files in os.walk(p):
        for name in files + dirs:
            if fnmatch.fnmatch(name, pattern):
                matches.append(str(Path(root) / name))

    return matches


@mcp.tool()
def grep(pattern: str, path: str = "."):
    """
    Find lines containing some text in the files beneath a folder. Files that are not UTF-8 text are skipped.

    Args:
        pattern: The text to look for (a plain substring, not a regular expression).
        path: The folder to search from, relative to the sandbox root. Defaults to the root.

    Returns:
        A list of {"file", "line", "text"} matches.

    Raises:
        ValueError: If the path is outside the sandbox.
    """
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
    """
    Read a file of any type.

    Args:
        path: A file relative to the sandbox root.

    Returns:
        The file's bytes, base64 encoded.

    Raises:
        ValueError: If the path is outside the sandbox.
        FileNotFoundError: If the file does not exist.
    """
    data = resolve(path).read_bytes()

    return base64.b64encode(data).decode()


@mcp.tool()
def write_binary(path: str, data: str):
    """
    Write a file of any type from base64 text, creating missing parent folders and replacing any existing file.

    Args:
        path: A file relative to the sandbox root.
        data: The file's bytes, base64 encoded.

    Returns:
        "OK" once the file is written.

    Raises:
        ValueError: If the path is outside the sandbox.
        binascii.Error: If data is not valid base64.
        OSError: If the file cannot be written.
    """
    p = resolve(path)

    p.parent.mkdir(parents=True, exist_ok=True)

    p.write_bytes(base64.b64decode(data))

    return "OK"


@mcp.tool()
def read_multiple(paths: List[str]):
    """
    Read several text files in one call.

    Args:
        paths: Files relative to the sandbox root.

    Returns:
        A dictionary mapping each path to its text, or to the error message if that file could not be read.
    """
    out = {}

    for p in paths:
        try:
            out[p] = read_file(p)
        except Exception as e:
            out[p] = str(e)

    return out


# ------------------------------
# FastAPI + MCP setup
# ------------------------------
# app creation
mcp_app = mcp.streamable_http_app()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Run the MCP session manager for as long as the web app is up.

    Args:
        app: The FastAPI application being started.

    Yields:
        None, while the server is running.
    """
    async with mcp.session_manager.run():
        yield

app = FastAPI(lifespan=lifespan)

# Mount MCP over HTTP/SSE
app.mount("/", mcp_app)

# Run command in terminal to start the FastAPI server
# $env:MCP_ROOT="PATH_TO_YOUR_MCP_WORKSPACE_DIRECTORY"
# Replace 'filename' with the actual name of this Python file: 'uvicorn filename:app --host 127.0.0.1 --port 8000'
