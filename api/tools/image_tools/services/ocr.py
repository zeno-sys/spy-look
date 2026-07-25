"""PP-OCRv6 det/rec small（CPU / ONNX）推理服务。

不依赖 RapidOCR 多层封装，仅用 onnxruntime + opencv + numpy
（DB unclip 需要 pyclipper + shapely）。
"""
from __future__ import annotations

import base64
import math
import threading
from pathlib import Path
from typing import Any, List, Optional, Sequence, Tuple, Union

import cv2
import numpy as np
import onnxruntime as ort
import pyclipper
from shapely.geometry import Polygon

# 仓库根目录 models/；兼容 services/models 与 image_tools/models
_REPO_ROOT = Path(__file__).resolve().parents[4]
_SERVICE_DIR = Path(__file__).resolve().parent
_TOOL_DIR = Path(__file__).resolve().parents[1]
MODELS_SEARCH_DIRS = (
    _REPO_ROOT / "models",
    _SERVICE_DIR / "models",
    _TOOL_DIR / "models",
)

DET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
DET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
DET_THRESH = 0.3
DET_BOX_THRESH = 0.5
DET_UNCLIP_RATIO = 1.8
DET_USE_DILATION = True

REC_IMG_SHAPE = (3, 48, 320)  # C, H, W
REC_BATCH_NUM = 6
DROP_SCORE = 0.5

DET_MODEL_NAME = "ch_PP-OCRv6_det_small.onnx"
REC_MODEL_NAME = "ch_PP-OCRv6_rec_small.onnx"


def resolve_model(filename: str) -> Path:
    for base in MODELS_SEARCH_DIRS:
        path = base / filename
        if path.is_file():
            return path
    searched = "\n".join(f"  - {d}" for d in MODELS_SEARCH_DIRS)
    raise FileNotFoundError(f"模型不存在: {filename}\n请放到以下任一目录:\n{searched}")


def expected_models_dir() -> Path:
    return MODELS_SEARCH_DIRS[0]


# ---------------------------------------------------------------------------
# 检测：预处理 + DB 后处理
# ---------------------------------------------------------------------------
def det_preprocess(img_bgr: np.ndarray) -> Optional[np.ndarray]:
    h, w = img_bgr.shape[:2]
    max_wh = max(h, w)
    if max_wh < 960:
        limit_side_len = 960
    elif max_wh < 1500:
        limit_side_len = 1500
    else:
        limit_side_len = 2000

    if max_wh > limit_side_len:
        ratio = limit_side_len / float(max_wh)
    else:
        ratio = 1.0

    resize_h = int(round(h * ratio / 32) * 32)
    resize_w = int(round(w * ratio / 32) * 32)
    if resize_h <= 0 or resize_w <= 0:
        return None

    resized = cv2.resize(img_bgr, (resize_w, resize_h))
    blob = (resized.astype(np.float32) / 255.0 - DET_MEAN) / DET_STD
    return blob.transpose(2, 0, 1)[None, ...].astype(np.float32)


def _order_points_clockwise(pts: np.ndarray) -> np.ndarray:
    x_sorted = pts[np.argsort(pts[:, 0]), :]
    left, right = x_sorted[:2], x_sorted[2:]
    left = left[np.argsort(left[:, 1]), :]
    right = right[np.argsort(right[:, 1]), :]
    return np.array([left[0], right[0], right[1], left[1]], dtype=np.float32)


def _get_mini_boxes(contour: np.ndarray) -> Tuple[np.ndarray, float]:
    bounding_box = cv2.minAreaRect(contour)
    points = sorted(list(cv2.boxPoints(bounding_box)), key=lambda x: x[0])
    if points[1][1] > points[0][1]:
        index_1, index_4 = 0, 1
    else:
        index_1, index_4 = 1, 0
    if points[3][1] > points[2][1]:
        index_2, index_3 = 2, 3
    else:
        index_2, index_3 = 3, 2
    box = np.array(
        [points[index_1], points[index_2], points[index_3], points[index_4]]
    )
    return box, min(bounding_box[1])


