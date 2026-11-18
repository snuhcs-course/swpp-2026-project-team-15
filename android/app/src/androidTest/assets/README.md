# HE recognition test fixture

`he-synthetic.heic.b64` is a genuine 64×64 HEIC file encoded as Base64. It was generated locally from a uniform RGB(20,150,40) synthetic bitmap using Pillow/pillow-heif in a temporary tool environment on 2026-11-09. It contains no user photo or third-party image.

The test verifies Android can decode the real format, then checks that the legacy HEIC-compatible endpoint is chosen before calling a review endpoint that only supports JPEG/PNG/WebP. pillow-heif is not an app or server runtime dependency.
