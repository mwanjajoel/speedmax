"""Generates fixture image files at run time so the repo does not carry megabytes of noise."""
import os
import struct
import sys
import zlib
from pathlib import Path


def png(path: Path, w: int, h: int) -> None:
    raw = b"".join(b"\x00" + os.urandom(w * 3) for _ in range(h))

    def chunk(t: bytes, d: bytes) -> bytes:
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw, 1)) + chunk(b"IEND", b""))


def blob(path: Path, header: bytes, size: int) -> None:
    path.write_bytes(header + os.urandom(size))


def generate(fixture: str, root: Path) -> None:
    if fixture == "slow-shop":
        (root / "public/img").mkdir(parents=True, exist_ok=True)
        png(root / "public/hero.png", 600, 500)  # ~900 KB PNG hero
        for i in range(1, 7):
            blob(root / f"public/img/g{i}.jpg", b"\xff\xd8\xff\xe0", 320_000)
    elif fixture == "lean-site":
        (root / "public/img").mkdir(parents=True, exist_ok=True)
        for name, size in [("hero-640.avif", 28_000), ("hero-1280.avif", 61_000), ("hero-640.webp", 39_000), ("hero-1280.webp", 84_000)]:
            blob(root / f"public/img/{name}", b"RIFF" if name.endswith("webp") else b"\x00\x00\x00\x1cftypavif", size)
        for i in range(1, 4):
            blob(root / f"public/img/card-{i}.webp", b"RIFF", 18_000)


if __name__ == "__main__":
    generate(sys.argv[1], Path(sys.argv[2]))
