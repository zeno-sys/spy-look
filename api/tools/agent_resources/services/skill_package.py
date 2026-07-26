from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

MAX_SKILL_BYTES = 5 * 1024 * 1024
SKILL_MD_NAME = "SKILL.md"
NOISE_DIR_PREFIXES = ("__MACOSX/", ".git/")
NOISE_NAMES = {".DS_Store", "Thumbs.db"}

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$", re.IGNORECASE)


@dataclass
class ParsedSkillPackage:
    name: str
    description: str
    skill_md: str
    files: dict[str, bytes]  # relative paths under root, e.g. "SKILL.md", "scripts/a.py"
    package_zip: bytes
    size_bytes: int


def _is_noise(path: str) -> bool:
    normalized = path.replace("\\", "/").lstrip("./")
    if not normalized or normalized.endswith("/"):
        return True
    lower = normalized.lower()
    for prefix in NOISE_DIR_PREFIXES:
        if lower.startswith(prefix.lower()) or f"/{prefix.lower()}" in f"/{lower}":
            return True
    name = normalized.rsplit("/", 1)[-1]
    return name in NOISE_NAMES


def parse_frontmatter(content: str) -> tuple[dict[str, str], str]:
    match = _FRONTMATTER_RE.match(content)
    if not match:
        raise ValueError("SKILL.md 必须包含 YAML frontmatter（以 --- 包裹）")
    raw = match.group(1)
    body = content[match.end() :]
    meta: dict[str, str] = {}
    current_key: str | None = None
    current_val_lines: list[str] = []

    def flush() -> None:
        nonlocal current_key, current_val_lines
        if current_key is None:
            return
        value = "\n".join(current_val_lines).strip()
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        elif value.startswith(">") or value.startswith("|"):
            # fold block scalar marker away; keep following lines
            parts = value.split("\n", 1)
            value = parts[1].strip() if len(parts) > 1 else ""
        meta[current_key] = value
        current_key = None
        current_val_lines = []

    for line in raw.splitlines():
        if not line.strip() and current_key is None:
            continue
        if re.match(r"^[A-Za-z0-9_-]+\s*:", line) and not line.startswith(" "):
            flush()
            key, _, rest = line.partition(":")
            current_key = key.strip()
            rest = rest.strip()
            if rest:
                current_val_lines = [rest]
            else:
                current_val_lines = []
        elif current_key is not None:
            current_val_lines.append(line)
        else:
            raise ValueError(f"无法解析 frontmatter 行: {line}")
    flush()
    return meta, body


def build_skill_md(*, name: str, description: str, body: str = "") -> str:
    desc = description.replace("\n", " ").strip()
    body_text = body if not body or body.startswith("\n") else "\n" + body
    text = f"---\nname: {name}\ndescription: {desc}\n---\n{body_text}"
    if not text.endswith("\n"):
        text += "\n"
    return text


def validate_skill_name(name: str) -> str:
    cleaned = (name or "").strip()
    if not cleaned:
        raise ValueError("Skill name 不能为空")
    if not _NAME_RE.match(cleaned):
        raise ValueError(
            "Skill name 仅允许字母、数字、连字符和下划线，且需以字母或数字开头"
        )
    return cleaned


def _files_from_zip_bytes(raw: bytes) -> dict[str, bytes]:
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as exc:
        raise ValueError("无效的 zip 文件") from exc
    files: dict[str, bytes] = {}
    with zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            path = info.filename.replace("\\", "/")
            if _is_noise(path):
                continue
            data = zf.read(info)
            files[path] = data
    if not files:
        raise ValueError("zip 包内没有有效文件")
    return files


def _normalize_to_root_files(files: dict[str, bytes]) -> tuple[str, dict[str, bytes]]:
    """Return (root_name, files relative to root)."""
    paths = [p.replace("\\", "/").lstrip("./") for p in files]
    paths = [p for p in paths if p and not _is_noise(p)]
    if not paths:
        raise ValueError("未找到有效 Skill 文件")

    # Case A: single top-level directory
    top_dirs = {p.split("/", 1)[0] for p in paths if "/" in p}
    top_files = {p for p in paths if "/" not in p}
    if len(top_dirs) == 1 and not top_files:
        root = next(iter(top_dirs))
        relative: dict[str, bytes] = {}
        prefix = root + "/"
        for full, data in files.items():
            norm = full.replace("\\", "/").lstrip("./")
            if not norm.startswith(prefix) or _is_noise(norm):
                continue
            rel = norm[len(prefix) :]
            if rel:
                relative[rel] = data
        return root, relative

    # Case B: SKILL.md at zip root (flat) — root name taken from frontmatter later
    if any(p.lower() == SKILL_MD_NAME.lower() for p in paths):
        relative = {}
        for full, data in files.items():
            norm = full.replace("\\", "/").lstrip("./")
            if _is_noise(norm):
                continue
            if "/" in norm:
                raise ValueError("zip 根目录结构无效：需要单一根文件夹 skill-name/")
            relative[norm] = data
        return "", relative

    raise ValueError(f"缺少 {SKILL_MD_NAME}，或 zip 未使用单一根目录 skill-name/")


