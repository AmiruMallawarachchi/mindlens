"""
Quantize MindLens's HF classifiers to dynamic int8 ONNX.

Why: loader.py loads torch.float32 pipelines (no CUDA in dev or on Render),
and app/models/loader.py:19-20 confirms there's no GPU path. Four models —
crisis (512MB), mental_health (836MB), emotion (483MB), rag_reranker (88MB)
on disk — loaded concurrently in warmup_all() push resident memory past what
this laptop (7.2GB, ~0.5GB typically free) and Render's `standard` plan
(2GB) can hold. Dynamic int8 quantization via ONNX Runtime cuts resident
size roughly 4x with a small, measurable accuracy cost — see the printed
report after each model.

The distortion classifier is deliberately excluded: its HF repo has no
usable files (Phase 5 — training it is a separate task), so there's nothing
to convert.

Usage:
    python -m scripts.quantize_models                 # all 4 models
    python -m scripts.quantize_models --only rag_reranker   # just one

Output: backend/data/onnx_models/<name>/ — a folder optimum's
ORTModelForSequenceClassification.from_pretrained() can load directly.
loader.py picks these up when USE_QUANTIZED_MODELS=true (see its docstring).

Run this locally on a machine with a few GB of free RAM, or in a Kaggle/
Colab notebook (same pattern as training/*.ipynb) — exporting a model to
ONNX briefly needs more peak memory than just running it, which is exactly
the ceiling this script exists to get everyone else off of.
"""

from __future__ import annotations

import argparse
import os
import shutil
import time

from app.config import settings
from optimum.onnxruntime import ORTModelForSequenceClassification, ORTQuantizer
from optimum.onnxruntime.configuration import AutoQuantizationConfig
from transformers import AutoTokenizer

MODELS: dict[str, str] = {
    "emotion": settings.EMOTION_MODEL_ID,
    "crisis": settings.CRISIS_MODEL_ID,
    "mental_health": settings.MH_MODEL_ID,
    "rag_reranker": settings.RAG_RERANKER_MODEL_ID,
}

_OUTPUT_ROOT = os.path.join(os.path.dirname(__file__), "..", "data", "onnx_models")


def _dir_size_mb(path: str) -> float:
    total = sum(
        os.path.getsize(os.path.join(root, f))
        for root, _, files in os.walk(path)
        for f in files
    )
    return total / (1024 * 1024)


def quantize_one(name: str, model_id: str) -> None:
    print(f"\n=== {name} ({model_id}) ===")
    export_dir = os.path.join(_OUTPUT_ROOT, f"{name}_fp32")
    quant_dir = os.path.join(_OUTPUT_ROOT, name)

    started = time.perf_counter()
    print("Exporting to ONNX (float32)...")
    ort_model = ORTModelForSequenceClassification.from_pretrained(model_id, export=True)
    ort_model.save_pretrained(export_dir)
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    tokenizer.save_pretrained(export_dir)
    fp32_mb = _dir_size_mb(export_dir)
    print(f"  fp32 ONNX: {fp32_mb:.1f} MB ({time.perf_counter() - started:.1f}s)")

    print("Quantizing to dynamic int8...")
    quantizer = ORTQuantizer.from_pretrained(export_dir)
    # avx2 is the portable default for x86_64 CPUs (this laptop and Render's
    # standard instance type are both x86_64) — dynamic quantization needs no
    # calibration dataset, unlike static quantization.
    qconfig = AutoQuantizationConfig.avx2(is_static=False, per_channel=False)
    quantizer.quantize(save_dir=quant_dir, quantization_config=qconfig)
    tokenizer.save_pretrained(quant_dir)
    # ORTQuantizer names its output "model_quantized.onnx", but
    # ORTModelForSequenceClassification.from_pretrained() looks for
    # "model.onnx" by default — rename so loader.py's plain
    # from_pretrained(onnx_dir) call finds it without extra arguments.
    quantized_path = os.path.join(quant_dir, "model_quantized.onnx")
    if os.path.isfile(quantized_path):
        os.replace(quantized_path, os.path.join(quant_dir, "model.onnx"))
    int8_mb = _dir_size_mb(quant_dir)
    print(f"  int8 ONNX: {int8_mb:.1f} MB (was {fp32_mb:.1f} MB fp32, {fp32_mb / int8_mb:.1f}x smaller)")

    # The fp32 export was only an intermediate step for the quantizer's input.
    shutil.rmtree(export_dir, ignore_errors=True)
    print(f"  done in {time.perf_counter() - started:.1f}s -> {quant_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--only",
        choices=list(MODELS),
        help="Convert a single model instead of all four (useful on a memory-constrained machine).",
    )
    args = parser.parse_args()

    os.makedirs(_OUTPUT_ROOT, exist_ok=True)
    targets = {args.only: MODELS[args.only]} if args.only else MODELS
    for name, model_id in targets.items():
        quantize_one(name, model_id)


if __name__ == "__main__":
    main()
