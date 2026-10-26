#!/usr/bin/env python3
"""Generate macOS-style folder + file-type icons into WhiteSur-dark.

Usage: gen_icons.py <out_root> [--install]
  Without --install, writes a preview set into <out_root>.
  With --install, <out_root> is the WhiteSur-dark theme dir.
"""
import os, re, sys

FONT = "SF Pro Display, Inter, Cantarell, Ubuntu, sans-serif"

# ---------------------------------------------------------------- folder
FOLDER_DEFS = """<defs>
<linearGradient id="fb" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3f9ce6"/><stop offset="1" stop-color="#2f86d4"/></linearGradient>
<linearGradient id="ff" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#7fcbfa"/><stop offset="1" stop-color="#63b8f3"/></linearGradient>
<filter id="fs" x="-10%" y="-10%" width="120%" height="130%"><feDropShadow dx="0" dy="3" stdDeviation="3" flood-color="#000" flood-opacity="0.28"/></filter>
</defs>"""

def folder_svg(size, symbol=None, open_=False):
    front_top = 86 if open_ else 80
    body = f"""<g filter="url(#fs)">
<path d="M28 66 a14 14 0 0 1 14 -14 H98 c8 0 12 3 17 8 l7 7 c3 3 6 4 10 4 H212 a14 14 0 0 1 14 14 V196 H28 Z" fill="url(#fb)"/>
<rect x="26" y="{front_top}" width="204" height="{214 - front_top}" rx="14" fill="url(#ff)"/>
</g>
<rect x="27" y="{front_top + 1}" width="202" height="2" rx="1" fill="#fff" opacity="0.45"/>
<rect x="27" y="186" width="202" height="2" fill="#4aa3e6" opacity="0.35"/>
<rect x="27" y="191" width="202" height="2" fill="#4aa3e6" opacity="0.25"/>"""
    if symbol and size >= 22:
        body += (f'<g transform="translate(128 {(front_top + 186) / 2}) scale(1.05)" '
                 f'fill="#2f87d2" opacity="0.85">{SYMBOLS[symbol]}</g>')
    return svg(size, FOLDER_DEFS + body)

# symbols centred on 0,0, roughly 56px box
SYMBOLS = {
    "home": '<path d="M0 -28 L30 -2 H21 V26 H7 V8 H-7 V26 H-21 V-2 H-30 Z"/>',
    "desktop": '<path d="M-30 -24 H30 a4 4 0 0 1 4 4 V14 a4 4 0 0 1 -4 4 H6 V24 H14 V28 H-14 V24 H-6 V18 H-30 a4 4 0 0 1 -4 -4 V-20 a4 4 0 0 1 4 -4 Z M-28 -18 V12 H28 V-18 Z" fill-rule="evenodd"/>',
    "documents": '<path d="M-20 -28 H8 L22 -14 V28 H-20 Z M-12 -8 H14 V-3 H-12 Z M-12 4 H14 V9 H-12 Z M-12 16 H6 V21 H-12 Z" fill-rule="evenodd"/>',
    "download": '<path d="M-7 -28 H7 V0 H20 L0 22 L-20 0 H-7 Z M-26 22 H26 V30 H-26 Z"/>',
    "music": '<path d="M-6 -28 L24 -34 V12 a10 9 0 1 1 -7 -8.5 V-20 L1 -16 V18 a10 9 0 1 1 -7 -8.5 Z"/>',
    "images": '<path d="M-30 -22 H30 a4 4 0 0 1 4 4 V22 a4 4 0 0 1 -4 4 H-30 a4 4 0 0 1 -4 -4 V-18 a4 4 0 0 1 4 -4 Z M-26 18 H26 L8 -4 L-4 10 L-12 2 Z M10 -12 a7 7 0 1 0 0.1 0 Z" fill-rule="evenodd"/>',
    "videos": '<path d="M-30 -20 H14 a4 4 0 0 1 4 4 V-4 L32 -14 V14 L18 4 V16 a4 4 0 0 1 -4 4 H-30 a4 4 0 0 1 -4 -4 V-16 a4 4 0 0 1 4 -4 Z"/>',
    "templates": '<path d="M-24 -28 H24 V28 H-24 Z M-17 -21 V-8 H17 V-21 Z M-17 -2 V21 H-2 V-2 Z M4 -2 V21 H17 V-2 Z" fill-rule="evenodd"/>',
    "public": '<path d="M-14 -8 a10 10 0 1 1 0.1 0 Z M14 -8 a10 10 0 1 1 0.1 0 Z M-32 26 a18 16 0 0 1 36 0 Z M-4 26 a18 16 0 0 1 36 0 Z"/>',
}

