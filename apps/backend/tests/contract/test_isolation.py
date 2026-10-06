"""AC-06 / NFR-01: aislamiento con dos cuentas en cada endpoint con datos de alumno.

`STUDENT_ENDPOINTS` lista los endpoints de alumno; cada change set agrega los suyos aquí
o en su propia prueba de aislamiento (con recursos creados por la cuenta A y pedidos por
la B, que debe recibir 404).
"""

from __future__ import annotations

from tests.helpers import AccountFactory

# Endpoints cuyo resultado depende solo de la sesión (no reciben ids de recursos).
STUDENT_ENDPOINTS = ["/api/v1/me", "/api/v1/me/export"]


def test_each_account_only_sees_its_own_data(make_account: AccountFactory) -> None:
    a = make_account("a@example.com")
    b = make_account("b@example.com")
    for url in STUDENT_ENDPOINTS:
        body_a = a.client.get(url).text
        body_b = b.client.get(url).text
        assert a.email in body_a and b.email not in body_a, url
        assert b.email in body_b and a.email not in body_b, url
        assert str(a.id) not in body_b, url


def test_admin_user_routes_reject_students(make_account: AccountFactory) -> None:
    a = make_account("a2@example.com")
    b = make_account("b2@example.com")
    for method, url in (
        ("POST", f"/api/v1/admin/users/{a.id}/reset-link"),
        ("POST", f"/api/v1/admin/users/{a.id}/revoke-sessions"),
        ("PATCH", f"/api/v1/admin/users/{a.id}"),
    ):
        res = b.client.request(method, url, json={"is_internal": True}, headers=b.headers())
        assert res.status_code == 403, url
