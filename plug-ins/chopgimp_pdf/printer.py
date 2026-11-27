# -*- coding: utf-8 -*-
"""
ChopGimp 4.2.0 — « Fichier > Exporter pour l'imprimeur » et profils CMJN de l'ECI.

- PDF/X-1a:2001 : chaque page (l'image entière ou un plan de travail) est
  convertie en CMJN par l'export TIFF CMJN de GIMP (profil de simulation de
  l'image, mode de rendu, compensation du point noir), puis écrite en image
  CMJN (DeviceCMYK, PDF 1.3) avec l'intention de sortie (profil intégré).
- PDF/X-4 : l'export PDF vectoriel du lot 4b (file-pdf-export, cairo) est
  repris : les couleurs unies des tracés et des textes deviennent des valeurs
  CMJN du profil cible (noir pur → 100 % K au choix), les images et les
  dégradés restent en RVB balisé sRGB (ICCBased, permis par PDF/X-4), la
  transparence est gardée. En cas d'échec : PDF/X-4 en image CMJN.
- TIFF CMJN : un fichier par page, profil intégré.

Fond perdu (les pixels autour du plan de travail, sinon du blanc), traits de
coupe en couleur de repérage (/Separation /All), TrimBox / BleedBox.

Les profils PSO v3 de l'ECI ne peuvent pas être fournis (licence) :
download_eci() les télécharge depuis eci.org (somme SHA-256 vérifiée).
"""
import datetime
import hashlib
import io
import os
import re
import struct
import uuid
import zipfile
import zlib

from ocg import Name, Ref, Raw, Reader, ser, decode, text_string, PdfError

MM = 72.0 / 25.4

# ─── profils de l'ECI (téléchargement) ───────────────────────────────────

ECI_FILES = [
    # (archive, somme SHA-256 de l'archive, profil dans l'archive)
    ("https://www.eci.org/lib/exe/pso-coated_v3.zip",
     "5c8ed32d40949c2e8b84a03642ca7aadc4e3f153237cf439d3cdddffffd4ed95", "PSOcoated_v3.icc"),
    ("https://www.eci.org/lib/exe/pso-uncoated_v3_fogra52.zip",
     "644cabd621faa6f92c81f5596cd60f8360a7cb520b0061454c8d17e6b94cf08a",
     "PSOuncoated_v3_FOGRA52.icc"),
]
ECI_MIRRORS = ("https://www.eci.org/", "https://eci.org/")


def download_eci(dest_dir, progress=None):
    """Télécharge et vérifie les profils PSO v3 → liste des fichiers écrits."""
    import urllib.request
    os.makedirs(dest_dir, exist_ok=True)
    written = []
    for i, (url, sha, member) in enumerate(ECI_FILES):
        target = os.path.join(dest_dir, member)
        if os.path.exists(target):
            written.append(target)
            continue
        data, last = None, None
        for base in ECI_MIRRORS:
            u = url.replace(ECI_MIRRORS[0], base)
            try:
                req = urllib.request.Request(u, headers={"User-Agent": "ChopGimp"})
                with urllib.request.urlopen(req, timeout=60) as r:
                    data = r.read()
                if hashlib.sha256(data).hexdigest() == sha:
                    break
                last, data = "somme de contrôle inattendue (%s)" % u, None
            except Exception as e:  # noqa: BLE001 — essai suivant
                last, data = "%s : %s" % (u, e), None
        if data is None:
            raise RuntimeError("téléchargement impossible : %s" % last)
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            name = next(n for n in z.namelist()
                        if n.endswith(member) and "__MACOSX" not in n)
            icc = z.read(name)
        if icc[36:40] != b"acsp" or icc[16:20] != b"CMYK":
            raise RuntimeError("%s n'est pas un profil CMJN" % member)
        tmp = target + ".part"
        with open(tmp, "wb") as f:
            f.write(icc)
        os.replace(tmp, target)
        written.append(target)
        if progress:
            progress((i + 1) / len(ECI_FILES))
    return written


# ─── condition d'impression d'un profil ──────────────────────────────────

CONDITIONS = [("PSO Coated v3", "FOGRA51"), ("PSO Uncoated v3", "FOGRA52"),
              ("ISO Coated v2", "FOGRA39"), ("Coated FOGRA39", "FOGRA39"),
              ("PSO Uncoated ISO12647", "FOGRA47"), ("ISO Uncoated", "FOGRA29")]


