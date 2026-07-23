"""Export MindLens sequence classifiers to quantized INT8 ONNX artifacts.

This script downloads model files from Hugging Face Hub only. It does not use
paid inference endpoints, Spaces, or hosted compute.

Example:
    python scripts/export_classifiers_to_onnx.py --model crisis --output-dir artifacts/onnx
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

MODELS = {
    "crisis": "AmiruMallawarachchi/mindlens-crisis",
    "emotion": "AmiruMallawarachchi/mindlens-emotion-classifier",
    "mental_health": "AmiruMallawarachchi/mindlens-mh-classifier",
    "distortion": "AmiruMallawarachchi/mindlens-distortion-classifier",
    "rag_reranker": "AmiruMallawarachchi/mindlens-rag-reranker",
}


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def export_model(name: str, model_id: str, output_dir: Path, quantize: bool) -> dict[str, str]:
    target = output_dir / name
    fp32_dir = target / "fp32"
    int8_dir = target / "int8"
    target.mkdir(parents=True, exist_ok=True)

    run(
        [
            sys.executable,
            "-m",
            "transformers.onnx",
            "--model",
            model_id,
            "--feature",
            "sequence-classification",
            str(fp32_dir),
        ]
    )

    final_dir = fp32_dir
    if quantize:
        try:
            from onnxruntime.quantization import QuantType, quantize_dynamic
        except ImportError as exc:  # pragma: no cover - dependency guidance path.
            raise RuntimeError("Install onnxruntime before using --quantize") from exc

        int8_dir.mkdir(parents=True, exist_ok=True)
        quantize_dynamic(
            model_input=fp32_dir / "model.onnx",
            model_output=int8_dir / "model.onnx",
            weight_type=QuantType.QInt8,
        )
        for filename in (
            "config.json",
            "tokenizer.json",
            "tokenizer_config.json",
            "special_tokens_map.json",
            "vocab.txt",
        ):
            source = fp32_dir / filename
            if source.exists():
                shutil.copy2(source, int8_dir / filename)
        final_dir = int8_dir

    return {
        "name": name,
        "model_id": model_id,
        "artifact_dir": str(final_dir),
        "model_bytes": str((final_dir / "model.onnx").stat().st_size),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=[*MODELS.keys(), "all"], default="crisis")
    parser.add_argument("--output-dir", default="artifacts/onnx")
    parser.add_argument("--quantize", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()

    selected = MODELS if args.model == "all" else {args.model: MODELS[args.model]}
    output_dir = Path(args.output_dir)
    results = []
    failures = []
    for name, model_id in selected.items():
        try:
            results.append(export_model(name, model_id, output_dir, args.quantize))
        except Exception as exc:
            failures.append(
                {"name": name, "model_id": model_id, "error": type(exc).__name__}
            )

    print(json.dumps({"exported": results, "failed": failures}, indent=2))
    if failures and not results:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
