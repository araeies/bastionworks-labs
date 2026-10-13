"""Seed codes and seed-derived values.

The lab page issues each learner a seed code per lab. The kit derives resource names and planted content
from it; the Verifier derives the same values to tell one learner's submission from another's.

The seed is NOT a secret: the learner sees it, and the derivation is public. It identifies; it does not
authenticate. The platform binds a seed to a learner server-side.
"""

import hashlib
import re

# Crockford base32 without I, L, O, U: unambiguous when read aloud or typed from a screen.
SEED_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_SEED_PATTERN = re.compile(r"^[0-9A-HJKMNP-TV-Z]{8}$")
_LOWER_ALNUM = "0123456789abcdefghijklmnopqrstuvwxyz"
_DOMAIN = "bastionworks/v1"


class InvalidSeed(ValueError):
    """The seed code is not 8 Crockford base32 characters."""


def normalise_seed(seed: str) -> str:
    """Accept 'k7q2-mx4p', 'K7Q2MX4P' or ' K7Q2 MX4P '; return 'K7Q2MX4P'."""
    cleaned = re.sub(r"[\s-]", "", seed).upper()
    if not _SEED_PATTERN.match(cleaned):
        raise InvalidSeed("seed must be 8 characters from 0-9 and A-Z excluding I, L, O and U (e.g. K7Q2-MX4P)")
    return cleaned


def format_seed(seed: str) -> str:
    """Display form: 'K7Q2-MX4P'."""
    value = normalise_seed(seed)
    return f"{value[:4]}-{value[4:]}"


def _digest(lab_id: str, seed: str, purpose: str) -> bytes:
    if not lab_id or "/" in lab_id or not purpose or "/" in purpose:
        raise ValueError("lab_id and purpose must be non-empty and contain no '/'")
    message = f"{_DOMAIN}/{lab_id}/{normalise_seed(seed)}/{purpose}".encode("ascii")
    return hashlib.sha256(message).digest()


def _encode(digest: bytes, alphabet: str, length: int) -> str:
    number = int.from_bytes(digest, "big")
    chars = []
    for _ in range(length):
        number, index = divmod(number, len(alphabet))
        chars.append(alphabet[index])
    return "".join(chars)


def derive_name(lab_id: str, seed: str, purpose: str, prefix: str, length: int, alphabet: str = "lower-alnum") -> str:
    """Deterministic resource name, e.g. derive_name('storage-sas-leak', seed, 'storageAccount', 'bwsas', 10)."""
    if not 4 <= length <= 20:
        raise ValueError("length must be 4..20")
    chars = "0123456789abcdef" if alphabet == "hex" else _LOWER_ALNUM
    return prefix + _encode(_digest(lab_id, seed, purpose), chars, length)


def derive_token(lab_id: str, seed: str, purpose: str, length: int = 24) -> str:
    """Deterministic planted content (e.g. a marker string inside a blob)."""
    if not 8 <= length <= 48:
        raise ValueError("length must be 8..48")
    return _encode(_digest(lab_id, seed, purpose), _LOWER_ALNUM, length)
