"""Skills API routes — list / detail / create / delete / upload skill packs."""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
import os, re, shutil, zipfile, tempfile

router = APIRouter(prefix="/api/skills", tags=["skills"])

SKILL_EFFICIENCY = {
    "rce": 100, "sqli": 95, "auth_bypass": 92, "deserialization": 88,
    "file_upload": 85, "xss": 82, "ssrf": 78, "path_traversal": 75,
    "business_logic": 70, "xxe": 65, "race_condition": 60,
    "hardcoded_secret": 55, "info_disclosure": 45, "crypto": 40,
}
SKILL_NAMES_ZH = {
    "rce": "远程代码执行", "sqli": "SQL 注入", "auth_bypass": "认证绕过",
    "deserialization": "反序列化", "file_upload": "文件上传", "xss": "跨站脚本",
    "ssrf": "服务端请求伪造", "path_traversal": "路径遍历",
    "business_logic": "业务逻辑", "xxe": "XML 外部实体",
    "race_condition": "竞态条件", "hardcoded_secret": "硬编码密钥",
    "info_disclosure": "信息泄露", "crypto": "加密问题",
}
SKILL_VALUE_DESC = {
    "rce": "直接控制服务器，最高利用价值", "sqli": "拖库/篡改数据，漏洞赏金常客",
    "auth_bypass": "越权访问一切，影响面最大", "deserialization": "常见 RCE 前置链路",
    "file_upload": "webshell 直接拿权限", "xss": "账号劫持/钓鱼，渗透首选",
    "ssrf": "内网漫游，云环境高危", "path_traversal": "任意文件读写",
    "business_logic": "0day 高发区，SRC 高价漏洞", "xxe": "文件读取+SSRF",
    "race_condition": "并发缺陷，薅羊毛/提现漏洞", "hardcoded_secret": "一键接管凭据",
    "info_disclosure": "低危但高频，报告凑数神器", "crypto": "弱加密可被暴力破解",
}


def _project_root():
    # .../code-audit/backend/app/api/routes/skills.py -> code-audit
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))


def _skills_dir():
    return os.path.join(_project_root(), "skills")


def _load_skill_info():
    skills_dir = _skills_dir()
    skills = []
    if not os.path.isdir(skills_dir):
        return skills
    for name in sorted(os.listdir(skills_dir)):
        skill_dir = os.path.join(skills_dir, name)
        md_path = os.path.join(skill_dir, "SKILL.md")
        if not os.path.isdir(skill_dir) or not os.path.isfile(md_path):
            continue
        overview = ""
        try:
            with open(md_path, "r", encoding="utf-8") as f:
                for line in f.readlines()[:60]:
                    ls = line.strip()
                    if ls and not ls.startswith("#") and not ls.startswith("```"):
                        overview = ls[:200]
                        break
        except Exception:
            pass
        cl_dir = os.path.join(skill_dir, "checklists")
        has_checklist = os.path.isdir(cl_dir)
        langs = [f.replace(".md", "") for f in os.listdir(cl_dir) if f.endswith(".md")] if has_checklist else []
        is_custom = name.startswith("custom_")
        skills.append({
            "name": name,
            "display_name": SKILL_NAMES_ZH.get(name, name),
            "efficiency": SKILL_EFFICIENCY.get(name, 30),
            "value_desc": SKILL_VALUE_DESC.get(name, "自定义技能包"),
            "overview": overview,
            "has_checklist": has_checklist,
            "checklist_langs": langs,
            "enabled": True,
            "is_custom": is_custom,
        })
    skills.sort(key=lambda s: s["efficiency"], reverse=True)
    return skills


@router.get("")
async def list_skills():
    skills = _load_skill_info()
    return {"skills": skills, "total": len(skills)}


@router.get("/{skill_name}")
async def get_skill(skill_name: str):
    md_path = os.path.join(_safe_skill_dir(skill_name), "SKILL.md")
    if not os.path.isfile(md_path):
        raise HTTPException(status_code=404, detail=f"Skill not found: {skill_name}")
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()
    return {"name": skill_name, "content": content[:8000]}


@router.post("")
async def create_skill(name: str, content: str, display_name: str = ""):
    """Create a custom skill pack (stored under skills/custom_<name>/SKILL.md)."""
    name = (name or "").strip().lower()
    if not name or not re.match(r"^[a-z0-9_\-]{2,32}$", name):
        raise HTTPException(status_code=400, detail="Invalid skill name (a-z0-9_- 2-32 chars)")
    if not content or len(content.strip()) < 20:
        raise HTTPException(status_code=400, detail="Skill content too short")
    # built-in names cannot be overwritten
    builtins = set(SKILL_EFFICIENCY.keys())
    if name in builtins:
        raise HTTPException(status_code=400, detail=f"Cannot overwrite built-in skill: {name}")
    dir_name = name if name.startswith("custom_") else f"custom_{name}"
    skill_dir = os.path.join(_skills_dir(), dir_name)
    os.makedirs(skill_dir, exist_ok=True)
    md_path = os.path.join(skill_dir, "SKILL.md")
    # ensure markdown heading
    if not content.lstrip().startswith("#"):
        title = display_name or name
        content = f"# {title}\n\n{content}"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(content)
    return {"status": "created", "name": dir_name}