def _box_score_fast(bitmap: np.ndarray, box: np.ndarray) -> float:
    h, w = bitmap.shape[:2]
    box = box.copy()
    xmin = int(np.clip(np.floor(box[:, 0].min()), 0, w - 1))
    xmax = int(np.clip(np.ceil(box[:, 0].max()), 0, w - 1))
    ymin = int(np.clip(np.floor(box[:, 1].min()), 0, h - 1))
    ymax = int(np.clip(np.ceil(box[:, 1].max()), 0, h - 1))
    mask = np.zeros((ymax - ymin + 1, xmax - xmin + 1), dtype=np.uint8)
    box[:, 0] -= xmin
    box[:, 1] -= ymin
    cv2.fillPoly(mask, box.reshape(1, -1, 2).astype(np.int32), 1)
    return cv2.mean(bitmap[ymin : ymax + 1, xmin : xmax + 1], mask)[0]


def _unclip(box: np.ndarray, unclip_ratio: float = DET_UNCLIP_RATIO) -> np.ndarray:
    poly = Polygon(box)
    distance = poly.area * unclip_ratio / poly.length
    offset = pyclipper.PyclipperOffset()
    offset.AddPath(box, pyclipper.JT_ROUND, pyclipper.ET_CLOSEDPOLYGON)
    expanded = np.array(offset.Execute(distance)).reshape((-1, 1, 2))
    return expanded


def det_postprocess(
    pred: np.ndarray,
    ori_shape: Tuple[int, int],
    thresh: float = DET_THRESH,
    box_thresh: float = DET_BOX_THRESH,
    unclip_ratio: float = DET_UNCLIP_RATIO,
    use_dilation: bool = DET_USE_DILATION,
    max_candidates: int = 1000,
) -> Tuple[np.ndarray, List[float]]:
    src_h, src_w = ori_shape
    pred = pred[:, 0, :, :]
    mask = (pred[0] > thresh).astype(np.uint8)
    if use_dilation:
        mask = cv2.dilate(mask, np.array([[1, 1], [1, 1]], dtype=np.uint8))

    outs = cv2.findContours(
        (mask * 255).astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE
    )
    contours = outs[0] if len(outs) == 2 else outs[1]

    boxes, scores = [], []
    for contour in contours[:max_candidates]:
        points, sside = _get_mini_boxes(contour)
        if sside < 3:
            continue
        score = _box_score_fast(pred[0], points.reshape(-1, 2))
        if score < box_thresh:
            continue
        box = _unclip(points, unclip_ratio)
        box, sside = _get_mini_boxes(box)
        if sside < 5:
            continue
        height, width = mask.shape
        box[:, 0] = np.clip(np.round(box[:, 0] / width * src_w), 0, src_w)
        box[:, 1] = np.clip(np.round(box[:, 1] / height * src_h), 0, src_h)
        box = _order_points_clockwise(box.astype(np.float32))
        box[:, 0] = np.clip(box[:, 0], 0, src_w - 1)
        box[:, 1] = np.clip(box[:, 1], 0, src_h - 1)
        rect_w = int(np.linalg.norm(box[0] - box[1]))
        rect_h = int(np.linalg.norm(box[0] - box[3]))
        if rect_w <= 3 or rect_h <= 3:
            continue
        boxes.append(box.astype(np.float32))
        scores.append(float(score))

    if not boxes:
        return np.array([]), []
    return np.array(boxes, dtype=np.float32), scores


def sorted_boxes(dt_boxes: np.ndarray) -> List[np.ndarray]:
    boxes = sorted(list(dt_boxes), key=lambda x: (x[0][1], x[0][0]))
    for i in range(len(boxes) - 1):
        for j in range(i, -1, -1):
            if abs(boxes[j + 1][0][1] - boxes[j][0][1]) < 10 and (
                boxes[j + 1][0][0] < boxes[j][0][0]
            ):
                boxes[j], boxes[j + 1] = boxes[j + 1], boxes[j]
            else:
                break
    return boxes


