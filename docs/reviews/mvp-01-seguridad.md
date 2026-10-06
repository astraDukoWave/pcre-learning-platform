# Revisión final de seguridad · MVP-01 (CS-10)

Contra `docs/arquitectura.md` §7 y NFR-05. Cada control lleva su evidencia ejecutable
(pruebas de `apps/backend/tests/` salvo que se indique otra ruta); todas corren en
`make verify` y en el job `backend` de la CI. Revisión hecha por el agente: no sustituye la
revisión humana de G1.

| Control (§7) | Estado | Evidencia |
|---|---|---|
| Sesión opaca: token de 32 bytes, solo su sha256 en la base | ✅ | `identity/test_domain.py::test_tokens_are_random_and_only_their_hash_is_stored`, `identity/test_auth_api.py::test_invitation_rows_store_only_hashes` |
| Cookie `__Host-pcre_session` con `HttpOnly`, `Secure`, `SameSite=Lax`, `Path=/`, sin `Domain` | ✅ | `identity/test_auth_api.py::test_login_sets_secure_host_cookie`, `::test_accept_and_reset_set_the_same_secure_cookie` |
| Vencimiento absoluto 7 días e inactividad 24 h; `last_seen_at` cada 5 min como máximo | ✅ | `identity/test_domain.py::test_session_absolute_and_idle_expiry`, `::test_last_seen_is_written_at_most_every_five_minutes`, `identity/test_auth_api.py::test_session_idle_and_absolute_expiry`, `::test_session_absolute_limit` |
| Rotación al entrar; revocación al salir, al consumir un reset y al borrar la cuenta | ✅ | `::test_login_rotates_the_previous_session`, `::test_logout_revokes_the_session`, `::test_reset_link_revokes_all_sessions`, `identity/test_export_delete.py::test_delete_removes_every_row_and_allows_reinvite` |
| Sin tokens en `localStorage` (CSRF solo en memoria; borradores en `sessionStorage` sin secretos) | ✅ | `apps/frontend/src/api/client.ts` (`setCsrfToken`), `apps/frontend/src/api/client.test.ts` |
| CSRF por sesión en `X-CSRF-Token` en todo método no seguro, comparado en tiempo constante | ✅ | `identity/test_csrf_origin.py::test_unsafe_method_without_or_with_wrong_token_is_403`, `::test_valid_token_and_origin_pass`, `::test_safe_methods_need_no_token` |
| `Origin` (o `Referer`) en `APP_ORIGIN` o la lista de desarrollo | ✅ | `::test_foreign_or_missing_origin_is_403`, `::test_referer_is_accepted_when_origin_is_missing` |
| WebSocket valida `Origin` antes de `accept()` | n/a en MVP-01 | No hay WebSocket hasta MVP-02 (CS del relay de voz) |
| Usuario y rol desde la sesión; recurso ajeno → 404; `/admin/*` exige admin | ✅ | `contract/test_isolation.py`, `practice/test_attempts_api.py::test_attempts_are_isolated_between_accounts`, `practice/test_assessments_api.py::test_answers_are_saved_without_feedback_and_isolated`, `identity/test_auth_api.py::test_students_cannot_use_admin_routes`, `insights/test_insights.py::test_admin_routes_are_guarded` |
| Primer admin solo por CLI | ✅ | `app/cli.py` (`create-admin-invite`); `identity/test_auth_api.py::test_role_cannot_be_chosen` |
| Argon2id; contraseña de 10 a 128 caracteres, distinta del email | ✅ | `identity/test_domain.py::test_argon2id_hash_and_verify`, `::test_password_policy` |
| Límite de login 5/min y 20/h por email e IP (IP del último salto de `X-Forwarded-For`); 429 con `Retry-After` | ✅ | `identity/test_domain.py::test_rate_limiter_per_minute_and_hour`, `identity/test_auth_api.py::test_login_rate_limit`, `::test_rate_limit_uses_the_last_forwarded_ip` |
| Error de login genérico | ✅ | `::test_wrong_password_and_unknown_email_get_the_same_error` |
| Cuerpo JSON ≤ 64 KB (también por partes, sin `Content-Length`) | ✅ | `test_security_headers.py::test_json_body_over_64kb_is_413`, `::test_chunked_body_over_the_limit_is_413` |
| Texto libre del alumno ≤ 4 000 caracteres | ✅ | `practice/test_grading.py::test_short_writing_self_assessment` |
| CSP (`default-src`, `script-src`, `style-src`, `img-src`, `media-src … blob:`, `connect-src` con el `wss:` propio, `font-src`, `frame-ancestors 'none'`, `object-src 'none'`, `base-uri`), `nosniff`, `Referrer-Policy`, `Permissions-Policy` | ✅ | `test_security_headers.py::test_security_headers_on_every_response`, `::test_hsts_only_in_production` |
| HSTS solo en producción | ✅ | `::test_hsts_only_in_production` |
| Fuentes servidas por la app (sin CDN) | ✅ | `apps/frontend/package.json` (`@fontsource/*`), CSP `font-src 'self'` |
| Markdown sin HTML crudo; sin enlaces `javascript:` | ✅ | `apps/frontend/src/components/Markdown.test.tsx` (`skipHtml`) |
| Secretos solo en Config Vars y secrets de environments; placeholders en el repo | ✅ | `.env.example`; job `image` (`scripts/ci/bundle-grep.sh`, AC-18) |
| Ninguna llamada de pago en pruebas ni en desarrollo | ✅ | `test_network_guard.py::test_external_connections_are_blocked`; `content/test_audio_generation.py` (adaptador con `MockTransport`) |
| Logs JSON sin contraseñas, tokens, cookies, `Authorization`, emails ni respuestas | ✅ | `test_logging.py::test_forbidden_fields_never_reach_the_log`, `::test_access_log_has_no_sensitive_headers`, `::test_login_logs_user_ref_not_email` |
| Errores 5xx en `error_events` sin mensajes ni datos personales; retención de 30 días | ✅ | `insights/test_insights.py::test_server_errors_are_recorded_and_old_ones_purged_at_startup` |
| Eventos de producto solo con ids y enumerados | ✅ | `insights/test_insights.py::test_events_are_a_closed_list_without_free_text` |
| Errores de la base sin parámetros en el mensaje | ✅ | `test_security_headers.py::test_engine_hides_query_parameters_in_errors` |
| Aviso de privacidad versionado, consentimiento y mayoría de edad antes de recolectar | ✅ (texto en borrador) | `identity/test_auth_api.py::test_accept_requires_consent_adult_and_good_password`, `test_legal.py` |
| Exportación y borrado de la cuenta | ✅ | `identity/test_export_delete.py` |
| Reloj de prueba: `prod` no arranca con él y la ruta no existe sin él | ✅ | `test_settings.py::test_prod_refuses_test_clock`, `progress/test_progress_api.py::test_test_clock_route_exists_only_with_the_test_clock` |

## Pendientes humanos (no bloquean el código)

- **G1:** revisar las Config Vars reales y que `APP_ORIGIN` sea el dominio de Heroku (la
  CSP y la cookie dependen de HTTPS en producción).
- **G4:** aprobar el texto legal (`apps/frontend/src/legal/*.md`, borrador
  `borrador-2026-10`) y completar el responsable en el aviso de privacidad.