def _safe_skill_dir(skill_name: str) -> str:
    """Resolve a skill dir and guarantee it stays inside _skills_dir()."""
    if not re.match(r"^[a-zA-Z0-9_\-]{1,64}$", skill_name or ""):
        raise HTTPException(status_code=400, detail=f"Invalid skill name: {skill_name!r}")
    base = os.path.realpath(_skills_dir())
    dest = os.path.realpath(os.path.join(base, skill_name))
    if not (dest.startswith(base + os.sep)):
        raise HTTPException(status_code=400, detail="Invalid skill path")
    return dest


@router.delete("/{skill_name}")
async def delete_skill(skill_name: str):
    """Delete a custom skill pack. Built-in skills are protected."""
    if skill_name in SKILL_EFFICIENCY:
        raise HTTPException(status_code=400, detail=f"Cannot delete built-in skill: {skill_name}")
    skill_dir = _safe_skill_dir(skill_name)
    if not os.path.isdir(skill_dir):
        raise HTTPException(status_code=404, detail=f"Skill not found: {skill_name}")
    shutil.rmtree(skill_dir)
    return {"status": "deleted", "name": skill_name}


@router.post("/upload")
async def upload_skill(file: UploadFile = File(...), display_name: str = Form("")):
    """Upload a skill from a local .md or .zip file."""
    filename = (file.filename or "").strip()
    if not filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    ext = os.path.splitext(filename)[1].lower()
    if ext not in (".md", ".zip"):
        raise HTTPException(status_code=400, detail="Only .md and .zip files are supported")
    raw_name = os.path.splitext(filename)[0].strip().lower()
    raw_name = re.sub(r"[^a-z0-9_\-]", "_", raw_name).strip("_")
    if not raw_name or len(raw_name) < 2:
        raw_name = "uploaded_skill"
    builtins = set(SKILL_EFFICIENCY.keys())
    if raw_name in builtins:
        raw_name = f"custom_{raw_name}"
    elif not raw_name.startswith("custom_"):
        raw_name = f"custom_{raw_name}"
    skill_dir = os.path.join(_skills_dir(), raw_name)
    content = ""
    extracted_files = []
    if ext == ".md":
        content_bytes = await file.read()
        content = content_bytes.decode("utf-8", errors="replace")
    else:
        zip_bytes = await file.read()
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = os.path.join(tmp, "upload.zip")
            with open(zip_path, "wb") as f:
                f.write(zip_bytes)
            try:
                with zipfile.ZipFile(zip_path, "r") as zf:
                    for info in zf.infolist():
                        member = info.filename.replace("\\", "/")
                        if member.startswith("/") or ".." in member:
                            continue
                        zf.extract(info, tmp)
            except zipfile.BadZipFile:
                raise HTTPException(status_code=400, detail="Invalid ZIP file")
            found_md = None
            for r, ds, fs in os.walk(tmp):
                for f in fs:
                    if f.upper() == "SKILL.MD":
                        found_md = os.path.join(r, f)
                    elif f.endswith(".md") and not found_md:
                        found_md = os.path.join(r, f)
            if not found_md:
                raise HTTPException(status_code=400, detail="ZIP must contain at least one .md file (preferably SKILL.md)")
            with open(found_md, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            for r, ds, fs in os.walk(tmp):
                for f in fs:
                    fp = os.path.join(r, f)
                    rel = os.path.relpath(fp, os.path.dirname(found_md)).replace("\\", "/")
                    if rel == "SKILL.md":
                        continue
                    with open(fp, "rb") as fh:
                        extracted_files.append((rel, fh.read()))
    if not content or len(content.strip()) < 20:
        raise HTTPException(status_code=400, detail="Skill content too short (< 20 chars)")
    os.makedirs(skill_dir, exist_ok=True)
    if not content.lstrip().startswith("#"):
        title = display_name or raw_name
        content = f"# {title}\n\n{content}"
    with open(os.path.join(skill_dir, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write(content)
    for rel, data in extracted_files:
        # Defense in depth: never write outside skill_dir even if rel contains ..
        dest = os.path.realpath(os.path.join(skill_dir, rel))
        if not dest.startswith(os.path.realpath(skill_dir) + os.sep):
            continue
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(data)
    return {"status": "created", "name": raw_name, "files": 1 + len(extracted_files)}