# ---------------------------------------------------------------------------
# 裁剪 + 识别
# ---------------------------------------------------------------------------
def get_rotate_crop_image(img: np.ndarray, points: np.ndarray) -> np.ndarray:
    assert len(points) == 4, "shape of points must be 4*2"
    img_crop_width = int(
        max(np.linalg.norm(points[0] - points[1]), np.linalg.norm(points[2] - points[3]))
    )
    img_crop_height = int(
        max(np.linalg.norm(points[0] - points[3]), np.linalg.norm(points[1] - points[2]))
    )
    pts_std = np.float32(
        [
            [0, 0],
            [img_crop_width, 0],
            [img_crop_width, img_crop_height],
            [0, img_crop_height],
        ]
    )
    matrix = cv2.getPerspectiveTransform(points.astype(np.float32), pts_std)
    dst = cv2.warpPerspective(
        img,
        matrix,
        (img_crop_width, img_crop_height),
        borderMode=cv2.BORDER_REPLICATE,
        flags=cv2.INTER_CUBIC,
    )
    if dst.shape[0] * 1.0 / max(dst.shape[1], 1) >= 2.0:
        dst = np.rot90(dst)
    return dst


def resize_norm_img(img: np.ndarray, max_wh_ratio: float) -> np.ndarray:
    img_c, img_h, img_w = REC_IMG_SHAPE
    assert img_c == img.shape[2]
    img_w = int(img_h * max_wh_ratio)

    h, w = img.shape[:2]
    ratio = w / float(h)
    resized_w = img_w if math.ceil(img_h * ratio) > img_w else int(math.ceil(img_h * ratio))
    resized = cv2.resize(img, (resized_w, img_h)).astype("float32")
    resized = resized.transpose((2, 0, 1)) / 255.0
    resized = (resized - 0.5) / 0.5

    padding = np.zeros((img_c, img_h, img_w), dtype=np.float32)
    padding[:, :, :resized_w] = resized
    return padding


def ctc_decode(
    preds: np.ndarray, character: List[str]
) -> List[Tuple[str, float]]:
    preds_idx = preds.argmax(axis=2)
    preds_prob = preds.max(axis=2)
    results = []
    for batch_idx in range(len(preds_idx)):
        token_indices = preds_idx[batch_idx]
        selection = np.ones(len(token_indices), dtype=bool)
        selection[1:] = token_indices[1:] != token_indices[:-1]
        selection &= token_indices != 0  # blank

        confs = preds_prob[batch_idx][selection]
        if len(confs) == 0:
            results.append(("", 0.0))
            continue
        chars = [character[i] for i in token_indices[selection]]
        text = "".join(chars)
        score = float(np.mean(confs))
        results.append((text, round(score, 5)))
    return results


