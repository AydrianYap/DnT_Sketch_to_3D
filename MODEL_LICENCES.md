# AI model licences (classroom review)

The app only loads models listed in `DNT_ALLOWED_MODELS` (default: `triposr`).
Before adding a model to that list, read its licence at the source link and,
if in doubt, check with your school's ICT or procurement team.

This table is a summary written to help that review, **not legal advice**.
Licences change, so always confirm on the linked pages.

| Model | Used for | Licence (code / weights) | Classroom notes | Default |
|---|---|---|---|---|
| **TripoSR** (Stability AI + Tripo AI) | Fast image-to-3D. Runs on NVIDIA, Apple Silicon or CPU. | MIT / MIT. [Code](https://github.com/VAST-AI-Research/TripoSR), [weights](https://huggingface.co/stabilityai/TripoSR) | Simplest licence. Lowest shape quality of the four. | **Allowed** |
| **Hunyuan3D-2** (Tencent) | Better shape quality (shape model, about 6-8 GB VRAM). | Tencent Hunyuan 3D 2.0 Community License. [Code](https://github.com/Tencent-Hunyuan/Hunyuan3D-2) | Licence territory excludes the EU, UK and South Korea (Singapore is not excluded). Has an acceptable-use policy. Read before enabling. | Off |
| **TRELLIS** (Microsoft) | High quality, about 16 GB+ VRAM. | MIT / MIT. [Code](https://github.com/microsoft/TRELLIS) | Some dependencies have their own terms, e.g. NVIDIA **nvdiffrast** (NVIDIA Source Code License, non-commercial/research use). Check before classroom use. | Off |
| **TRELLIS.2** (Microsoft) | Newest, about 24 GB+ VRAM. | MIT. [Code](https://github.com/microsoft/TRELLIS.2) | Needs Meta **DINOv3** (gated download, DINOv3 License, see `backend/models/dinov3_vitl16/LICENSE.md`). Native add-ons often fail to build on Windows. | Off |
| **rembg** background removal (ISNet / U2Net) | Removes the background from photos. | rembg MIT; model weights from their original projects | Weights download from GitHub on first start. No images are uploaded. | Used |

## Data protection

All models run on the local machine. In this version, no uploaded image is
sent to any outside service. The only internet access the AI part needs is the
one-time download of model weights (from Hugging Face and GitHub). After that,
it can run offline.

To enable another model after review, for example Hunyuan3D-2:

```bash
DNT_ALLOWED_MODELS=triposr,hunyuan ./PIXFORM.sh
```
