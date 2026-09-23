from pathlib import Path

from sentence_transformers import (
    CrossEncoder,
    export_dynamic_quantized_onnx_model,
)


MODEL_NAME = "BAAI/bge-reranker-v2-m3"
OUTPUT_DIR = Path(
    "models/bge-reranker-v2-m3-onnx"
)


def main():
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("Loading ONNX model...")

    model = CrossEncoder(
        MODEL_NAME,
        backend="onnx",
    )

    print("Saving local ONNX model...")

    model.save_pretrained(
        str(OUTPUT_DIR)
    )

    print("Quantizing to INT8...")

    export_dynamic_quantized_onnx_model(
        model=model,
        quantization_config="avx2",
        model_name_or_path=str(
            OUTPUT_DIR
        ),
        file_suffix="qint8_avx2",
    )

    print()
    print("=== COMPLETE ===")
    print(
        f"Saved to: {OUTPUT_DIR}"
    )


if __name__ == "__main__":
    main()