def icc_description(icc):
    """Libellé « desc » d'un profil ICC (v2 desc ou v4 mluc)."""
    try:
        n = struct.unpack(">I", icc[128:132])[0]
        for i in range(n):
            sig, off, size = struct.unpack(">4sII", icc[132 + 12 * i:144 + 12 * i])
            if sig != b"desc":
                continue
            t = icc[off:off + size]
            if t[:4] == b"desc":
                ln = struct.unpack(">I", t[8:12])[0]
                return t[12:12 + ln].split(b"\0")[0].decode("latin-1")
            if t[:4] == b"mluc":
                rec = struct.unpack(">I", t[12:16])[0]
                _lang, ln, o = struct.unpack(">4sII", t[16:28])
                return t[o:o + ln].decode("utf-16-be") if rec else ""
    except Exception:  # noqa: BLE001
        pass
    return "CMYK"


def condition_of(label):
    for key, cond in CONDITIONS:
        if label.startswith(key):
            return cond
    return "Custom"


# ─── TIFF CMJN (écrit par l'export TIFF de GIMP, sans compression) ───────

def read_tiff_cmyk(path):
    """→ (largeur, hauteur, octets CMJN 8 bits entrelacés, profil ICC ou b"")"""
    d = open(path, "rb").read()
    bo = "<" if d[:2] == b"II" else ">"
    if struct.unpack(bo + "H", d[2:4])[0] != 42:
        raise PdfError("TIFF classique attendu")
    ifd = struct.unpack(bo + "I", d[4:8])[0]
    n = struct.unpack(bo + "H", d[ifd:ifd + 2])[0]
    tags = {}
    sizes = {1: ("B", 1), 2: ("B", 1), 3: ("H", 2), 4: ("I", 4), 7: ("B", 1), 16: ("Q", 8)}
    for i in range(n):
        e = d[ifd + 2 + 12 * i:ifd + 14 + 12 * i]
        tag, typ, cnt = struct.unpack(bo + "HHI", e[:8])
        if typ not in sizes:
            continue
        fmt, sz = sizes[typ]
        if sz * cnt <= 4:
            raw = e[8:8 + sz * cnt]
        else:
            off = struct.unpack(bo + "I", e[8:12])[0]
            raw = d[off:off + sz * cnt]
        tags[tag] = raw if typ in (1, 2, 7) else list(struct.unpack(bo + fmt * cnt, raw))
    w, h = tags[256][0], tags[257][0]
    spp = tags.get(277, [1])[0]
    if tags.get(259, [1])[0] != 1 or tags.get(262, [0])[0] != 5 or tags.get(258, [8])[0] != 8:
        raise PdfError("TIFF CMJN 8 bits non compressé attendu")
    data = b"".join(d[o:o + c] for o, c in zip(tags[273], tags[279]))
    if spp > 4:
        out = bytearray(w * h * 4)
        for c in range(4):
            out[c::4] = data[c::spp]
        data = bytes(out)
    return w, h, data, bytes(tags.get(34675, b""))


# ─── écriture PDF ────────────────────────────────────────────────────────

class Out:
    def __init__(self):
        self.objs = {}
        self.next = 1

    def reserve(self):
        n = self.next
        self.next += 1
        return Ref(n)

    def put(self, ref, value, stream=None):
        self.objs[ref[0]] = (value, stream)
        return ref

    def add(self, value, stream=None):
        return self.put(self.reserve(), value, stream)

    def write(self, path, version, root, info, doc_id):
        out = bytearray(b"%%PDF-%s\n%%\xe2\xe3\xcf\xd3\n" % version.encode())
        offs = {}
        for num in sorted(self.objs):
            value, stream = self.objs[num]
            offs[num] = len(out)
            if stream is None:
                out += b"%d 0 obj\n%s\nendobj\n" % (num, ser(value))
            else:
                value = dict(value)
                value["Length"] = len(stream)
                out += b"%d 0 obj\n%s\nstream\n%s\nendstream\nendobj\n" % (num, ser(value), stream)
        xref = len(out)
        size = max(offs) + 1
        out += b"xref\n0 %d\n0000000000 65535 f \n" % size
        for num in range(1, size):
            out += (b"%010d 00000 n \n" % offs[num]) if num in offs else b"0000000000 65535 f \n"
        idh = Raw(b"<" + doc_id.encode() + b">")
        trailer = {"Size": size, "Root": root, "Info": info, "ID": [idh, idh]}
        out += b"trailer\n%s\nstartxref\n%d\n%%%%EOF\n" % (ser(trailer), xref)
        tmp = path + ".part"
        with open(tmp, "wb") as f:
            f.write(bytes(out))
        os.replace(tmp, path)


