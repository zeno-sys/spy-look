"""PP-FormulaNet+ M（CPU / ONNX）公式识别服务。

将公式区域图像识别为 LaTeX 字符串。
"""
from __future__ import annotations

import base64
import json
import math
import re
import threading
from pathlib import Path
from typing import Any, List, Union

import cv2
import numpy as np
import onnxruntime as ort
from ftfy import fix_text
from PIL import Image, ImageOps
from tokenizers import Tokenizer as TokenizerFast

_REPO_ROOT = Path(__file__).resolve().parents[4]
_SERVICE_DIR = Path(__file__).resolve().parent
_TOOL_DIR = Path(__file__).resolve().parents[1]
MODELS_SEARCH_DIRS = (
    _REPO_ROOT / "models",
    _SERVICE_DIR / "models",
    _TOOL_DIR / "models",
)

MODEL_NAME = "pp_formulanet_plus_m.onnx"
IMG_SIZE = (384, 384)  # (h, w)
EOS_TOKEN_ID = 2


def resolve_model(filename: str = MODEL_NAME) -> Path:
    for base in MODELS_SEARCH_DIRS:
        path = base / filename
        if path.is_file():
            return path
    searched = "\n".join(f"  - {d}" for d in MODELS_SEARCH_DIRS)
    raise FileNotFoundError(f"模型不存在: {filename}\n请放到以下任一目录:\n{searched}")


def expected_models_dir() -> Path:
    return MODELS_SEARCH_DIRS[0]


# ---------------------------------------------------------------------------
# 预处理
# ---------------------------------------------------------------------------
def crop_margin(img: Image.Image) -> Image.Image:
    data = np.array(img.convert("L"), dtype=np.uint8)
    max_val, min_val = data.max(), data.min()
    if max_val == min_val:
        return img
    data = (data - min_val) / (max_val - min_val) * 255
    gray = 255 * (data < 200).astype(np.uint8)
    coords = cv2.findNonZero(gray)
    if coords is None:
        return img
    a, b, w, h = cv2.boundingRect(coords)
    return img.crop((a, b, w + a, h + b))


def resize_keep_short(img: Image.Image, size: int) -> Image.Image:
    width, height = img.size
    if width <= height:
        new_w, new_h = size, int(size * height / width)
    else:
        new_h, new_w = size, int(size * width / height)
    return img.resize((new_w, new_h), resample=Image.BILINEAR)


def decode_image(img_rgb: np.ndarray, input_size: tuple[int, int] = IMG_SIZE) -> np.ndarray:
    img = crop_margin(Image.fromarray(img_rgb).convert("RGB"))
    if img.height == 0 or img.width == 0:
        raise ValueError("裁边后图像为空")
    img = resize_keep_short(img, min(input_size))
    img.thumbnail((input_size[1], input_size[0]))
    delta_w = input_size[1] - img.width
    delta_h = input_size[0] - img.height
    pad_w, pad_h = delta_w // 2, delta_h // 2
    padding = (pad_w, pad_h, delta_w - pad_w, delta_h - pad_h)
    return np.array(ImageOps.expand(img, padding))


def normalize_image(img: np.ndarray) -> np.ndarray:
    mean = np.array([0.7931, 0.7931, 0.7931], dtype=np.float32).reshape(1, 1, 3)
    std = np.array([0.1738, 0.1738, 0.1738], dtype=np.float32).reshape(1, 1, 3)
    img = (img.astype(np.float32) / 255.0 - mean) / std
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return cv2.merge([np.squeeze(gray)] * 3)


def to_model_input(img: np.ndarray) -> np.ndarray:
    im_h, im_w = img.shape[:2]
    divide_h = math.ceil(im_h / 16) * 16
    divide_w = math.ceil(im_w / 16) * 16
    img = img[:, :, 0]
    img = np.pad(img, ((0, divide_h - im_h), (0, divide_w - im_w)), constant_values=(1, 1))
    return img[:, :, None].transpose(2, 0, 1)[None, ...].astype(np.float32)


def preprocess(img_rgb: np.ndarray) -> np.ndarray:
    return to_model_input(normalize_image(decode_image(img_rgb)))


# ---------------------------------------------------------------------------
# LaTeX 轻量修复
# ---------------------------------------------------------------------------
LEFT_COUNT_PATTERN = re.compile(r"\\left(?![a-zA-Z])")
RIGHT_COUNT_PATTERN = re.compile(r"\\right(?![a-zA-Z])")
LEFT_RIGHT_REMOVE_PATTERN = re.compile(r"\\left\.?|\\right\.?")
UP_PATTERN = re.compile(r"\\up([a-zA-Z]+)")
COMMANDS_TO_REMOVE = re.compile(
    r"\\(?:lefteqn|boldmath|ensuremath|centering|textsubscript|sides|textsl|textcent|emph|protect|null)"
)
CHINESE_TEXT_WRAP = re.compile(r"\\text\s*{\s*([^}]*?[\u4e00-\u9fff]+[^}]*?)\s*}")

