# PDF Handwriting Analyzer Setup

## GLM-OCR serving

This project uses **GLM-OCR** as the primary handwriting extraction model.

### Model
- `mlx-community/GLM-OCR-bf16`

### Runtime
- served with `mlx-vlm.server`
- local endpoint: `http://127.0.0.1:11436`

### Why `mlx-vlm` and not `mlx-lm`
The GLM-OCR model page indicates MLX-VLM usage, and the model type is `glm_ocr`.
Current `mlx-lm` on this machine does not support that model type.

---

## Local environment

Project-local virtual environment:
- `.venv`

Important package:
- `mlx-vlm`

---

## Start GLM-OCR server

Use the provided startup script:

```bash
./scripts/start-glm-ocr.sh
```

Equivalent command:

```bash
.venv/bin/python -m mlx_vlm.server \
  --model mlx-community/GLM-OCR-bf16 \
  --host 127.0.0.1 \
  --port 11436 \
  --trust-remote-code
```

---

## Installed model cache

Current expected Hugging Face cache location:

```bash
~/.cache/huggingface/hub/models--mlx-community--GLM-OCR-bf16
```

This is the actual cached model copy on this Mac.

---

## Planned serving layout

- `11436` -> GLM-OCR via `mlx-vlm.server`
- `11435` -> Gemma4 review/refine model via separate server

Only one model should be served per port.

---

## Notes

- GLM-OCR setup is now validated enough to serve locally.
- Analyzer implementation should call the GLM-OCR endpoint on port `11436`.
- Review/refine flow remains separate on port `11435`.
