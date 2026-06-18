import io, json, re, sys, os, urllib.request
from datetime import datetime, timedelta, timezone, date

# ====== CONFIGURA TU AUTO (cambia el dígito por el de TU patente) ======
MI_DIGITO = 6          # <-- pon aquí el último dígito de tu patente (0 a 9)
MI_TIPO   = "cat_old"  # cat_old = catalítico antiguo (tu caso)
# ======================================================================

TZ_CL = timezone(timedelta(hours=-4))
BASE = "https://airerm.mma.gob.cl/wp-content/uploads"
CAL_CAT = {1:[8,9],2:[0,1],3:[2,3],4:[4,5],5:[6,7]}
FERIADOS = {"2026-05-01","2026-05-21","2026-06-20","2026-06-29","2026-07-16","2026-08-15"}
DIA = {1:"lunes",2:"martes",3:"miércoles",4:"jueves",5:"viernes",6:"sábado",7:"domingo"}
MES = {1:"enero",2:"febrero",3:"marzo",4:"abril",5:"mayo",6:"junio",7:"julio",8:"agosto",9:"septiembre",10:"octubre",11:"noviembre",12:"diciembre"}

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

def parse_digitos(text):
    t = re.sub(r'\s*-\s*', '-', text)   # une "8 - 9" -> "8-9" por si viene espaciado
    return [list(map(int, g.split("-"))) for g in re.findall(r"(?<!\d)(\d(?:-\d){1,9})(?!\d)", t)]

def parse_condicion(text):
    # Detección por DÍGITOS (robusta al desorden/espaciado del PDF):
    # sin sello fuera del anillo => 4 normal / 6 preemergencia / 8 emergencia.
    # Las palabras solo se usan para la etiqueta cosmética en días sin episodio.
    grupos = parse_digitos(text)
    if not grupos:
        return None  # no se pudo leer la tabla -> desconocido
    no10 = [len(g) for g in grupos if len(g) != 10]  # excluye total interior (0-9)
    mx = max(no10) if no10 else 0
    if mx >= 8: return "emergencia"
    if mx >= 6: return "preemergencia"
    def cnt(k): return len(re.findall(r"(?<![0-9A-ZÁÉÍÓÚ])"+k+r"(?![0-9A-ZÁÉÍÓÚ])", text))
    cand = {"alerta":cnt("ALERTA"), "bueno":cnt("BUENO")+cnt("BUENA"), "regular":cnt("REGULAR")}
    best = max(cand, key=lambda x: cand[x])
    return best if cand[best] > 0 else "regular"

def parse_fecha(t):
    m = re.search(r"(LUNES|MARTES|MI[ÉE]RCOLES|JUEVES|VIERNES|S[ÁA]BADO|DOMINGO)\s+(\d{2})/(\d{2})/(\d{4})", t, re.I)
    return date(int(m.group(4)), int(m.group(3)), int(m.group(2))) if m else None

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

def en_temporada(d):
    return date(2026,5,1) <= d <= date(2026,8,31)

def construir_mensaje(estado, digit, tipo, target):
    iso = target.isoweekday(); ds = target.strftime("%Y-%m-%d")
    fecha_txt = f"{DIA[iso]} {target.day} de {MES[target.month]}"
    cond = estado.get("condicion","desconocido")
    if iso in (6,7):             return f"✅ {fecha_txt}: circulas (fin de semana)."
    if ds in FERIADOS:           return f"✅ {fecha_txt}: circulas (feriado)."
    if not en_temporada(target): return f"✅ {fecha_txt}: circulas (fuera de temporada)."
    if tipo == "cat_new":
        ex = f" Aire: {cond}, evita esfuerzo físico al aire libre." if cond in ("preemergencia","emergencia") else ""
        return f"✅ {fecha_txt}: circulas (catalítico moderno).{ex}"
    if tipo == "cat_old":
        if estado.get("catalitico_confiable") and estado.get("digitos_catalitico") and estado.get("fecha")==ds:
            restr = estado["digitos_catalitico"]
        else:
            restr = CAL_CAT.get(iso, [])
        rtxt = "-".join(str(x) for x in restr)
        if digit in restr:
            emer = " (emergencia)" if cond=="emergencia" else ""
            return f"🚫 {fecha_txt}: NO circulas hoy{emer}. Restringe {rtxt}; el tuyo es {digit}."
        emer = " ¡Hay EMERGENCIA ambiental!" if cond=="emergencia" else ""
        return f"✅ {fecha_txt}: circulas hoy (restringe {rtxt}, no el {digit}). Aire: {cond}.{emer}"
    return f"⚠️ {fecha_txt}: revisa la app. Aire: {cond}."

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
                "digitos_catalitico": cat, "catalitico_confiable": bool(cat_ok),
                "digitos_detectados": parse_digitos(txt), "pdf_url": url,
                "actualizado_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "ok": cond is not None,
            }
        except Exception as e:
            last_err = str(e); continue
    return {"fecha": target_date.strftime("%Y-%m-%d"), "condicion":"desconocido",
            "digitos_catalitico":None,"catalitico_confiable":False,"digitos_detectados":[],
            "pdf_url":None,"actualizado_utc":datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ok":False,"error":last_err}

if __name__ == "__main__":
    hoy = datetime.now(TZ_CL).date()
    estado = build_estado(hoy)
    mensaje = construir_mensaje(estado, MI_DIGITO, MI_TIPO, hoy)
    estado["mensaje"] = mensaje
    os.makedirs("data", exist_ok=True)
    with open("data/estado.json", "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=2)
    with open("data/aviso.txt", "w", encoding="utf-8") as f:
        f.write(mensaje)
    print(mensaje)
