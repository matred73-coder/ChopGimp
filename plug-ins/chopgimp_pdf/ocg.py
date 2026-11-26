# -*- coding: utf-8 -*-
"""
ChopGimp 3.31.0 (lot 4b) — calques PDF (contenu optionnel, OCG) sans
dépendance : lecture d'un PDF 1.4 écrit par cairo, réécriture en PDF 1.5.

cairo ne sait pas écrire d'OCG. L'export PDF de ChopGimp (file-pdf-export)
écrit donc un PDF intermédiaire où chaque calque est seul sur sa page, puis
appelle ce module avec la description des pages finales (JSON) :

  {"pages": [{"w": pt, "h": pt, "bg": [r, g, b] ou null,
              "layers": [nœud, …]}]}          (nœuds de bas en haut)
  nœud = {"id", "name", "visible", "page": n}             un calque
       | {"id", "name", "visible", "opacity", "mode",
          "children": [nœud, …]}                         un groupe

Chaque page intermédiaire devient un XObject de formulaire, posé dans la
page finale entre « /OC /ocN BDC » et « EMC » ; un groupe est un contenu
optionnel englobant (ses enfants sont masqués avec lui) et, s'il a une
opacité ou un mode de fusion, un groupe de transparence (/Group) peint avec
un état graphique (/ca, /CA, /BM). Un même calque (même « id ») a le même
OCG sur toutes les pages (plans de travail). L'arborescence des calques
(/Order), les calques masqués (/OFF) et l'ouverture du panneau Calques
(/PageMode /UseOC) sont décrits dans /OCProperties : Acrobat et Illustrator
les montrent comme calques.

Limites du lecteur (le PDF vient toujours de cairo) : table xref classique
(cairo n'écrit des flux d'objets qu'à partir de PDF 1.5 : l'export
intermédiaire est restreint à 1.4), filtres FlateDecode ou aucun.
"""
import json
import re
import zlib

WS = b" \t\r\n\f\x00"
DELIM = b"()<>[]{}/%"


class PdfError(Exception):
    pass


class Name(str):
    """Nom PDF, gardé tel qu'il est écrit (sans la barre)."""


class Ref(tuple):
    def __new__(cls, num, gen=0):
        return tuple.__new__(cls, (num, gen))


class Raw(bytes):
    """Chaîne PDF, gardée telle qu'elle est écrite (délimiteurs compris)."""


# ─── lecture ─────────────────────────────────────────────────────────────

class Lexer:
    def __init__(self, data, pos=0):
        self.d = data
        self.p = pos

    def skip(self):
        d, n = self.d, len(self.d)
        while self.p < n:
            c = d[self.p:self.p + 1]
            if c in WS and c:
                self.p += 1
            elif c == b"%":
                while self.p < n and d[self.p:self.p + 1] not in b"\r\n":
                    self.p += 1
            else:
                break

    def token(self):
        self.skip()
        d, p = self.d, self.p
        if p >= len(d):
            return None
        c = d[p:p + 1]
        if d[p:p + 2] in (b"<<", b">>"):
            self.p += 2
            return d[p:p + 2]
        if c in b"[]{}":
            self.p += 1
            return c
        if c == b"/":
            q = p + 1
            while q < len(d) and d[q:q + 1] not in WS and d[q:q + 1] not in DELIM:
                q += 1
            self.p = q
            return Name(d[p + 1:q].decode("latin-1"))
        if c == b"(":
            depth, q = 0, p
            while q < len(d):
                ch = d[q:q + 1]
                if ch == b"\\":
                    q += 2
                    continue
                if ch == b"(":
                    depth += 1
                elif ch == b")":
                    depth -= 1
                    if depth == 0:
                        break
                q += 1
            self.p = q + 1
            return Raw(d[p:q + 1])
        if c == b"<":
            q = d.index(b">", p)
            self.p = q + 1
            return Raw(d[p:q + 1])
        q = p
        while q < len(d) and d[q:q + 1] not in WS and d[q:q + 1] not in DELIM:
            q += 1
        self.p = q
        word = d[p:q]
        if not word:
            raise PdfError("caractère inattendu à %d" % p)
        return word

    def value(self, tok=None):
        tok = self.token() if tok is None else tok
        if tok == b"<<":
            out = {}
            while True:
                k = self.token()
                if k == b">>":
                    return out
                if not isinstance(k, Name):
                    raise PdfError("clé de dictionnaire attendue à %d" % self.p)
                out[k] = self.value()
        if tok == b"[":
            out = []
            while True:
                t = self.token()
                if t == b"]":
                    return out
                out.append(self.value(t))
        if isinstance(tok, (Name, Raw)):
            return tok
        if tok in (b"true", b"false"):
            return tok == b"true"
        if tok == b"null":
            return None
        if re.match(rb"^[+-]?(\d+\.?\d*|\.\d+)$", tok or b""):
            num = float(tok) if b"." in tok else int(tok)
            # « n g R » : une référence
            if isinstance(num, int):
                save = self.p
                t2 = self.token()
                if isinstance(t2, bytes) and not isinstance(t2, (Name, Raw)) and t2.isdigit():
                    t3 = self.token()
                    if t3 == b"R":
                        return Ref(num, int(t2))
                self.p = save
            return num
        raise PdfError("jeton inattendu %r" % tok)


