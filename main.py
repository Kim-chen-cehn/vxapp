"""
最小可运行后端:浏览器写 Python 代码 -> 本后端 -> Judge0 执行 -> 返回结果。

环境变量(都有默认值,先用默认的跑通即可):
  JUDGE0_URL                默认 https://ce.judge0.com (免费公共实例)
  PYTHON_LANGUAGE_ID        默认 71 (Judge0 CE 上的 Python 3)
  JUDGE0_AUTH_HEADER_NAME   可选,鉴权头名字,如 X-Auth-Token / X-RapidAPI-Key
  JUDGE0_AUTH_HEADER_VALUE  可选,鉴权头的值(你的 key)

启动: uvicorn main:app --reload
然后浏览器打开 http://localhost:8000/
"""

import os
import base64
import re
from pathlib import Path
import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


def b64enc(s: str) -> str:
    return base64.b64encode(s.encode()).decode()


def b64dec(s: str | None) -> str:
    if not s:
        return ""
    return base64.b64decode(s).decode(errors="replace")

JUDGE0_URL = os.getenv("JUDGE0_URL", "https://ce.judge0.com").rstrip("/")
PYTHON_LANGUAGE_ID = int(os.getenv("PYTHON_LANGUAGE_ID", "71"))
AUTH_HEADER_NAME = os.getenv("JUDGE0_AUTH_HEADER_NAME", "")
AUTH_HEADER_VALUE = os.getenv("JUDGE0_AUTH_HEADER_VALUE", "")
BASE_DIR = Path(__file__).resolve().parent
FILES_DIR = BASE_DIR / "files"
SAFE_FILENAME_RE = re.compile(r"^[\w\u4e00-\u9fff .-]{1,80}$")

app = FastAPI(title="Mini Python IDE Backend")

# 开发期允许跨域,方便你直接用浏览器调试。上线前要收紧。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class RunRequest(BaseModel):
    code: str
    stdin: str = ""


class CodeFile(BaseModel):
    filename: str
    code: str


class CodeFileInfo(BaseModel):
    filename: str
    updated_at: float
    size: int


class DeleteFileResult(BaseModel):
    filename: str
    deleted: bool


class RunResult(BaseModel):
    stdout: str
    stderr: str
    compile_output: str
    status: str
    time: str | None = None
    memory: int | None = None


def judge0_headers() -> dict:
    headers = {"Content-Type": "application/json"}
    if AUTH_HEADER_NAME and AUTH_HEADER_VALUE:
        headers[AUTH_HEADER_NAME] = AUTH_HEADER_VALUE
    return headers


def normalize_filename(filename: str) -> str:
    name = filename.strip()
    if not name:
        raise HTTPException(status_code=400, detail="文件名为空")
    if not name.endswith(".py"):
        name = f"{name}.py"
    if "/" in name or "\\" in name or name in {".py", "..py"}:
        raise HTTPException(status_code=400, detail="文件名不合法")
    if not SAFE_FILENAME_RE.fullmatch(name):
        raise HTTPException(status_code=400, detail="文件名只能包含中文、字母、数字、空格、点、横线和下划线")
    return name


def file_path(filename: str) -> Path:
    name = normalize_filename(filename)
    path = (FILES_DIR / name).resolve()
    if FILES_DIR.resolve() not in path.parents:
        raise HTTPException(status_code=400, detail="文件路径不合法")
    return path


@app.get("/")
def index():
    # 把测试页和后端放在同一来源,省去跨域麻烦
    return FileResponse(BASE_DIR / "index.html")


@app.get("/api/files", response_model=list[CodeFileInfo])
def list_files():
    FILES_DIR.mkdir(exist_ok=True)
    files = []
    for path in FILES_DIR.glob("*.py"):
        stat = path.stat()
        files.append(CodeFileInfo(filename=path.name, updated_at=stat.st_mtime, size=stat.st_size))
    return sorted(files, key=lambda item: item.updated_at, reverse=True)


@app.get("/api/files/{filename}", response_model=CodeFile)
def load_file(filename: str):
    path = file_path(filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    return CodeFile(filename=path.name, code=path.read_text(encoding="utf-8"))


@app.post("/api/files", response_model=CodeFile)
def save_file(req: CodeFile):
    path = file_path(req.filename)
    FILES_DIR.mkdir(exist_ok=True)
    path.write_text(req.code, encoding="utf-8")
    return CodeFile(filename=path.name, code=req.code)


@app.delete("/api/files/{filename}", response_model=DeleteFileResult)
def delete_file(filename: str):
    path = file_path(filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    path.unlink()
    return DeleteFileResult(filename=path.name, deleted=True)


@app.post("/api/run", response_model=RunResult)
def run_code(req: RunRequest):
    if not req.code.strip():
        raise HTTPException(status_code=400, detail="代码为空")

    payload = {
        "language_id": PYTHON_LANGUAGE_ID,
        "source_code": b64enc(req.code),
        "stdin": b64enc(req.stdin),
    }

    try:
        resp = requests.post(
            f"{JUDGE0_URL}/submissions?base64_encoded=true&wait=true",
            json=payload,
            headers=judge0_headers(),
            timeout=30,
        )
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"连不上 Judge0:{e}")

    if resp.status_code == 401:
        raise HTTPException(status_code=502, detail="Judge0 需要鉴权:请配置 JUDGE0_AUTH_HEADER_* 或自托管")
    if resp.status_code == 429:
        raise HTTPException(status_code=502, detail="Judge0 触发限流:公共实例额度有限,建议用自己的 key 或自托管")
    if resp.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Judge0 返回 {resp.status_code}:{resp.text[:200]}")

    data = resp.json()
    status = (data.get("status") or {}).get("description", "Unknown")
    return RunResult(
        stdout=b64dec(data.get("stdout")),
        stderr=b64dec(data.get("stderr")),
        compile_output=b64dec(data.get("compile_output")),
        status=status,
        time=data.get("time"),
        memory=data.get("memory"),
    )