def pdf_date(t):
    return "D:" + t.strftime("%Y%m%d%H%M%S") + "Z"


def xmp_packet(title, version, t, doc_id):
    iso = t.strftime("%Y-%m-%dT%H:%M:%SZ")
    esc = (title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    return ('<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
            '<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF '
            'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n'
            '<rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/" '
            'xmlns:xmp="http://ns.adobe.com/xap/1.0/" xmlns:pdf="http://ns.adobe.com/pdf/1.3/" '
            'xmlns:xmpMM="http://ns.adobe.com/xap/1.0/mm/" '
            'xmlns:pdfxid="http://www.npes.org/pdfx/ns/id/" '
            'xmlns:pdfx="http://ns.adobe.com/pdfx/1.3/">\n'
            '<dc:format>application/pdf</dc:format>\n'
            '<dc:title><rdf:Alt><rdf:li xml:lang="x-default">%s</rdf:li></rdf:Alt></dc:title>\n'
            '<xmp:CreateDate>%s</xmp:CreateDate><xmp:ModifyDate>%s</xmp:ModifyDate>'
            '<xmp:MetadataDate>%s</xmp:MetadataDate><xmp:CreatorTool>ChopGimp</xmp:CreatorTool>\n'
            '<pdf:Producer>ChopGimp</pdf:Producer><pdf:Trapped>False</pdf:Trapped>\n'
            '<xmpMM:DocumentID>uuid:%s</xmpMM:DocumentID>'
            '<xmpMM:InstanceID>uuid:%s</xmpMM:InstanceID>'
            '<xmpMM:RenditionClass>default</xmpMM:RenditionClass><xmpMM:VersionID>1</xmpMM:VersionID>\n'
            '<pdfxid:GTS_PDFXVersion>%s</pdfxid:GTS_PDFXVersion>'
            '<pdfx:GTS_PDFXVersion>%s</pdfx:GTS_PDFXVersion>\n'
            '</rdf:Description></rdf:RDF></x:xmpmeta>\n<?xpacket end="w"?>'
            % (esc, iso, iso, iso, doc_id, uuid.uuid4(), version, version)).encode("utf-8")


class Doc:
    """Un PDF/X en cours : intention de sortie, pages, métadonnées."""

    def __init__(self, x4, icc, title):
        self.x4 = x4
        self.out = Out()
        self.pages_ref = self.out.reserve()
        self.kids = []
        self.title = title
        label = icc_description(icc)
        icc_ref = self.out.add({"N": 4, "Filter": Name("FlateDecode")}, zlib.compress(icc, 9))
        self.intent = {"Type": Name("OutputIntent"), "S": Name("GTS_PDFX"),
                       "OutputConditionIdentifier": condition_of(label),
                       "OutputCondition": label, "RegistryName": "http://www.color.org",
                       "Info": label, "DestOutputProfile": icc_ref}
        # couleur de repérage des traits de coupe : 100 % de chaque encre
        fn = {"FunctionType": 2, "Domain": [0, 1], "C0": [0, 0, 0, 0], "C1": [1, 1, 1, 1], "N": 1}
        self.reg_cs = self.out.add([Name("Separation"), Name("All"), Name("DeviceCMYK"), fn])

    def marks_ops(self, trim, bleed_pt):
        """Traits de coupe autour de la boîte de coupe (x0, y0, x1, y1)."""
        x0, y0, x1, y1 = trim
        off = max(bleed_pt, 3 * MM)
        ln = 5 * MM
        ops = ["q /CSreg CS 1 SCN 0.25 w"]
        for x in (x0, x1):
            for y, sy in ((y0, -1), (y1, 1)):
                sx = -1 if x == x0 else 1
                ops.append("%.3f %.3f m %.3f %.3f l S" % (x + sx * off, y, x + sx * (off + ln), y))
                ops.append("%.3f %.3f m %.3f %.3f l S" % (x, y + sy * off, x, y + sy * (off + ln)))
        ops.append("Q")
        return "\n".join(ops).encode()

    def geometry(self, w_pt, h_pt, bleed_pt, marks):
        m = (max(bleed_pt, 3 * MM) + 5 * MM + 2 * MM) if marks else bleed_pt
        media = [0, 0, w_pt + 2 * m, h_pt + 2 * m]
        trim = (m, m, m + w_pt, m + h_pt)
        bleed = [m - bleed_pt, m - bleed_pt, m + w_pt + bleed_pt, m + h_pt + bleed_pt]
        return m, media, trim, bleed

    def add_page(self, media, trim, bleed, resources, contents, group=None):
        page = {"Type": Name("Page"), "Parent": self.pages_ref,
                "MediaBox": [float(v) for v in media],
                "BleedBox": [float(v) for v in bleed],
                "TrimBox": [float(v) for v in trim],
                "Resources": resources, "Contents": contents}
        if group is not None:
            page["Group"] = group
        self.kids.append(self.out.add(page))

    def add_raster_page(self, w_px, h_px, cmyk, w_pt, h_pt, bleed_pt, marks):
        """Image CMJN couvrant la boîte de fond perdu."""
        m, media, trim, bleed = self.geometry(w_pt, h_pt, bleed_pt, marks)
        img = self.out.add({"Type": Name("XObject"), "Subtype": Name("Image"),
                            "Width": w_px, "Height": h_px, "ColorSpace": Name("DeviceCMYK"),
                            "BitsPerComponent": 8, "Filter": Name("FlateDecode")},
                           zlib.compress(cmyk, 6))
        bw, bh = bleed[2] - bleed[0], bleed[3] - bleed[1]
        ops = b"q %.4f 0 0 %.4f %.4f %.4f cm /Im0 Do Q\n" % (bw, bh, bleed[0], bleed[1])
        if marks:
            ops += self.marks_ops(trim, bleed_pt)
        contents = self.out.add({"Filter": Name("FlateDecode")}, zlib.compress(ops))
        self.add_page(media, trim, bleed, {"XObject": {"Im0": img},
                                           "ColorSpace": {"CSreg": self.reg_cs}}, contents)

    def save(self, path):
        t = datetime.datetime.now(datetime.timezone.utc)
        doc_id = uuid.uuid4().hex
        o = self.out
        o.put(self.pages_ref, {"Type": Name("Pages"), "Kids": self.kids, "Count": len(self.kids)})
        version = "PDF/X-4" if self.x4 else "PDF/X-1:2001"
        info = {"Title": self.title, "Creator": "ChopGimp", "Producer": "ChopGimp",
                "CreationDate": pdf_date(t), "ModDate": pdf_date(t), "Trapped": Name("False"),
                "GTS_PDFXVersion": version}
        if not self.x4:
            info["GTS_PDFXConformance"] = "PDF/X-1a:2001"
        info_ref = o.add(info)
        catalog = {"Type": Name("Catalog"), "Pages": self.pages_ref,
                   "OutputIntents": [self.intent]}
        if self.x4:
            catalog["Metadata"] = o.add({"Type": Name("Metadata"), "Subtype": Name("XML")},
                                        xmp_packet(self.title, version, t, doc_id))
        root = o.add(catalog)
        o.write(path, "1.6" if self.x4 else "1.3", root, info_ref, doc_id)


# ─── PDF/X-4 vectoriel : reprise de l'export PDF de cairo ───────────────

NUM = rb"(-?(?:\d+\.?\d*|\.\d+))"
RGB_OP = re.compile(rb"(?<![\w.\-])" + NUM + rb"\s+" + NUM + rb"\s+" + NUM + rb"\s+(rg|RG)(?![\w])")


def import_vector_page(doc, src_bytes, convert, srgb_cs, bleed_pt, marks, w_pt, h_pt):
    """Ajoute à doc la page unique de src_bytes (cairo, PDF 1.4), couleurs
    unies converties par convert([(r, g, b)…]) → [(c, m, y, k)…]."""
    rd = Reader(src_bytes)
    _root, pages = rd.pages()
    if len(pages) != 1:
        raise PdfError("une page attendue")
    page_ref, page, inherited = pages[0]
    media = rd.resolve(inherited.get("MediaBox"))

    # les flux de contenu : la page, les formulaires et les motifs de pavage
    content_nums = set()
    for c in (page["Contents"] if isinstance(page.get("Contents"), list) else
              [page.get("Contents")]):
        if isinstance(c, Ref):
            content_nums.add(c[0])
    for num in rd.offsets:
        try:
            val, stream = rd.obj(num)
        except PdfError:
            continue
        if stream is not None and isinstance(val, dict) and (
                val.get("Subtype") == "Form" or val.get("PatternType") == 1):
            content_nums.add(num)

    decoded = {}
    colors = set()
    for num in content_nums:
        val, stream = rd.obj(num)
        data = decode(val, stream)
        if b"/DeviceRGB" in data:
            raise PdfError("espace /DeviceRGB dans un flux de contenu")
        decoded[num] = data
        for m in RGB_OP.finditer(data):
            colors.add(tuple(float(m.group(i)) for i in (1, 2, 3)))
    colors = sorted(colors)
    table = dict(zip(colors, convert(colors))) if colors else {}

    def sub(m):
        rgb = tuple(float(m.group(i)) for i in (1, 2, 3))
        c = table[rgb]
        op = b"k" if m.group(4) == b"rg" else b"K"
        return b"%s %s %s %s %s" % (tuple(ser(round(v, 4)) for v in c) + (op,))

    # renumérotation : objets de la source → objets du document
    mapping = {}

    def new_ref(num):
        if num not in mapping:
            mapping[num] = doc.out.reserve()
        return mapping[num]

    def remap(v):
        if isinstance(v, Ref):
            return new_ref(v[0])
        if isinstance(v, Name) and v == "DeviceRGB":
            return srgb_cs
        if isinstance(v, dict):
            return {k: remap(x) for k, x in v.items()}
        if isinstance(v, list):
            return [remap(x) for x in v]
        return v

    skip = {page_ref[0]} if isinstance(page_ref, Ref) else set()
    root_ref = rd.trailer.get("Root")
    if isinstance(root_ref, Ref):
        skip.add(root_ref[0])
    # l'arbre des pages et les infos de cairo sont remplacés
    for num in rd.offsets:
        val, _s = rd.obj(num)
        if isinstance(val, dict) and val.get("Type") in ("Pages", "Catalog"):
            skip.add(num)
    info = rd.trailer.get("Info")
    if isinstance(info, Ref):
        skip.add(info[0])

    res_raw = rd.resolve(inherited.get("Resources", {})) or {}
    cs_raw = rd.resolve(res_raw.get("ColorSpace")) if isinstance(res_raw, dict) else None
    resources = remap(res_raw)
    contents = page.get("Contents")
    contents = [remap(c) for c in (contents if isinstance(contents, list) else [contents])]
    group = remap(page.get("Group")) if page.get("Group") is not None else None

    # recopie des objets atteints (les autres sont abandonnés)
    done = set()
    while True:
        todo = [n for n in mapping if n not in done]
        if not todo:
            break
        for num in todo:
            done.add(num)
            if num in skip:
                continue
            val, stream = rd.obj(num)
            val = remap(val)
            if num in decoded:
                data = RGB_OP.sub(sub, decoded[num])
                val = dict(val)
                val.pop("DecodeParms", None)
                val["Filter"] = Name("FlateDecode")
                stream = zlib.compress(data, 6)
            doc.out.put(mapping[num], val, stream)

    # cadre : le contenu de cairo couvre la boîte de fond perdu
    _m, mediabox, trim, bleed = doc.geometry(w_pt, h_pt, bleed_pt, marks)
    pre = doc.out.add({}, b"q 1 0 0 1 %.4f %.4f cm\n" % (bleed[0], bleed[1]))
    post_ops = b"Q\n" + (doc.marks_ops(trim, bleed_pt) if marks else b"")
    post = doc.out.add({"Filter": Name("FlateDecode")}, zlib.compress(post_ops))
    res = dict(resources) if isinstance(resources, dict) else {}
    cs = remap(cs_raw) if isinstance(cs_raw, dict) else {}
    cs["CSreg"] = doc.reg_cs
    res["ColorSpace"] = cs
    doc.add_page(mediabox, trim, bleed, res, [pre] + contents + [post], group)
    return len(colors)