FOLDERS = {  # icon name -> (symbol, open)
    "folder": (None, False), "folder-open": (None, True),
    "user-home": ("home", False), "user-desktop": ("desktop", False),
    "folder-documents": ("documents", False), "folder-download": ("download", False),
    "folder-music": ("music", False), "folder-images": ("images", False),
    "folder-videos": ("videos", False), "folder-templates": ("templates", False),
    "folder-public": ("public", False),
}

# ---------------------------------------------------------------- pages
PAGE_DEFS = """<defs>
<linearGradient id="pg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffffff"/><stop offset="1" stop-color="#f1f1f1"/></linearGradient>
<linearGradient id="pf" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="#f6f6f6"/><stop offset="0.5" stop-color="#e2e2e2"/><stop offset="1" stop-color="#cfcfcf"/></linearGradient>
<filter id="ps" x="-15%" y="-10%" width="130%" height="125%"><feDropShadow dx="0" dy="2" stdDeviation="3" flood-color="#000" flood-opacity="0.3"/></filter>
</defs>"""
PAGE = """<path d="M58 26 a8 8 0 0 1 8 -8 H158 L202 62 V230 a8 8 0 0 1 -8 8 H66 a8 8 0 0 1 -8 -8 Z" fill="url(#pg)" filter="url(#ps)"/>
<path d="M58 26 a8 8 0 0 1 8 -8 H158 L202 62 V230 a8 8 0 0 1 -8 8 H66 a8 8 0 0 1 -8 -8 Z" fill="none" stroke="#000" stroke-opacity="0.08"/>
<path d="M158 18 V54 a8 8 0 0 0 8 8 H202 Z" fill="url(#pf)"/>
<path d="M158 18 V54 a8 8 0 0 0 8 8 H202" fill="none" stroke="#000" stroke-opacity="0.07"/>"""
G = "#a9a9a9"  # glyph grey

def lines(y0, y1, step, h, seed, x0=72, x1=186):
    out, n = [], 0
    for y in range(y0, y1, step):
        n += 1
        w = (x1 - x0) * (0.55 + ((seed * 37 + n * 53) % 45) / 100)
        if n % 6 == 0:
            continue  # paragraph gap
        out.append(f'<rect x="{x0}" y="{y}" width="{w:.0f}" height="{h}" rx="{h/2}" fill="#5c5c5c" opacity="0.75"/>')
    return "".join(out)

