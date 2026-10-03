"""Phone and name normalisation. Used for storing, searching and duplicate detection."""
import re
import unicodedata

from rapidfuzz import fuzz


def digits_of(raw: str) -> str:
    """Keep only digits; Devanagari digits (९८७६) are converted to 0-9 as well."""
    return "".join(str(unicodedata.decimal(c)) for c in (raw or "") if c.isdecimal())


def normalize_phone(raw: str) -> str:
    """+91 98765 43210, 098765 43210, 0091..., 9876543210  ->  '9876543210'."""
    d = digits_of(raw)
    if d.startswith("0091") and len(d) == 14:
        d = d[4:]
    elif len(d) == 12 and d.startswith("91"):
        d = d[2:]
    elif len(d) == 11 and d.startswith("0"):
        d = d[1:]
    if not re.fullmatch(r"[6-9]\d{9}", d):
        raise ValueError("Enter a valid 10-digit mobile number (with +91, a leading 0, or just 10 digits).")
    return d


def clean_name(name: str) -> str:
    """NFC-normalise (Devanagari can be typed in different code point orders) and squash spaces."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", name or "")).strip()


# --- Devanagari -> rough Latin, only so that "राहुल" and "Rahul" can be compared ---
_VOWELS = {"अ": "a", "आ": "a", "इ": "i", "ई": "i", "उ": "u", "ऊ": "u", "ऋ": "ri", "ए": "e", "ऐ": "ai",
           "ओ": "o", "औ": "au", "ऑ": "o"}
_MATRAS = {"ा": "a", "ि": "i", "ी": "i", "ु": "u", "ू": "u", "ृ": "ri", "े": "e", "ै": "ai", "ो": "o",
           "ौ": "au", "ॉ": "o", "ॅ": "e"}
_CONSONANTS = {"क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "n", "च": "ch", "छ": "chh", "ज": "j",
               "झ": "jh", "ञ": "n", "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n", "त": "t",
               "थ": "th", "द": "d", "ध": "dh", "न": "n", "प": "p", "फ": "f", "ब": "b", "भ": "bh",
               "म": "m", "य": "y", "र": "r", "ल": "l", "व": "v", "श": "sh", "ष": "sh", "स": "s", "ह": "h"}
_MARKS = {"ं": "n", "ँ": "n", "ः": "h"}  # halant and nukta are simply ignored


def to_latin(text: str) -> str:
    out = []
    for ch in unicodedata.normalize("NFC", text):
        for table in (_CONSONANTS, _VOWELS, _MATRAS, _MARKS):
            if ch in table:
                out.append(table[ch])
                break
        else:
            if ch.isspace():
                out.append(" ")
            elif ch.isascii() and ch.isalpha():
                out.append(ch.lower())
    return "".join(out)


_DIGRAPHS = [("chh", "c"), ("ch", "c"), ("sh", "s"), ("kh", "k"), ("gh", "g"), ("th", "t"),
             ("dh", "d"), ("bh", "b"), ("ph", "p"), ("jh", "j")]


def name_key(name: str) -> str:
    """Spelling-insensitive skeleton: 'Rahul', 'Rahool' and 'राहुल' all become 'rl'."""
    s = to_latin(clean_name(name))
    for a, b in _DIGRAPHS:
        s = s.replace(a, b)
    s = s.translate(str.maketrans({"w": "v", "z": "j", "f": "p", "q": "k"}))
    s = re.sub(r"[aeiouyh]", "", s)       # vowels and h cause most spelling variation
    s = re.sub(r"(.)\1+", r"\1", s)       # double letters
    return re.sub(r"\s+", " ", s).strip()


def name_similarity(a: str, b: str) -> int:
    """0-100. Takes the better of the phonetic comparison and the plain-text comparison."""
    ka, kb = name_key(a), name_key(b)
    phonetic = fuzz.token_sort_ratio(ka, kb) if ka and kb else 0
    plain = fuzz.token_sort_ratio(clean_name(a).casefold(), clean_name(b).casefold())
    return int(max(phonetic, plain))