def ser(v):
    if isinstance(v, bool):
        return b"true" if v else b"false"
    if v is None:
        return b"null"
    if isinstance(v, Ref):
        return b"%d %d R" % v
    if isinstance(v, Name):
        return b"/" + v.encode("latin-1")
    if isinstance(v, Raw):
        return bytes(v)
    if isinstance(v, int):
        return b"%d" % v
    if isinstance(v, float):
        s = ("%.6f" % v).rstrip("0").rstrip(".")
        return (s if s not in ("", "-0") else "0").encode()
    if isinstance(v, dict):
        return b"<<" + b" ".join(ser(Name(k)) + b" " + ser(x) for k, x in v.items()) + b">>"
    if isinstance(v, (list, tuple)):
        return b"[" + b" ".join(ser(x) for x in v) + b"]"
    if isinstance(v, str):
        return text_string(v)
    raise PdfError("valeur non sérialisable %r" % (v,))


def text_string(s):
    """Chaîne de texte PDF : PDFDocEncoding si ASCII, sinon UTF-16BE."""
    try:
        b = s.encode("ascii")
    except UnicodeEncodeError:
        b = b"\xfe\xff" + s.encode("utf-16-be")
    out = bytearray(b"(")
    for ch in b:
        if ch in b"()\\":
            out += b"\\"
        if ch in (10, 13):
            out += b"\\n" if ch == 10 else b"\\r"
            continue
        out.append(ch)
    out += b")"
    return Raw(bytes(out))


