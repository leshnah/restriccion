#!/usr/bin/env python3
"""
Lee la Declaración GEC diaria del MMA (airerm.mma.gob.cl) y escribe data/estado.json
con la condición de calidad del aire (bueno/regular/alerta/preemergencia/emergencia)
para HOY en la Región Metropolitana. Pensado para correr en GitHub Actions.
"""
import io, json, re, sys, urllib.request
from datetime import datetime, timedelta, timezone

TZ_CL = timezone(timedelta(hours=-4))   # Chile continental (horario invierno -4 / verano -3; en temporada GEC es invierno)
BASE = "https://airerm.mma.gob.cl/wp-content/uploads"
MESES = {1:"enero",2:"febrero",3:"marzo",4:"abril",5:"mayo",6:"junio",
         7:"julio",8:"agosto",9:"septiembre",10:"octubre",11:"noviembre",12:"diciembre"}
SEV = {"emergencia":5,"preemergencia":4,"alerta":3,"regular":2,"bueno":1}

def candidate_urls(d):
    """La declaración de la fecha d se publica la tarde anterior; la carpeta /AAAA/MM/
    corresponde al mes de (d-1). Probamos esa y, por si acaso, la del propio mes de d."""
    prev = d - timedelta(days=1)
    name = f"Declaracion-GEC-{d:%Y-%m-%d}.pdf"
    urls = [f"{BASE}/{prev:%Y/%m}/{name}", f"{BASE}/{d:%Y/%m}/{name}"]
    # dedup conservando orden
    seen=set(); return [u for u in urls if not (u in seen or seen.add(u))]

def fetch_pdf_text(url):
    req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0 (restriccion-app)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        if r.status != 200: raise IOError(f"HTTP {r.status}")
        data = r.read()
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    return "\n".join((p.extract_text() or "") for p in reader.pages)

def norm(s): 
    s=s.lower(); return "bueno" if s=="buena" else s

def parse_condicion(t):
    m = re.search(r"prevista:\s*\n?\s*(EMERGENCIA|PREEMERGENCIA|ALERTA|REGULAR|BUEN[OA])", t, re.I)
    if m: return norm(m.group(1))
    m = re.search(r"M\s*E\s*D\s*I\s*D\s*A\s*S\s*\n?\s*(EMERGENCIA|PREEMERGENCIA|ALERTA|REGULAR|BUEN[OA])", t, re.I)
    if m: return norm(m.group(1))
    best=None; bs=0
    for k in SEV:
        if re.search(r"\b"+k+r"\b", t, re.I) and SEV[k]>bs: bs=SEV[k]; best=k
    return best

def parse_fecha(t):
    m = re.search(r"(LUNES|MARTES|MI[ÉE]RCOLES|JUEVES|VIERNES|S[ÁA]BADO|DOMINGO)\s+(\d{2})/(\d{2})/(\d{4})", t, re.I)
    return f"{m.group(4)}-{m.group(3)}-{m.group(2)}" if m else None

def parse_digitos(t):
    return [list(map(int,g.split("-"))) for g in re.findall(r"\b(\d(?:-\d){1,9})\b", t)]

def build_estado(target_date):
    last_err=None
    for url in candidate_urls(target_date):
        try:
            txt = fetch_pdf_text(url)
            cond = parse_condicion(txt)
            fecha = parse_fecha(txt) or f"{target_date:%Y-%m-%d}"
            return {
                "fecha": fecha,
                "condicion": cond or "desconocido",
                "digitos_detectados": parse_digitos(txt),
                "pdf_url": url,
                "actualizado_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "ok": cond is not None,
            }
        except Exception as e:
            last_err=str(e); continue
    return {"fecha": f"{target_date:%Y-%m-%d}", "condicion":"desconocido",
            "digitos_detectados":[], "pdf_url":None,
            "actualizado_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ok": False, "error": last_err}

# ---- prueba offline del parser con el texto REAL del 25-05-2026 ----
if __name__ == "__main__" and "--selftest" in sys.argv:
    sample = open("sample_real.txt", encoding="utf-8").read()
    print("condicion:", parse_condicion(sample))
    print("fecha:", parse_fecha(sample))
    print("digitos:", parse_digitos(sample))
    print("url ejemplo 25-may:", candidate_urls(datetime(2026,5,25).date()))
    print("url ejemplo 01-jun:", candidate_urls(datetime(2026,6,1).date()))
    sys.exit(0)

if __name__ == "__main__":
    hoy = datetime.now(TZ_CL).date()
    estado = build_estado(hoy)
    import os; os.makedirs("data", exist_ok=True)
    with open("data/estado.json","w",encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=2)
    print(json.dumps(estado, ensure_ascii=False))
    sys.exit(0 if estado.get("ok") else 0)  # nunca falla el build; deja estado "desconocido"