GLYPHS = {
    "blank": "",
    "text": lines(34, 228, 9, 3, 1, x0=72, x1=150),
    "doc": f'<rect x="82" y="64" width="96" height="9" rx="3" fill="{G}"/>' + lines(86, 168, 13, 5, 2, 82, 178).replace('#5c5c5c', G).replace('opacity="0.75"', ''),
    "sheet": f'<g fill="none" stroke="{G}" stroke-width="7" stroke-linejoin="round"><rect x="84" y="84" width="92" height="66" rx="7"/><path d="M84 106 H176 M84 128 H176 M114 84 V150"/></g><rect x="84" y="84" width="92" height="22" rx="7" fill="{G}"/>',
    "pdf": f'<rect x="84" y="78" width="36" height="34" rx="4" fill="{G}"/><rect x="128" y="80" width="48" height="8" rx="4" fill="{G}"/><rect x="128" y="98" width="48" height="8" rx="4" fill="{G}"/><rect x="84" y="122" width="92" height="8" rx="4" fill="{G}"/><rect x="84" y="140" width="92" height="8" rx="4" fill="{G}"/><rect x="84" y="158" width="64" height="8" rx="4" fill="{G}"/>',
    "image": f'<path d="M90 82 H170 a10 10 0 0 1 10 10 V150 a10 10 0 0 1 -10 10 H90 a10 10 0 0 1 -10 -10 V92 a10 10 0 0 1 10 -10 Z M88 150 H172 L144 116 L124 138 L110 124 Z M150 100 a9 9 0 1 0 0.1 0 Z" fill="{G}" fill-rule="evenodd"/>',
    "zip": f'<g fill="{G}"><rect x="122" y="18" width="16" height="10"/>' + "".join(
        f'<rect x="{116 if i % 2 else 130}" y="{30 + i * 11}" width="14" height="7" rx="2"/>' for i in range(8)) +
        f'<path d="M118 120 H142 V156 a12 12 0 0 1 -24 0 Z M124 132 V154 a6 6 0 0 0 12 0 V132 Z" fill-rule="evenodd"/></g>',
    "install": '<defs><linearGradient id="ib" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fafafa"/><stop offset="1" stop-color="#d9d9d9"/></linearGradient></defs>'
        '<rect x="92" y="88" width="76" height="76" rx="14" fill="url(#ib)" stroke="#000" stroke-opacity="0.12" stroke-width="2"/>'
        f'<path d="M122 102 H138 V126 H150 L130 148 L110 126 H122 Z" fill="{G}"/>',
    "code": f'<g fill="none" stroke="{G}" stroke-width="10" stroke-linecap="round" stroke-linejoin="round"><path d="M106 96 L80 122 L106 148 M154 96 L180 122 L154 148 M140 88 L120 156"/></g>',
    "audio": f'<path d="M116 84 L170 72 V142 a14 12 0 1 1 -10 -11.5 V96 L126 104 V154 a14 12 0 1 1 -10 -11.5 Z" fill="{G}"/>',
    "video": f'<rect x="80" y="86" width="100" height="72" rx="12" fill="{G}"/><path d="M118 104 V140 L148 122 Z" fill="#fff"/>',
    "slides": f'<rect x="80" y="84" width="100" height="66" rx="8" fill="none" stroke="{G}" stroke-width="7"/><rect x="98" y="124" width="12" height="16" fill="{G}"/><rect x="118" y="110" width="12" height="30" fill="{G}"/><rect x="138" y="100" width="12" height="40" fill="{G}"/><rect x="126" y="150" width="8" height="12" fill="{G}"/>',
    "font": f'<text x="130" y="152" text-anchor="middle" font-family="Georgia, serif" font-size="74" fill="{G}">Aa</text>',
}

def page_svg(size, glyph, label=None):
    g = GLYPHS[glyph]
    if size < 32:
        if glyph == "text":
            g = lines(60, 210, 30, 12, 1, 80, 170)
        elif glyph == "zip":
            g = f'<rect x="120" y="20" width="20" height="140" fill="{G}"/><rect x="112" y="150" width="36" height="40" rx="8" fill="{G}"/>'
        g = f'<g transform="translate(128 130) scale(1.25) translate(-128 -124)">{g}</g>' if glyph not in ("text", "zip", "blank") else g
        label = None
    body = PAGE + g
    if label:
        body += (f'<text x="130" y="210" text-anchor="middle" font-family="{FONT}" font-weight="600" '
                 f'font-size="{30 if len(label) <= 4 else 24}" letter-spacing="1" fill="{G}">{label}</text>')
    return svg(size, PAGE_DEFS + body)

def svg(size, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
            f'viewBox="0 0 256 256">{body}</svg>\n')

# ---------------------------------------------------------------- mime classification
def has(name, *words):
    toks = set(re.split(r"[-_.+]", name))
    return any(w in toks for w in words)

