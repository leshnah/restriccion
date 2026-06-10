# ¿Circulo hoy? — Restricción vehicular Santiago

PWA que indica si tu auto tiene restricción vehicular hoy en la Región Metropolitana,
y se actualiza **sola cada día** con la condición de calidad del aire (bueno / regular /
alerta / preemergencia / emergencia) publicada por el Ministerio del Medio Ambiente.

## Cómo funciona

- `index.html` — la app. Calcula la restricción con el calendario oficial 2026 y lee
  `data/estado.json` para saber si hoy hay episodio crítico.
- `scripts/actualizar_estado.py` — descarga la Declaración GEC diaria (PDF) desde
  `airerm.mma.gob.cl`, detecta la condición del día y escribe `data/estado.json`.
- `.github/workflows/actualizar-estado.yml` — corre el script varias veces al día con
  GitHub Actions y hace commit del `estado.json` actualizado. Sin servidores.

```
índice ── lee ──► data/estado.json ◄── escribe ── GitHub Action (cron) ──► PDF del MMA
```

## Puesta en marcha (una sola vez)

1. Crea un repositorio en GitHub (público para que Pages y Actions sean gratis) y sube
   estos archivos respetando las carpetas.
2. **Settings → Pages**: en *Source* elige *Deploy from a branch*, rama `main`, carpeta `/root`.
   Tu app quedará en `https://TU_USUARIO.github.io/NOMBRE_REPO/`.
3. **Settings → Actions → General → Workflow permissions**: marca
   *Read and write permissions* (deja que la Action pueda commitear el `estado.json`).
4. Ve a la pestaña **Actions**, abre *Actualizar estado de calidad del aire* y pulsa
   *Run workflow* para la primera carga. Luego corre solo según el cron.
5. Abre la app en Safari (iPhone) → Compartir → **Agregar a inicio**. Queda como app.

## El cron

Está en UTC. En temporada GEC (mayo–agosto) Chile es UTC−4:

| cron (UTC) | hora Chile | para qué |
|---|---|---|
| `30 10 * * *` | ~06:30 | declaración del día, lista para la mañana |
| `0 16 * * *` | ~12:00 | refresco de respaldo |
| `30 1 * * *` | ~21:30 | tras publicarse la del día siguiente |

GitHub a veces atrasa los cron unos minutos; por eso hay tres.

## Qué es exacto y qué no

- **Días normales**: 100% determinístico con el calendario oficial 2026.
- **Episodios (preemergencia/emergencia)**: la condición se detecta automáticamente del
  PDF oficial. Para *catalíticos modernos* la respuesta es definitiva (no se restringen
  nunca). Para *catalíticos antiguos en emergencia* y *sin sello verde en episodio*, los
  **dígitos adicionales los fija la autoridad día a día**; la app avisa y enlaza la
  declaración oficial en vez de adivinarlos. Esa es la parte que se podría endurecer
  después parseando los dígitos exactos del PDF (ver `digitos_detectados` en estado.json).

## Notas de mantenimiento

- Si el MMA cambia la URL o el formato del PDF, el script deja `estado.json` con
  `"ok": false` y la app cae a modo normal avisando que no pudo confirmar el episodio.
  Nunca afirma "circula" sobre un episodio sin confirmar.
- El calendario de dígitos y los feriados están al inicio de `index.html`; actualízalos
  cada temporada.