class Reader:
    def __init__(self, data):
        self.data = data
        self.offsets = {}
        self.trailer = {}
        self._parse_xref()
        order = sorted(self.offsets.items(), key=lambda kv: kv[1])
        self.ends = {}
        xref_at = self.xref_at
        for i, (num, off) in enumerate(order):
            nxt = order[i + 1][1] if i + 1 < len(order) else xref_at
            if nxt <= off:
                nxt = xref_at
            self.ends[num] = nxt
        self.cache = {}

    def _parse_xref(self):
        d = self.data
        i = d.rfind(b"startxref")
        if i < 0:
            raise PdfError("startxref absent")
        pos = int(d[i + 9:].split()[0])
        self.xref_at = pos
        while pos is not None:
            if d[pos:pos + 4] != b"xref":
                raise PdfError("table xref classique attendue (PDF 1.4 de cairo)")
            lx = Lexer(d, pos + 4)
            while True:
                lx.skip()
                if d[lx.p:lx.p + 7] == b"trailer":
                    lx.p += 7
                    break
                start = int(lx.token())
                count = int(lx.token())
                lx.skip()
                for k in range(count):
                    line = d[lx.p:lx.p + 20]
                    lx.p += 20
                    off, _gen, kind = line.split()[:3]
                    if kind == b"n" and (start + k) not in self.offsets:
                        self.offsets[start + k] = int(off)
            tr = lx.value()
            for k, v in tr.items():
                self.trailer.setdefault(k, v)
            prev = tr.get("Prev")
            pos = int(prev) if prev is not None else None

    def obj(self, num):
        """(valeur, données du flux ou None)"""
        if num in self.cache:
            return self.cache[num]
        off = self.offsets.get(num)
        if off is None:
            raise PdfError("objet %d absent" % num)
        lx = Lexer(self.data, off)
        n = lx.token()
        lx.token()                      # génération
        kw = lx.token()
        if kw != b"obj" or int(n) != num:
            raise PdfError("objet %d illisible" % num)
        val = lx.value()
        stream = None
        lx.skip()
        if self.data[lx.p:lx.p + 6] == b"stream":
            p = lx.p + 6
            if self.data[p:p + 2] == b"\r\n":
                p += 2
            elif self.data[p:p + 1] in (b"\n", b"\r"):
                p += 1
            length = self.resolve(val.get("Length"))
            if not isinstance(length, int):
                end = self.data.index(b"endstream", p)
                length = end - p
                while length > 0 and self.data[p + length - 1:p + length] in (b"\n", b"\r"):
                    length -= 1
            stream = self.data[p:p + length]
        self.cache[num] = (val, stream)
        return val, stream

    def resolve(self, v):
        while isinstance(v, Ref):
            v = self.obj(v[0])[0]
        return v

    def raw(self, num):
        return self.data[self.offsets[num]:self.ends[num]]

    def pages(self):
        root = self.resolve(self.trailer["Root"])
        out = []

        def walk(node_ref, inherited):
            node = self.resolve(node_ref)
            inh = dict(inherited)
            for k in ("Resources", "MediaBox"):
                if k in node:
                    inh[k] = node[k]
            if node.get("Type") == "Pages":
                for kid in node.get("Kids", []):
                    walk(kid, inh)
            else:
                out.append((node_ref, node, inh))

        walk(root["Pages"], {})
        return root, out


def decode(dct, data):
    f = dct.get("Filter")
    if isinstance(f, list):
        f = f[0] if len(f) == 1 else f
    if f is None:
        return data
    if f == "FlateDecode":
        return zlib.decompress(data)
    raise PdfError("filtre non pris en charge : %r" % (f,))


# ─── écriture ────────────────────────────────────────────────────────────

BLEND = {"Normal", "Multiply", "Screen", "Overlay", "Darken", "Lighten", "ColorDodge",
         "ColorBurn", "HardLight", "SoftLight", "Difference", "Exclusion", "Hue",
         "Saturation", "Color", "Luminosity"}


class Writer:
    def __init__(self, first_free):
        self.next = first_free
        self.objs = {}

    def add(self, value, stream=None, num=None):
        if num is None:
            num = self.next
            self.next += 1
        self.objs[num] = (value, stream)
        return Ref(num)

    def reserve(self):
        num = self.next
        self.next += 1
        return Ref(num)

    def body(self, num):
        value, stream = self.objs[num]
        if stream is None:
            return b"%d 0 obj\n%s\nendobj\n" % (num, ser(value))
        value = dict(value)
        value["Length"] = len(stream)
        return b"%d 0 obj\n%s\nstream\n%s\nendstream\nendobj\n" % (num, ser(value), stream)