def classify(n):
    """icon name (no .svg) -> (glyph, label) or None to keep the original"""
    n = n.lower()
    if n.startswith(("inode-", "x-office-address", "x-office-calendar")) or "folder" in n:
        return None
    if re.search(r"epub|ebook|mobi|comicbook|fictionbook|djvu", n):
        return ("doc", "EPUB" if "epub" in n else "BOOK")
    # installers / disk images
    if has(n, "deb", "debian", "rpm", "apk", "appimage", "flatpak", "flatpakref", "flatpakrepo", "snap", "msi",
           "executable", "msdownload", "install", "gdebi", "iso", "dmg", "pkg", "exe", "appinstaller",
           "appx", "appxbundle", "msix", "msixbundle", "cd", "disk", "img") or "package-archive" in n \
            or "disk-image" in n or "binary-package" in n or "portable-executable" in n:
        for k, l in (("deb", "DEB"), ("rpm", "RPM"), ("apk", "APK"), ("android", "APK"), ("appimage", "APP"),
                     ("flatpak", "FLATPAK"), ("snap", "SNAP"), ("iso", "ISO"), ("dmg", "DMG"), ("msi", "MSI"),
                     ("ms-dos", "EXE"), ("portable-executable", "EXE"), ("executable", "BIN"), ("exe", "EXE")):
            if k in n:
                return ("install", l)
        return ("install", None)
    if "pdf" in n and "banner" not in n:
        return ("pdf", "PDF")
    if n.startswith("image") or has(n, "jpeg", "jpg", "png", "gif", "bmp", "tiff", "webp", "svg", "psd",
                                    "photoshop", "xcf", "ico", "icon", "krita", "heic", "heif", "raw",
                                    "avif", "jxl", "images", "illustrator", "eps") or "gnome-mime-image" in n:
        for k, l in (("jpeg2000", "JP2"), ("jpeg", "JPG"), ("jpg", "JPG"), ("png", "PNG"), ("gif", "GIF"),
                     ("svg", "SVG"), ("webp", "WEBP"), ("psd", "PSD"), ("photoshop", "PSD"), ("tif", "TIFF"),
                     ("bmp", "BMP"), ("ico", "ICO"), ("heic", "HEIC"), ("avif", "AVIF"), ("xcf", "XCF"),
                     ("illustrator", "AI"), ("eps", "EPS")):
            if k in n:
                return ("image", l)
        return ("image", None)
    if n.startswith("video") or not n.startswith("audio") and has(n, "mp4", "matroska", "mkv", "webm", "avi", "msvideo", "quicktime",
                                    "flv", "wmv", "ogv", "m4v", "3gpp", "video") or "gnome-mime-video" in n:
        for k, l in (("mp4", "MP4"), ("matroska", "MKV"), ("mkv", "MKV"), ("webm", "WEBM"), ("quicktime", "MOV"),
                     ("avi", "AVI"), ("msvideo", "AVI"), ("wmv", "WMV"), ("flv", "FLV")):
            if k in n:
                return ("video", l)
        return ("video", None)
    if n.startswith("audio") or has(n, "mp3", "mpeg3", "flac", "wav", "ogg", "vorbis", "aac", "m4a", "opus",
                                    "midi", "mid", "music", "sound", "audio", "podcast", "mpegurl") \
            or "playlist" in n or "gnome-mime-audio" in n:
        for k, l in (("mp3", "MP3"), ("mpeg", "MP3"), ("flac", "FLAC"), ("wav", "WAV"), ("ogg", "OGG"),
                     ("vorbis", "OGG"), ("aac", "AAC"), ("m4a", "M4A"), ("opus", "OPUS"), ("midi", "MIDI")):
            if k in n:
                return ("audio", l)
        return ("audio", None)
    if "csv" in n or "comma-separated" in n:
        return ("sheet", "CSV")
    if re.search(r"spreadsheet|excel|xls|sheet|calc|gnumeric|numbers", n) or has(n, "table", "ods"):
        return ("sheet", "XLSX" if ("openxml" in n or "xlsx" in n) else "XLS")
    if re.search(r"presentation|powerpoint|ppt|impress|slides|keynote|kpresenter", n) or has(n, "odp"):
        return ("slides", "KEY" if "keynote" in n else "PPT")
    if "font" in n or has(n, "ttf", "otf", "woff", "woff2"):
        return ("font", "TTF" if "ttf" in n or "truetype" in n else "OTF" if "otf" in n or "opentype" in n else None)
    if re.search(r"compress|archive|zip|rar|lzma|zstd|cpio|bzip|gzip|tarball", n) or \
            has(n, "tar", "gz", "xz", "bz2", "7z", "7zip", "cab", "zoo", "lha", "lzh", "arj", "ace", "jar",
                "package", "zst", "lz", "lz4", "z"):
        for k, l in (("7z", "7Z"), ("7zip", "7Z"), ("rar", "RAR"), ("jar", "JAR"), ("zip", "ZIP"), ("tar", "TAR"),
                     ("gz", "GZ"), ("xz", "XZ"), ("bz", "BZ2"), ("zst", "ZST")):
            if k in n:
                return ("zip", l)
        return ("zip", "ZIP")
    if re.search(r"opendocument\.text|msword|wordprocessing|oasis-text|libreoffice-text|openoffice4-text|x-office-document|"
                 r"office-document|abiword|application-document|^document|stock_new-text|sxw|rtf|\bodt|docx?$", n) \
            or has(n, "doc", "docx", "odt", "rtf", "wps", "pages"):
        for k, l in (("openxml", "DOCX"), ("docx", "DOCX"), ("rtf", "RTF"), ("odt", "ODT"), ("oasis", "ODT"),
                     ("msword", "DOC"), ("word", "DOC")):
            if k in n:
                return ("doc", l)
        return ("doc", "DOC")
    code = [("python", "PY"), ("javascript", "JS"), ("typescript", "TS"), ("ecmascript", "JS"), ("json", "JSON"),
            ("html", "HTML"), ("css", "CSS"), ("scss", "SCSS"), ("sass", "SASS"), ("yaml", "YAML"),
            ("toml", "TOML"), ("xml", "XML"), ("sql", "SQL"), ("shellscript", "SH"), ("php", "PHP"),
            ("ruby", "RB"), ("perl", "PL"), ("rust", "RS"), ("kotlin", "KT"), ("swift", "SWIFT"),
            ("lua", "LUA"), ("java", "JAVA"), ("csharp", "C#"), ("c++", "CPP"), ("cpp", "CPP"),
            ("chdr", "H"), ("csrc", "C"), ("makefile", "MAKE"), ("cmake", "CMAKE"), ("dockerfile", "DOCKER"),
            ("patch", "DIFF"), ("diff", "DIFF"), ("coffeescript", "COFFEE"), ("go", "GO"), ("vue", "VUE"),
            ("dart", "DART")]
    for k, l in code:
        if (len(k) > 3 and k in n) or has(n, k):
            return ("code", l if len(l) <= 6 else None)
    if has(n, "sh", "bash", "zsh", "csh", "fish", "js", "ts", "py", "c", "h", "hpp", "rb", "rs", "awk",
           "script", "source", "src", "x-c", "jsx", "tsx") or "-x-sh" in n or "x-source" in n:
        return ("code", "SH" if has(n, "sh", "bash", "zsh", "csh", "fish") else None)
    if "markdown" in n or has(n, "md"):
        return ("text", None)
    if n.startswith("text") or re.search(r"plain|readme|changelog|authors|copying|credits|license|ascii|"
                                         r"\blog\b|txt|gnome-mime-text|stock_new-text", n) or has(n, "log", "text"):
        return ("text", None)
    if n in ("application-x-generic", "unknown", "empty", "application-octet-stream", "gtk-file", "none",
             "gnome-unknown", "application-blank", "application-document-blank", "misc",
             "application-x-zerosize") or n.endswith("-blank"):
        return ("blank", None)
    return None

