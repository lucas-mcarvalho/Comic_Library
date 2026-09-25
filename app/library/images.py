"""Utilitários de imagem: miniaturas de capa e comparação de capas."""

import io

from PIL import Image


def thumbnail(data: bytes, max_width: int) -> bytes:
    """Reduz a imagem para no máximo `max_width` de largura e devolve em JPEG."""
    image = Image.open(io.BytesIO(data))
    image.thumbnail((max_width, max_width * 3))
    output = io.BytesIO()
    image.convert("RGB").save(output, "JPEG", quality=88)
    return output.getvalue()


def cover_hash(data: bytes) -> int:
    """Hash perceptual (dHash de 64 bits): capas parecidas têm hashes com poucos bits diferentes."""
    image = Image.open(io.BytesIO(data)).convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    pixels = list(image.getdata())
    bits = 0
    for row in range(8):
        for col in range(8):
            bits = (bits << 1) | (pixels[row * 9 + col] > pixels[row * 9 + col + 1])
    return bits


def hash_distance(first: int, second: int) -> int:
    return (first ^ second).bit_count()