def make_layers(src_bytes, spec):
    """PDF intermédiaire (bytes) + description → PDF à calques (bytes)."""
    if isinstance(spec, str):
        spec = json.loads(spec)
    rd = Reader(src_bytes)
    root, pages = rd.pages()
    page_nums = {r[0] for r, _n, _i in pages if isinstance(r, Ref)}
    drop = set(page_nums)
    # le catalogue et l'arbre des pages sont remplacés
    root_ref = rd.trailer["Root"]
    drop.add(root_ref[0])

    def drop_pages(ref):
        if isinstance(ref, Ref):
            drop.add(ref[0])
            node = rd.resolve(ref)
            for kid in node.get("Kids", []) if node.get("Type") == "Pages" else []:
                drop_pages(kid)

    drop_pages(root["Pages"])

    wr = Writer(max(rd.offsets) + 1)

    # pages intermédiaires → XObjects de formulaire
    forms = []
    for _ref, node, inh in pages:
        box = rd.resolve(inh.get("MediaBox", [0, 0, 612, 792]))
        res = inh.get("Resources", {})
        contents = node.get("Contents")
        if isinstance(contents, Ref):
            contents = rd.resolve(contents) if isinstance(rd.resolve(contents), list) else [contents]
        contents = contents or []
        form = {"Type": Name("XObject"), "Subtype": Name("Form"),
                "BBox": [rd.resolve(x) for x in box], "Resources": res}
        if len(contents) == 1 and isinstance(contents[0], Ref):
            cdict, cdata = rd.obj(contents[0][0])
            if cdict.get("Filter") is not None:
                form["Filter"] = cdict["Filter"]
            if cdict.get("DecodeParms") is not None:
                form["DecodeParms"] = cdict["DecodeParms"]
            data = cdata or b""
            drop.add(contents[0][0])
        else:
            parts = []
            for c in contents:
                cdict, cdata = rd.obj(c[0])
                parts.append(decode(cdict, cdata or b""))
                drop.add(c[0])
            data = zlib.compress(b"\n".join(parts))
            form["Filter"] = Name("FlateDecode")
        forms.append(wr.add(form, data))

    # OCG : un par calque (« id »), partagé entre les pages
    ocgs = {}
    ocg_order = []
    hidden = []

    def ocg_for(node):
        key = str(node.get("id", node.get("name", "")))
        if key not in ocgs:
            ocgs[key] = wr.add({"Type": Name("OCG"), "Name": str(node.get("name") or "Calque")})
            if not node.get("visible", True):
                hidden.append(ocgs[key])
        return ocgs[key]

    def order_of(nodes):
        out = []
        for nd in reversed(nodes):                # le panneau : de haut en bas
            ref = ocg_for(nd)
            if ref in ocg_order:
                continue
            ocg_order.append(ref)
            out.append(ref)
            if nd.get("children"):
                sub = order_of(nd["children"])
                if sub:
                    out.append(sub)
        return out

    order = []
    for pg in spec["pages"]:
        order += order_of(pg.get("layers", []))

    class Res:
        def __init__(self):
            self.x, self.p, self.g = {}, {}, {}

        def dict(self):
            d = {}
            if self.x:
                d["XObject"] = self.x
            if self.p:
                d["Properties"] = self.p
            if self.g:
                d["ExtGState"] = self.g
            return d

    def ops_of(nodes, res):
        out = []
        for nd in nodes:
            oc = ocg_for(nd)
            tag = "oc%d" % oc[0]
            res.p[tag] = oc
            out.append(b"/OC /%s BDC" % tag.encode())
            if nd.get("children") is not None:
                opacity = float(nd.get("opacity", 1.0))
                mode = str(nd.get("mode", "Normal"))
                if mode not in BLEND:
                    mode = "Normal"
                inner = Res()
                body = b"\n".join(ops_of(nd["children"], inner))
                if opacity < 1.0 or mode != "Normal":
                    pg_w, pg_h = cur_size
                    grp = wr.add({"Type": Name("XObject"), "Subtype": Name("Form"),
                                  "BBox": [0, 0, pg_w, pg_h], "Resources": inner.dict(),
                                  "Group": {"Type": Name("Group"), "S": Name("Transparency")},
                                  "Filter": Name("FlateDecode")}, zlib.compress(body))
                    gs = wr.add({"Type": Name("ExtGState"), "ca": opacity, "CA": opacity,
                                 "BM": Name(mode)})
                    gname, xname = "gs%d" % gs[0], "fx%d" % grp[0]
                    res.g[gname] = gs
                    res.x[xname] = grp
                    out.append(b"q /%s gs /%s Do Q" % (gname.encode(), xname.encode()))
                else:
                    res.x.update(inner.x)
                    res.p.update(inner.p)
                    res.g.update(inner.g)
                    out.append(body)
            else:
                k = int(nd["page"])
                if not 0 <= k < len(forms):
                    raise PdfError("page %d absente du PDF intermédiaire" % k)
                xname = "fx%d" % forms[k][0]
                res.x[xname] = forms[k]
                out.append(b"q /%s Do Q" % xname.encode())
            out.append(b"EMC")
        return out

    pages_ref = wr.reserve()
    kids = []
    for pg in spec["pages"]:
        w, h = float(pg["w"]), float(pg["h"])
        cur_size = (w, h)
        res = Res()
        ops = [b"q"]
        bg = pg.get("bg")
        if bg:
            ops.append(b"%s %s %s rg 0 0 %s %s re f" % tuple(ser(float(c)) for c in
                                                             (bg[0], bg[1], bg[2], w, h)))
        ops += ops_of(pg.get("layers", []), res)
        ops.append(b"Q")
        content = wr.add({"Filter": Name("FlateDecode")}, zlib.compress(b"\n".join(ops)))
        kids.append(wr.add({"Type": Name("Page"), "Parent": pages_ref, "MediaBox": [0, 0, w, h],
                            "Resources": res.dict(), "Contents": content,
                            "Group": {"Type": Name("Group"), "S": Name("Transparency"),
                                      "CS": Name("DeviceRGB")}}))
    wr.add({"Type": Name("Pages"), "Kids": kids, "Count": len(kids)}, num=pages_ref[0])

    all_ocgs = list(ocgs.values())
    catalog = wr.add({"Type": Name("Catalog"), "Pages": pages_ref, "PageMode": Name("UseOC"),
                      "OCProperties": {"OCGs": all_ocgs,
                                       "D": {"Name": "ChopGimp", "BaseState": Name("ON"),
                                             "Order": order, "OFF": hidden,
                                             "ListMode": Name("AllPages")}}})

    # sortie : objets gardés tels quels, puis les nouveaux
    out = bytearray(b"%PDF-1.5\n%\xe2\xe3\xcf\xd3\n")
    offsets = {}
    for num in sorted(rd.offsets):
        if num in drop:
            continue
        offsets[num] = len(out)
        raw = rd.raw(num)
        out += raw if raw.endswith(b"\n") else raw + b"\n"
    for num in sorted(wr.objs):
        offsets[num] = len(out)
        out += wr.body(num)
    size = max(offsets) + 1
    xref = len(out)
    out += b"xref\n0 %d\n" % size
    out += b"0000000000 65535 f \n"
    for num in range(1, size):
        if num in offsets:
            out += b"%010d 00000 n \n" % offsets[num]
        else:
            out += b"0000000000 00001 f \n"
    trailer = {"Size": size, "Root": catalog}
    if isinstance(rd.trailer.get("Info"), Ref) and rd.trailer["Info"][0] not in drop:
        trailer["Info"] = rd.trailer["Info"]
    out += b"trailer\n%s\nstartxref\n%d\n%%%%EOF\n" % (ser(trailer), xref)
    return bytes(out)


def make_layers_file(src_path, dst_path, spec):
    with open(src_path, "rb") as f:
        data = make_layers(f.read(), spec)
    with open(dst_path, "wb") as f:
        f.write(data)
    return True