# ---------------------------------------------------------------- main
def write(path, data):
    if os.path.islink(path) or os.path.exists(path):
        os.remove(path)
    with open(path, "w") as f:
        f.write(data)

def main():
    root, install = sys.argv[1], "--install" in sys.argv
    if not install:
        os.makedirs(root, exist_ok=True)
        for name, (sym, op) in FOLDERS.items():
            write(f"{root}/{name}.svg", folder_svg(256, sym, op))
        for glyph, label in [("blank", None), ("text", None), ("install", "DEB"), ("sheet", "XLS"), ("sheet", "CSV"),
                             ("zip", "ZIP"), ("code", "PY"), ("doc", "DOCX"), ("pdf", "PDF"), ("image", "JPG"),
                             ("image", "PNG"), ("audio", "MP3"), ("video", "MP4"), ("slides", "PPT"), ("font", "TTF")]:
            write(f"{root}/{glyph}-{label}.svg", page_svg(256, glyph, label))
            write(f"{root}/small-{glyph}-{label}.svg", page_svg(16, glyph, label))
        write(f"{root}/small-folder.svg", folder_svg(16))
        return
    # folders in places/
    for d, size in (("scalable", 256), ("16", 16), ("22", 22), ("24", 24)):
        for name, (sym, op) in FOLDERS.items():
            write(f"{root}/places/{d}/{name}.svg", folder_svg(size, sym, op))
    # mimes: scalable, 16, 22 (real dirs, not links)
    stats = {}
    for d, size in (("scalable", 256), ("16", 16), ("22", 22)):
        dd = f"{root}/mimes/{d}"
        assert not os.path.islink(dd), dd
        for fn in sorted(os.listdir(dd)):
            if not fn.endswith(".svg"):
                continue
            c = classify(fn[:-4])
            if c is None:
                continue
            write(f"{dd}/{fn}", page_svg(size, *c))
            if d == "scalable":
                stats.setdefault(c[0], []).append(fn[:-4])
    for k, v in sorted(stats.items()):
        print(f"{k:8} {len(v):4}  e.g. {', '.join(v[:6])}")

if __name__ == "__main__":
    main()
