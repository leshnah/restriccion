import io, json, re, sys, os, urllib.request
from datetime import datetime, timedelta, timezone, date

TZ_CL = timezone(timedelta(hours=-4))
BASE = "https://airerm.mma.gob.cl/wp-content/uploads"
SEV = {"emergencia":5,"preemergencia":4,"alerta":3,"regular":2,"bueno":1}
CAL_CAT = {1:[8,9],2:[0,1],3:[2,3],4:[4,5],5:[6,7]}

def candidate_urls(d):
    prev = d - timedelta(days=1)
    name = f"Declaracion-GEC-{d:%Y-%m-%d}.pdf"
    urls, seen = [], set()
    for u in (f"{BASE}/{prev:%Y/%m}/{name}", f"{BASE}/{d:%Y/%m}/{name}"):
        if u not in seen:
            seen.add(u); urls.append(u)
    return urls

def fetch_pdf_text(url):
    req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0 (restriccion-app)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        if r.status != 200:
            raise IOError(f"HTTP {r.status}")
        data = r.read()
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    return "\n".join((p.extract_text() or "") for p in reader.pages)

def norm(s):
    s = s.lower(); return "bueno" if s == "buena" else s

def parse_condicion(t):
    m = re.search(r"prevista:\s*\n?\s*(EMERGENCIA|PREEMERGENCIA|ALERTA|REGULAR|BUEN[OA])", t, re.I)
    if m: return norm(m.group(1))
    m = re.search(r"M\s*E\s*D\s*I\s*D\s*A\s*S\s*\n?\s*(EMERGENCIA|PREEMERGENCIA|ALERTA|REGULAR|BUEN[OA])", t, re.I)
    if m: return norm(m.group(1))
    best, bs = None, 0
    for k in SEV:
        if re.search(r"\b"+k+r"\b", t, re.I) and SEV[k] > bs:
            bs = SEV[k]; best = k
    return best

def parse_fecha(t):
    m = re.search(r"(LUNES|MARTES|MI[ÉE]RCOLES|JUEVES|VIERNES|S[ÁA]BADO|DOMINGO)\s+(\d{2})/(\d{2})/(\d{4})", t, re.I)
    return date(int(m.group(4)), int(m.group(3)), int(m.group(2))) if m else None

def parse_digitos(t):
    return [list(map(int, g.split("-"))) for g in re.findall(r"\b(\d(?:-\d){1,9})\b", t)]

def catalitico_digits(text, target, condicion):
    iso = target.isoweekday()
    pair = CAL_CAT.get(iso)
    if pair is None:
        return None, False
    want = 4 if condicion == "emergencia" else 2
    cands = [g for g in parse_digitos(text) if len(g) == want and all(d in g for d in pair)]
    if not cands:
        return None, False
    chosen = sorted(cands[0])
    confiable = True if condicion == "emergencia" else (chosen == sorted(pair))
    return chosen, confiable

def build_estado(target_date):
    last_err = None
    for url in candidate_urls(target_date):
        try:
            txt = fetch_pdf_text(url)
            cond = parse_condicion(txt)
            fecha = parse_fecha(txt) or target_date
            cat, cat_ok = catalitico_digits(txt, fecha, cond or "")
            return {
                "fecha": fecha.strftime("%Y-%m-%d"),
                "condicion": cond or "desconocido",
                "digitos_catalitico": cat,
                "catalitico_confiable": bool(cat_ok),
                "digitos_detectados": parse_digitos(txt),
                "pdf_url": url,
                "actualizado_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "ok": cond is not None,
            }
        except Exception as e:
            last_err = str(e); continue
    return {
        "fecha": target_date.strftime("%Y-%m-%d"), "condicion": "desconocido",
        "digitos_catalitico": None, "catalitico_confiable": False,
        "digitos_detectados": [], "pdf_url": None,
        "actualizado_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ok": False, "error": last_err,
    }

if __name__ == "__main__":
    hoy = datetime.now(TZ_CL).date()
    estado = build_estado(hoy)
    os.makedirs("data", exist_ok=True)
    with open("data/estado.json", "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=2)
    print(json.dumps(estado, ensure_ascii=False))