# ---------------------------------------------------------------------------
# 模型封装
# ---------------------------------------------------------------------------
class PPOCRV6CPU:
    """PP-OCRv6 det/rec small 单文件推理（强制 CPU / ONNX）。"""

    def __init__(
        self,
        det_path: Union[str, Path, None] = None,
        rec_path: Union[str, Path, None] = None,
        drop_score: float = DROP_SCORE,
    ):
        det_path = Path(det_path) if det_path else resolve_model(DET_MODEL_NAME)
        rec_path = Path(rec_path) if rec_path else resolve_model(REC_MODEL_NAME)
        if not det_path.is_file():
            raise FileNotFoundError(f"检测模型不存在: {det_path}")
        if not rec_path.is_file():
            raise FileNotFoundError(f"识别模型不存在: {rec_path}")

        self.drop_score = drop_score
        providers = ["CPUExecutionProvider"]
        self.det_session = ort.InferenceSession(str(det_path), providers=providers)
        self.rec_session = ort.InferenceSession(str(rec_path), providers=providers)

        meta = self.rec_session.get_modelmeta().custom_metadata_map
        chars = meta.get("character", "").splitlines()
        self.character = ["blank"] + chars + [" "]

        self.det_input = self.det_session.get_inputs()[0].name
        self.rec_input = self.rec_session.get_inputs()[0].name

    def detect(self, img_bgr: np.ndarray) -> List[np.ndarray]:
        blob = det_preprocess(img_bgr)
        if blob is None:
            return []
        pred = self.det_session.run(None, {self.det_input: blob})[0]
        boxes, _ = det_postprocess(pred, ori_shape=img_bgr.shape[:2])
        if len(boxes) == 0:
            return []
        return sorted_boxes(boxes)

    def recognize(self, img_list: Sequence[np.ndarray]) -> List[Tuple[str, float]]:
        if not img_list:
            return []

        width_list = [img.shape[1] / float(img.shape[0]) for img in img_list]
        indices = np.argsort(np.array(width_list))
        img_num = len(img_list)
        rec_res: List[Tuple[str, float]] = [("", 0.0)] * img_num

        for beg in range(0, img_num, REC_BATCH_NUM):
            end = min(img_num, beg + REC_BATCH_NUM)
            img_c, img_h, img_w = REC_IMG_SHAPE
            max_wh_ratio = img_w / float(img_h)
            for ino in range(beg, end):
                h, w = img_list[indices[ino]].shape[:2]
                max_wh_ratio = max(max_wh_ratio, w * 1.0 / h)

            batch = []
            for ino in range(beg, end):
                batch.append(resize_norm_img(img_list[indices[ino]], max_wh_ratio)[None, ...])
            batch = np.concatenate(batch, axis=0).astype(np.float32)
            preds = self.rec_session.run(None, {self.rec_input: batch})[0]
            line_results = ctc_decode(preds, self.character)
            for rno, one in enumerate(line_results):
                rec_res[indices[beg + rno]] = one
        return rec_res

    def ocr(self, img_bgr: np.ndarray) -> List[Tuple[list, Tuple[str, float]]]:
        """端到端：det + crop + rec，返回 [[box, (text, score)], ...]。"""
        dt_boxes = self.detect(img_bgr)
        if not dt_boxes:
            return []

        crops = [get_rotate_crop_image(img_bgr, box.copy()) for box in dt_boxes]
        rec_res = self.recognize(crops)

        results = []
        for box, (text, score) in zip(dt_boxes, rec_res):
            if score >= self.drop_score:
                results.append((box.tolist(), (text, score)))
        return results


_model: PPOCRV6CPU | None = None
_model_lock = threading.Lock()


def get_ocr_model() -> PPOCRV6CPU:
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                _model = PPOCRV6CPU()
    return _model


def score_color(score: float) -> str:
    t = max(0.0, min(1.0, (score - 0.5) / 0.5))
    r = int(245 - 120 * t)
    g = int(140 + 80 * t)
    b = int(40 + 40 * t)
    return f"#{r:02x}{g:02x}{b:02x}"


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


def build_ocr_payload(
    img_bgr: np.ndarray,
    ocr_res: List[Tuple[list, Tuple[str, float]]],
) -> dict[str, Any]:
    h, w = img_bgr.shape[:2]
    items: list[dict[str, Any]] = []
    texts: list[str] = []
    for i, (box, (text, score)) in enumerate(ocr_res):
        pts = np.asarray(box, dtype=np.float32).reshape(-1, 2)
        xs, ys = pts[:, 0], pts[:, 1]
        xmin, xmax = float(xs.min()), float(xs.max())
        ymin, ymax = float(ys.min()), float(ys.max())
        items.append(
            {
                "id": i,
                "text": text,
                "score": float(score),
                "points": [[round(float(x), 2), round(float(y), 2)] for x, y in pts],
                "xmin": round(xmin, 2),
                "ymin": round(ymin, 2),
                "xmax": round(xmax, 2),
                "ymax": round(ymax, 2),
                "color": score_color(float(score)),
            }
        )
        texts.append(text)

    return {
        "width": w,
        "height": h,
        "image_data_uri": img_to_data_uri(img_bgr),
        "items": items,
        "full_text": "\n".join(texts),
        "count": len(items),
    }


def run_ocr_on_bytes(data: bytes) -> dict[str, Any]:
    img = decode_image_bytes(data)
    model = get_ocr_model()
    results = model.ocr(img)
    return build_ocr_payload(img, results)
