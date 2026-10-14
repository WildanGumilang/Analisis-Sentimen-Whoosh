"""Kode samaran untuk ID ulasan Google.

ID ulasan asli (review_id) dapat dipakai untuk menemukan ulasan dan profil penulisnya di Google Maps.
Berkas yang dipublikasikan (data/public/, output/) memakai kode samaran ini sebagai gantinya.
"""
from __future__ import annotations

import hashlib


def kode_ulasan(review_id: str) -> str:
    """'U' + 10 karakter heksadesimal SHA-256 dari review_id (deterministik, satu arah)."""
    return "U" + hashlib.sha256(str(review_id).encode("utf-8")).hexdigest()[:10]