ENV_TYPES = [
    "array", "matrix", "pmatrix", "bmatrix", "vmatrix",
    "Bmatrix", "Vmatrix", "cases", "aligned", "gathered", "align", "align*",
]
ENV_BEGIN = {env: re.compile(rf"\\begin\{{{env}\}}") for env in ENV_TYPES}
ENV_END = {env: re.compile(rf"\\end\{{{env}\}}") for env in ENV_TYPES}
ENV_FORMAT = {env: re.compile(rf"\\begin\{{{env}\}}\{{([^}}]*)\}}") for env in ENV_TYPES}


def fix_latex_left_right(s: str) -> str:
    left_count = len(LEFT_COUNT_PATTERN.findall(s))
    right_count = len(RIGHT_COUNT_PATTERN.findall(s))
    if left_count != right_count:
        return LEFT_RIGHT_REMOVE_PATTERN.sub("", s)
    return s


def fix_latex_environments(s: str) -> str:
    for env in ENV_TYPES:
        begin_count = len(ENV_BEGIN[env].findall(s))
        end_count = len(ENV_END[env].findall(s))
        if begin_count == end_count:
            continue
        if end_count > begin_count:
            fmt_match = ENV_FORMAT[env].search(s)
            default_fmt = "{c}" if env == "array" else ""
            fmt = "{" + fmt_match.group(1) + "}" if fmt_match else default_fmt
            s = (f"\\begin{{{env}}}" + fmt + " ") * (end_count - begin_count) + s
        else:
            s = s + (f" \\end{{{env}}}") * (begin_count - end_count)
    return s


def remove_up_commands(s: str) -> str:
    keep = {"arrow", "downarrow", "lus", "silon"}
    return UP_PATTERN.sub(
        lambda m: m.group(0) if m.group(1) in keep else f"\\{m.group(1)}", s
    )


def fix_latex(text: str) -> str:
    text = CHINESE_TEXT_WRAP.sub(lambda m: m.group(1), text).replace('"', "")
    text = fix_latex_left_right(text)
    text = fix_latex_environments(text)
    text = remove_up_commands(text)
    text = COMMANDS_TO_REMOVE.sub("", text)
    return fix_text(text)


# ---------------------------------------------------------------------------
# 解码
# ---------------------------------------------------------------------------
def build_tokenizer(character_meta: dict) -> TokenizerFast:
    buf = json.dumps(character_meta["fast_tokenizer_file"]).encode("utf-8")
    return TokenizerFast.from_buffer(buf)


def decode_tokens(token_ids: np.ndarray, tokenizer: TokenizerFast) -> str:
    tok_id = np.asarray(token_ids).reshape(-1)
    end_idx = np.argwhere(tok_id == EOS_TOKEN_ID)
    if len(end_idx) > 0:
        tok_id = tok_id[: int(end_idx[0][0]) + 1]
    text = tokenizer.decode(tok_id.tolist(), skip_special_tokens=True)
    return fix_latex(text)


# ---------------------------------------------------------------------------
# 模型封装
# ---------------------------------------------------------------------------
class PPFormulaNetPlusMCPU:
    def __init__(self, model_path: Union[str, Path, None] = None):
        model_path = Path(model_path) if model_path else resolve_model()
        if not model_path.is_file():
            raise FileNotFoundError(f"模型不存在: {model_path}")

        self.session = ort.InferenceSession(
            str(model_path),
            providers=["CPUExecutionProvider"],
        )
        meta = self.session.get_modelmeta().custom_metadata_map
        character = json.loads(meta["character"])
        self.tokenizer = build_tokenizer(character)
        self.input_name = self.session.get_inputs()[0].name

    def predict(self, img_rgb: np.ndarray) -> str:
        blob = preprocess(img_rgb)
        preds = self.session.run(None, {self.input_name: blob})[0]
        return decode_tokens(preds[0], self.tokenizer)

    def batch_predict(self, images: List[np.ndarray]) -> List[str]:
        blobs = [preprocess(img) for img in images]
        batch = np.concatenate(blobs, axis=0)
        preds = self.session.run(None, {self.input_name: batch})[0]
        return [decode_tokens(p, self.tokenizer) for p in preds]


_model: PPFormulaNetPlusMCPU | None = None
_model_lock = threading.Lock()


def get_formula_model() -> PPFormulaNetPlusMCPU:
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                _model = PPFormulaNetPlusMCPU()
    return _model


def img_to_data_uri(img_bgr: np.ndarray, quality: int = 92) -> str:
    ok, buf = cv2.imencode(".jpg", img_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise RuntimeError("图像编码失败")
    b64 = base64.b64encode(buf.tobytes()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def decode_image_bytes(data: bytes) -> np.ndarray:
    if not data:
        raise ValueError("上传文件为空")
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("无法解码图片，请确认文件为有效图像")
    return img


def run_formula_on_bytes(data: bytes) -> dict[str, Any]:
    img_bgr = decode_image_bytes(data)
    h, w = img_bgr.shape[:2]
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    model = get_formula_model()
    latex = model.predict(img_rgb)
    return {
        "width": w,
        "height": h,
        "image_data_uri": img_to_data_uri(img_bgr),
        "latex": latex,
    }
