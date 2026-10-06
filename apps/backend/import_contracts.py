"""Contrato de import-linter con las reglas de dependencia de `docs/arquitectura.md` §4.

Cada módulo de `app.modules.<módulo>` se divide en capas. La capa de un submódulo es el
primer segmento (después del módulo) cuyo nombre empieza por una capa conocida; así
`content.router_admin` es `router`, `content.service_editorial` es `service` y
`coaching.voice.adapters.deepgram_agent` es `adapters`. Lo demás (`loader`, `lint`,
`data_registry`…) es `support`.

Reglas (`rule` en `.importlinter`):

- `domain_purity`: `domain` no importa, ni directa ni indirectamente, `fastapi`,
  `starlette`, `sqlalchemy`, `pydantic`, `httpx`, `websockets`, `google`, `app.db` ni
  `app.http`; tampoco `models`, `repository`, `router` ni `adapters` de ningún módulo.
- `service_no_http`: `service` no importa (ni indirectamente) `fastapi` ni `starlette`, ni
  ningún `router`.
- `router_no_persistence`: `router` no importa `models` ni `repository` (pasa por servicios).
- `cross_module`: un módulo usa a otro solo por su `service`, su `domain` o sus `ports`.
  Excepción: un `repository` (o un `support` declarado en `allow`) puede leer `models` de
  otro módulo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from grimp import ImportGraph
from importlinter import Contract, ContractCheck, fields, output

MODULES_ROOT = "app.modules"
LAYERS = ("domain", "service", "ports", "models", "repository", "schemas", "router", "adapters")
PURE_EXTERNALS = ("fastapi", "starlette", "sqlalchemy", "pydantic", "httpx", "websockets", "google")
HTTP_EXTERNALS = ("fastapi", "starlette")


@dataclass(frozen=True)
class Located:
    module: str
    layer: str


def locate(name: str) -> Located | None:
    parts = name.split(".")
    root = MODULES_ROOT.split(".")
    if parts[: len(root)] != root or len(parts) <= len(root):
        return None
    module = parts[len(root)]
    for segment in parts[len(root) + 1 :]:
        for layer in LAYERS:
            if segment == layer or segment.startswith(layer + "_"):
                return Located(module, layer)
    return Located(module, "support")


def _top(name: str) -> str:
    return name.split(".", maxsplit=1)[0]


def _in(name: str, prefixes: tuple[str, ...]) -> bool:
    return any(name == p or name.startswith(p + ".") for p in prefixes)


class PcreLayersContract(Contract):
    type_name = "pcre_layers"

    rule = fields.StringField()
    allow = fields.SetField(subfield=fields.StringField(), required=False)

    def check(self, graph: ImportGraph, verbose: bool) -> ContractCheck:
        rule = str(self.rule)
        checker = {
            "domain_purity": self._domain_purity,
            "service_no_http": self._service_no_http,
            "router_no_persistence": self._router_no_persistence,
            "cross_module": self._cross_module,
        }.get(rule)
        if checker is None:
            raise ValueError(f"regla desconocida: {rule}")
        violations = checker(graph)
        return ContractCheck(kept=not violations, metadata={"violations": violations})

    def render_broken_contract(self, check: ContractCheck) -> None:
        for violation in check.metadata["violations"]:
            output.print_error(f"- {violation}", bold=False)
        output.new_line()

    # -- reglas -----------------------------------------------------------------------

    def _modules(self, graph: ImportGraph, layer: str) -> list[str]:
        found = []
        for name in sorted(graph.modules):
            loc = locate(name)
            if loc is not None and loc.layer == layer:
                found.append(name)
        return found

    def _chain(self, graph: ImportGraph, importer: str, imported: str) -> str:
        chain = graph.find_shortest_chain(importer=importer, imported=imported)
        return " -> ".join(chain) if chain else f"{importer} -> {imported}"

    def _transitive(self, graph: ImportGraph, module: str) -> set[str]:
        return set(graph.find_upstream_modules(module))

    def _domain_purity(self, graph: ImportGraph) -> list[str]:
        violations = []
        for module in self._modules(graph, "domain"):
            for target in sorted(self._transitive(graph, module)):
                bad_external = _top(target) in PURE_EXTERNALS and "." not in target
                bad_internal = _in(target, ("app.db", "app.http"))
                loc = locate(target)
                bad_layer = loc is not None and loc.layer in (
                    "models",
                    "repository",
                    "router",
                    "adapters",
                )
                if bad_external or bad_internal or bad_layer:
                    violations.append(
                        f"{module} no puede importar {target}: {self._chain(graph, module, target)}"
                    )
        return violations

    def _service_no_http(self, graph: ImportGraph) -> list[str]:
        violations = []
        for module in self._modules(graph, "service"):
            for target in sorted(self._transitive(graph, module)):
                loc = locate(target)
                if (_top(target) in HTTP_EXTERNALS and "." not in target) or (
                    loc is not None and loc.layer == "router"
                ):
                    violations.append(
                        f"{module} no puede importar {target}: {self._chain(graph, module, target)}"
                    )
        return violations

    def _router_no_persistence(self, graph: ImportGraph) -> list[str]:
        violations = []
        for module in self._modules(graph, "router"):
            for target in sorted(graph.find_modules_directly_imported_by(module)):
                loc = locate(target)
                if loc is not None and loc.layer in ("models", "repository"):
                    violations.append(f"{module} no puede importar {target} (usa un servicio)")
        return violations

    def _cross_module(self, graph: ImportGraph) -> list[str]:
        allowed_pairs = self._allowed_pairs()
        violations = []
        for importer in sorted(graph.modules):
            src = locate(importer)
            if src is None:
                continue
            for imported in sorted(graph.find_modules_directly_imported_by(importer)):
                dst = locate(imported)
                if dst is None or dst.module == src.module:
                    continue
                if dst.layer in ("service", "domain", "ports"):
                    continue
                if dst.layer == "models" and src.layer == "repository":
                    continue
                if (importer, imported) in allowed_pairs or (importer, f"*.{dst.layer}") in (
                    allowed_pairs
                ):
                    continue
                violations.append(
                    f"{importer} ({src.module}.{src.layer}) no puede importar {imported} "
                    f"({dst.module}.{dst.layer}): entre módulos solo service, domain o ports"
                )
        return violations

    def _allowed_pairs(self) -> set[tuple[str, str]]:
        pairs: set[tuple[str, str]] = set()
        raw: Any = self.allow or set()
        for entry in raw:
            importer, _, imported = str(entry).partition("->")
            pairs.add((importer.strip(), imported.strip()))
        return pairs