def _find_skill_md(relative: dict[str, bytes]) -> str:
    for key in relative:
        if key.replace("\\", "/") == SKILL_MD_NAME or key.lower() == SKILL_MD_NAME.lower():
            return key
    raise ValueError(f"缺少 {SKILL_MD_NAME}")


def pack_skill_zip(root_name: str, relative_files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel, data in sorted(relative_files.items()):
            arc = f"{root_name}/{rel.replace(chr(92), '/')}"
            zf.writestr(arc, data)
    raw = buf.getvalue()
    if len(raw) > MAX_SKILL_BYTES:
        raise ValueError(f"Skill 体积超过上限 ({MAX_SKILL_BYTES // (1024 * 1024)} MB)")
    return raw


def list_package_files(package_zip: bytes) -> list[str]:
    files = _files_from_zip_bytes(package_zip)
    root, relative = _normalize_to_root_files(files)
    if not root:
        # should not happen for stored packages
        return sorted(relative.keys())
    return sorted(f"{root}/{p}" for p in relative)


def extract_skill_md(package_zip: bytes) -> str:
    files = _files_from_zip_bytes(package_zip)
    _root, relative = _normalize_to_root_files(files)
    key = _find_skill_md(relative)
    try:
        return relative[key].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("SKILL.md 需为 UTF-8 编码") from exc


def parse_and_pack(files: dict[str, bytes], *, preferred_root: str | None = None) -> ParsedSkillPackage:
    root, relative = _normalize_to_root_files(files)
    skill_key = _find_skill_md(relative)
    try:
        skill_md = relative[skill_key].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("SKILL.md 需为 UTF-8 编码") from exc

    meta, _body = parse_frontmatter(skill_md)
    name = validate_skill_name(str(meta.get("name", "")))
    description = str(meta.get("description", "")).strip()
    if not description:
        raise ValueError("frontmatter 必须包含非空 description")

    if root and root != name:
        raise ValueError(f"文件夹名「{root}」必须与 frontmatter name「{name}」一致")
    if preferred_root and preferred_root != name:
        raise ValueError(f"根目录名「{preferred_root}」必须与 frontmatter name「{name}」一致")

    # normalize SKILL.md key casing
    if skill_key != SKILL_MD_NAME:
        relative[SKILL_MD_NAME] = relative.pop(skill_key)

    package_zip = pack_skill_zip(name, relative)
    return ParsedSkillPackage(
        name=name,
        description=description,
        skill_md=skill_md,
        files=relative,
        package_zip=package_zip,
        size_bytes=len(package_zip),
    )


def parse_zip_bytes(raw: bytes) -> ParsedSkillPackage:
    if len(raw) > MAX_SKILL_BYTES:
        raise ValueError(f"上传文件超过上限 ({MAX_SKILL_BYTES // (1024 * 1024)} MB)")
    if not raw:
        raise ValueError("上传文件为空")
    return parse_and_pack(_files_from_zip_bytes(raw))


def parse_file_map(file_map: dict[str, bytes], *, root_name: str | None = None) -> ParsedSkillPackage:
    """file_map keys are relative paths, optionally prefixed with root folder."""
    if not file_map:
        raise ValueError("未提供任何文件")
    normalized_input: dict[str, bytes] = {}
    for path, data in file_map.items():
        norm = path.replace("\\", "/").lstrip("./")
        if _is_noise(norm):
            continue
        normalized_input[norm] = data
    if not normalized_input:
        raise ValueError("未提供任何有效文件")

    has_nested = any("/" in p for p in normalized_input)
    flat_has_skill = any(p.lower() == SKILL_MD_NAME.lower() for p in normalized_input)
    if root_name and (flat_has_skill or not has_nested):
        wrapped = {f"{root_name}/{p}": d for p, d in normalized_input.items()}
        return parse_and_pack(wrapped, preferred_root=root_name)
    return parse_and_pack(normalized_input, preferred_root=root_name)


def create_empty_skill(*, name: str, description: str) -> ParsedSkillPackage:
    name = validate_skill_name(name)
    description = (description or "").strip()
    if not description:
        raise ValueError("description 不能为空")
    body = (
        f"\n# {name}\n\n"
        f"{description}\n\n"
        f"## Instructions\n\n"
        f"Describe how the agent should use this skill.\n"
    )
    skill_md = build_skill_md(name=name, description=description, body=body)
    relative = {SKILL_MD_NAME: skill_md.encode("utf-8")}
    package_zip = pack_skill_zip(name, relative)
    return ParsedSkillPackage(
        name=name,
        description=description,
        skill_md=skill_md,
        files=relative,
        package_zip=package_zip,
        size_bytes=len(package_zip),
    )


def replace_skill_md(package_zip: bytes, new_skill_md: str) -> ParsedSkillPackage:
    files = _files_from_zip_bytes(package_zip)
    _root, relative = _normalize_to_root_files(files)
    skill_key = _find_skill_md(relative)
    relative.pop(skill_key, None)
    relative[SKILL_MD_NAME] = new_skill_md.encode("utf-8")

    meta, _ = parse_frontmatter(new_skill_md)
    name = validate_skill_name(str(meta.get("name", "")))
    description = str(meta.get("description", "")).strip()
    if not description:
        raise ValueError("frontmatter 必须包含非空 description")

    # If name changed, root folder follows name
    package_zip = pack_skill_zip(name, relative)
    return ParsedSkillPackage(
        name=name,
        description=description,
        skill_md=new_skill_md,
        files=relative,
        package_zip=package_zip,
        size_bytes=len(package_zip),
    )


def _parse_github_url(url: str) -> tuple[str, str, str | None, str | None]:
    """Return owner, repo, ref, subpath."""
    parsed = urlparse(url.strip())
    if parsed.netloc not in ("github.com", "www.github.com"):
        raise ValueError("仅支持 github.com 链接")
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2:
        raise ValueError("无效的 GitHub URL")
    owner, repo = parts[0], parts[1].removesuffix(".git")
    ref: str | None = None
    subpath: str | None = None
    if len(parts) >= 4 and parts[2] in ("tree", "blob"):
        ref = parts[3]
        if len(parts) > 4:
            subpath = "/".join(parts[4:])
    elif len(parts) >= 3 and parts[2] == "releases":
        raise ValueError("请使用仓库或目录链接，暂不支持 releases 页")
    return owner, repo, ref, subpath


def _slice_github_skill(all_files: dict[str, bytes], skill_dir: str) -> ParsedSkillPackage:
    """skill_dir is archive path to the skill folder (no trailing slash)."""
    root_name = skill_dir.rstrip("/").split("/")[-1]
    prefix = skill_dir.rstrip("/") + "/"
    wrapped: dict[str, bytes] = {}
    for path, data in all_files.items():
        if path.startswith(prefix):
            wrapped[f"{root_name}/{path[len(prefix):]}"] = data
    if f"{root_name}/{SKILL_MD_NAME}" not in wrapped and not any(
        k.lower().endswith("/skill.md") for k in wrapped
    ):
        raise ValueError(f"目录中缺少 {SKILL_MD_NAME}: {skill_dir}")
    return parse_and_pack(wrapped)


async def fetch_github_skill(url: str) -> ParsedSkillPackage:
    owner, repo, ref, subpath = _parse_github_url(url)
    ref = ref or "HEAD"
    zip_url = f"https://codeload.github.com/{owner}/{repo}/zip/{ref}"
    async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
        resp = await client.get(zip_url)
        if resp.status_code >= 400:
            raise ValueError(f"拉取 GitHub 仓库失败 ({resp.status_code})")
        raw = resp.content
    if len(raw) > 50 * 1024 * 1024:
        raise ValueError("仓库归档过大，请改用包含 Skill 的子目录 zip 上传")

    all_files = _files_from_zip_bytes(raw)
    archive_roots = {p.split("/", 1)[0] for p in all_files if "/" in p}
    if len(archive_roots) != 1:
        # rare; still try
        archive_root = next(iter(archive_roots), "")
    else:
        archive_root = next(iter(archive_roots))

    if subpath:
        skill_dir = f"{archive_root}/{subpath.strip('/')}"
        return _slice_github_skill(all_files, skill_dir)

    skill_paths = [
        p for p in all_files if p.endswith("/" + SKILL_MD_NAME) or p.lower().endswith("/skill.md")
    ]
    if not skill_paths:
        raise ValueError("仓库中未找到 SKILL.md，请提供指向 Skill 目录的 URL")
    if len(skill_paths) > 1:
        raise ValueError(
            f"仓库中找到多个 SKILL.md（{len(skill_paths)} 个），请使用指向具体 Skill 目录的 URL"
        )
    parent = skill_paths[0].rsplit("/", 1)[0]
    return _slice_github_skill(all_files, parent)

