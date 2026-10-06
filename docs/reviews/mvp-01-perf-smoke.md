# MVP-01 · Smoke de rendimiento (NFR-03, AC-20)

Baseline de `scripts/perf/smoke.py`, corrido en la sesión cloud durante CS-10
`[verified-this-session]`. NFR-03 no es un gate de CI: este archivo guarda el resultado y
`docs/reviews/mvp-01-verify.md` lo cita en AC-20.

## Cómo se corrió

- Build de producción local: `npm run build` en `apps/frontend` y el comando `run.web` de
  `heroku.yml` (uvicorn, 1 worker) con `APP_ENV=prod`, `APP_ORIGIN=http://localhost:8011` y
  `LOG_LEVEL=WARNING`.
- Base desechable `pcre_migcheck` (PostgreSQL 16.14 local): `dbtool.py reset`,
  `python -m app.cli release` y `APP_ENV=dev python -m app.cli dev-seed --student-email
  perf@example.com` (contenido publicado por el revisor `fixture:dev`, solo para esta base).
- Máquina: contenedor Linux x86_64 de 4 CPU; cliente y servidor en la misma máquina.
- 100 peticiones por endpoint con 10 concurrentes, tras una de calentamiento que no cuenta;
  `POST /attempts` con un `Idempotency-Key` nuevo en cada petición (cada una crea un intento,
  así que `GET /me/progress` se mide con ~100 intentos de la alumna).

## Resultado

Smoke de rendimiento · 2026-10-06 03:57 UTC · http://localhost:8011
100 peticiones por endpoint, 10 concurrentes; umbral p95 < 800 ms; Python 3.12.11 en Linux x86_64

| Endpoint | Peticiones | Errores | p50 (ms) | p95 (ms) | Máx. (ms) | NFR-03 |
| --- | ---: | ---: | ---: | ---: | ---: | :---: |
| `GET /me` | 100 | 0 | 57.3 | 87.2 | 94.7 | ✅ |
| `GET /learning-paths/{id}` | 100 | 0 | 158.4 | 230.4 | 245.9 | ✅ |
| `GET /lessons/{id}` | 100 | 0 | 98.8 | 113.5 | 161.4 | ✅ |
| `POST /attempts` | 100 | 0 | 154.4 | 229.2 | 280.7 | ✅ |
| `GET /me/progress` | 100 | 0 | 301.3 | 410.9 | 452.7 | ✅ |

Salida del script: `exit 0` (todos los p95 bajo 800 ms, sin errores).

## Lectura

- Cumple NFR-03 con margen; no hace falta desviación.
- Con 10 concurrentes y un solo worker (como en `heroku.yml`), las peticiones esperan en
  cola: el p50 incluye esa espera.
- `GET /me/progress` es el más caro porque recalcula las métricas desde los intentos; crece
  con el historial de la alumna. Si en el piloto supera 800 ms, el primer paso es medir de
  nuevo en Heroku (dyno Basic, Postgres Essential-0, con latencia de red a la base) antes de
  cachear nada.
- No mide Heroku: la latencia real se observa en G2 con los logs del router
  (`docs/runbook.md`).
