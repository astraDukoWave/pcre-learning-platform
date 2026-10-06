"""Construye una ruta de contenido mínima y válida en un directorio temporal.

Las pruebas la modifican (`mutate`) para provocar cada regla del lint. Todo el texto es
original y de prueba; no es contenido para alumnos.
"""

from __future__ import annotations

import copy
import hashlib
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

PATH_SLUG = "ruta-prueba"
PASSAGE = (
    "Course A meets on Monday, Wednesday and Friday from 6 to 8 p.m. It costs 120 dollars a "
    "month and has twelve students per group. Course B meets on Saturday mornings from 9 to 1. "
    "It costs 90 dollars a month, but groups have up to twenty students. Both courses include "
    "an online library, and Course A also records every class so students can review it later. "
    "Marta works until 5 p.m. from Monday to Friday and wants to study three evenings a week. "
    "She prefers small groups because she likes to ask questions, and she wants to review "
    "difficult classes at home. Her friend Luis works on Saturdays, so he cannot take the "
    "weekend course, even though it is cheaper. They both need to decide before the end of "
    "the month, when registration closes."
)


def _choice(key: str, pool: str, n: int, **extra: Any) -> dict[str, Any]:
    act = {
        "key": key,
        "format": "choice",
        "task_family": "read_in_daily_life",
        "pool": pool,
        "objectives": ["U1.R"],
        "instructions_es": "Elige la respuesta correcta según el texto.",
        "prompt_en": f"Question {n}: which course fits Marta's schedule?",
        "stimulus": {"passage": "p1"},
        "options": [
            {"id": "a", "text": f"Course A, option {n}"},
            {"id": "b", "text": f"Course B, option {n}", "why_es": "Es en sábado."},
            {"id": "c", "text": f"Neither course, option {n}"},
        ],
        "correct": ["a"],
        "explanation_es": "Marta puede estudiar entre semana por la noche.",
    }
    if pool == "practice":
        act["hints"] = ["Busca los días de cada curso."]
        act["support_es"] = "Compara los horarios con el de Marta."
    act.update(extra)
    return act


def _writing(key: str, prompt: str) -> dict[str, Any]:
    return {
        "key": key,
        "format": "short_writing",
        "task_family": "write_an_email",
        "pool": "practice",
        "objectives": ["U1.W"],
        "instructions_es": "Escribe un correo breve.",
        "prompt_en": prompt,
        "min_words": 40,
        "max_words": 90,
        "rubric": "email",
        "model_answer": "Dear Ms. Lee, I would like to ask about the evening course.",
        "model_commentary_es": "Saluda, dice el propósito y cierra con cortesía.",
    }


def base_files() -> dict[str, Any]:
    lesson_reading = {
        "kind": "lesson",
        "slug": "u1-l1-lectura",
        "unit": "u1-informacion-decisiones",
        "position": 1,
        "skill": "reading",
        "title": "Elegir un curso",
        "status": "draft",
        "objectives": ["U1.R"],
        "objective_es": "Localizarás horarios y costos para decidir qué curso conviene.",
        "sources": [
            {
                "source": "ets-toefl-ibt-content",
                "claim": "Formato Read in Daily Life",
                "scope": "formato",
            }
        ],
        "pcre": {
            "pattern": "from 6 to 8 p.m.",
            "concept": "Los rangos de horario se leen con from … to …",
            "rules": [
                {
                    "text": "From marca el inicio y to el final del rango.",
                    "source": "cambridge-prepositions",
                }
            ],
            "examples": ["The shop is open from 9 to 5.", "I study from Monday to Thursday."],
        },
        "application_task_es": "Anota tu propio horario de estudio con from … to …",
        "passages": [{"id": "p1", "title_en": "Two courses", "text_en": PASSAGE}],
        "activities": [_choice(f"u1.l1.p{i}", "practice", i) for i in range(1, 5)]
        + [_choice(f"u1.l1.r{i}", "review", i + 10) for i in range(1, 5)],
    }
    lesson_writing = {
        "kind": "lesson",
        "slug": "u1-l3-escritura",
        "unit": "u1-informacion-decisiones",
        "position": 3,
        "skill": "writing",
        "title": "Pedir información por correo",
        "status": "draft",
        "objectives": ["U1.W"],
        "objective_es": "Escribirás una petición clara.",
        "sources": [
            {
                "source": "ets-toefl-ibt-content",
                "claim": "Formato Write an Email",
                "scope": "formato",
            }
        ],
        "pcre": {
            "pattern": "I would like to ask about…",
            "concept": "Una petición cortés empieza con el propósito.",
            "rules": [
                {
                    "text": "Di el propósito en la primera oración.",
                    "source": "ets-toefl-ibt-content",
                }
            ],
            "examples": [
                "I would like to ask about the fees.",
                "I am writing to ask about the dates.",
            ],
        },
        "application_task_es": "Escribe una petición a tu escuela.",
        "activities": [
            _writing("u1.l3.p1", "Write to the school to ask about evening classes."),
            _writing("u1.l3.p2", "Write to a gym to ask about weekend hours."),
        ],
    }
    scenario = {
        "kind": "scenario",
        "slug": "u1-escenario",
        "unit": "u1-informacion-decisiones",
        "position": 5,
        "title": "En la recepción",
        "status": "draft",
        "objectives": ["U1.T"],
        "situation_es": "Pides información en la recepción de una escuela.",
        "situation_en": "You ask for information at a school reception desk.",
        "learner_role_en": "A new student",
        "agent_persona_en": "A friendly receptionist",
        "opening_en": "Hi! How can I help you today?",
        "required_moves": ["ask_schedule", "ask_price"],
        "coach_hints": ["Ask about the time first."],
        "rubric": "transfer",
        "activities": [
            {
                "key": "u1.esc.d1",
                "format": "guided_dialogue",
                "task_family": "communicative_transfer",
                "pool": "practice",
                "objectives": ["U1.T"],
                "instructions_es": "Elige qué dirías.",
                "start": "n1",
                "nodes": [
                    {
                        "id": "n1",
                        "speaker": "agent",
                        "text_en": "Hi! How can I help you today?",
                        "options": [
                            {
                                "id": "a",
                                "text": "What time are the classes?",
                                "next": "n2",
                                "feedback_es": "Pregunta directa y clara.",
                            },
                            {
                                "id": "b",
                                "text": "Classes.",
                                "next": "n2",
                                "feedback_es": "Muy breve: arma una pregunta.",
                                "good": False,
                            },
                        ],
                    },
                    {
                        "id": "n2",
                        "speaker": "agent",
                        "text_en": "From 6 to 8 p.m. Anything else?",
                        "options": [],
                    },
                ],
                "success_paths": [["n1.a"]],
            }
        ],
    }
    checkpoint = {
        "kind": "assessment_form",
        "slug": "u1-checkpoint",
        "unit": "u1-informacion-decisiones",
        "form_kind": "checkpoint",
        "position": 6,
        "title": "Checkpoint de la unidad 1",
        "status": "draft",
        "objectives": ["U1.R", "U1.W"],
        "duration_minutes": 15,
        "passages": [
            {"id": "p1", "text_en": PASSAGE.replace("Marta", "Ana").replace("Luis", "Pedro")}
        ],
        "activities": [
            {
                **_choice(f"u1.cp.a{i}", "assessment", i + 40),
                "prompt_en": f"Checkpoint question {i}: what does Ana prefer?",
            }
            for i in range(1, 7)
        ]
        + [{**_writing("u1.cp.w1", "Write to ask about the library hours."), "pool": "assessment"}],
    }
    return {
        "path.yaml": {
            "code": PATH_SLUG,
            "exam_code": "toefl_ibt",
            "exam_format_version": "2026-01",
            "level_from": "B1",
            "level_to": "B2",
            "title": "Ruta de prueba",
            "label": "Preparación independiente",
            "catalog_version": 1,
            "units": [
                {
                    "slug": "u1-informacion-decisiones",
                    "position": 1,
                    "title": "Unidad 1",
                    "summary": "Resumen 1.",
                },
                {
                    "slug": "u5-ideas-academicas",
                    "position": 5,
                    "title": "Unidad 5",
                    "summary": "Resumen 5.",
                },
            ],
        },
        "objectives.yaml": {
            "objectives": [
                {
                    "code": c,
                    "unit": int(c[1]),
                    "skill": s,
                    "description_es": f"Objetivo {c}",
                    "cefr_ref_es": "Paráfrasis de prueba.",
                    "families": [],
                }
                for c, s in (
                    ("U1.R", "reading"),
                    ("U1.L", "listening"),
                    ("U1.W", "writing"),
                    ("U1.S", "speaking"),
                    ("U1.T", "transfer"),
                    ("U5.R", "reading"),
                )
            ]
        },
        "sources.yaml": {
            "sources": [
                {
                    "id": "ets-toefl-ibt-content",
                    "url": "https://www.ets.org/toefl",
                    "title": "TOEFL iBT",
                    "publisher": "ETS",
                    "accessed_on": "2026-10-05",
                    "status": "consulted",
                },
                {
                    "id": "cambridge-prepositions",
                    "url": "https://dictionary.cambridge.org/grammar",
                    "title": "Prepositions of time",
                    "publisher": "Cambridge",
                    "accessed_on": "2026-10-05",
                    "status": "consulted",
                },
            ]
        },
        "rubrics.yaml": {
            "rubrics": [
                {
                    "id": rid,
                    "version": 1,
                    "name_es": rid,
                    "applies_to": [fam],
                    "criteria": [
                        {
                            "id": "task",
                            "name_es": "Tarea",
                            "levels": [
                                {"score": n, "descriptor_es": f"Nivel {n}"} for n in range(4)
                            ],
                        }
                    ],
                }
                for rid, fam in (
                    ("email", "write_an_email"),
                    ("interview", "take_an_interview"),
                    ("transfer", "communicative_transfer"),
                )
            ]
        },
        "audio/manifest.yaml": {"audio": []},
        "units/u1/l1-lectura.yaml": lesson_reading,
        "units/u1/l3-escritura.yaml": lesson_writing,
        "units/u1/escenario.yaml": scenario,
        "units/u1/checkpoint.yaml": checkpoint,
    }


def write_content(root: Path, mutate: Callable[[dict[str, Any]], None] | None = None) -> Path:
    """Escribe la ruta en `root/<PATH_SLUG>/` y devuelve `root` (el `--dir` del CLI)."""
    files = copy.deepcopy(base_files())
    if mutate is not None:
        mutate(files)
    path_dir = root / PATH_SLUG
    for rel, data in files.items():
        target = path_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, bytes):
            target.write_bytes(data)
        elif isinstance(data, str):
            target.write_text(data, encoding="utf-8")
        else:
            target.write_text(
                yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8"
            )
    return root


def add_listening(files: dict[str, Any], *, reviewed: bool) -> None:
    """Lección de escucha con audio; `reviewed=False` deja el audio pendiente."""
    mp3 = b"ID3-prueba-no-es-audio-real"
    entry: dict[str, Any] = {
        "id": "u1-l2-aviso",
        "script": [{"speaker": "Narrator", "text": "Attention please. " * 25}],
        "voices": {"Narrator": "voz-a"},
    }
    if reviewed:
        files["audio/0a1b2c3d-u1-l2-aviso.mp3"] = mp3
        entry.update(
            {
                "file": "0a1b2c3d-u1-l2-aviso.mp3",
                "sha256": hashlib.sha256(mp3).hexdigest(),
                "provider": "deepgram",
                "model": "aura-2",
                "reviewed_by": "jonathan",
                "reviewed_at": "2026-10-06",
            }
        )
    files["audio/manifest.yaml"] = {"audio": [entry]}

    def listen(key: str, pool: str, n: int) -> dict[str, Any]:
        act = _choice(key, pool, n + 100)
        act.update(
            {
                "task_family": "listen_announcement",
                "objectives": ["U1.L"],
                "stimulus": {"audio": "u1-l2-aviso", "transcript": "Attention please."},
            }
        )
        act.pop("support_es", None)
        return act

    files["units/u1/l2-escucha.yaml"] = {
        **{
            k: v
            for k, v in files["units/u1/l1-lectura.yaml"].items()
            if k not in ("passages", "activities")
        },
        "slug": "u1-l2-escucha",
        "position": 2,
        "skill": "listening",
        "title": "Escuchar un aviso",
        "objectives": ["U1.L"],
        "activities": [listen(f"u1.l2.p{i}", "practice", i) for i in range(1, 5)]
        + [listen(f"u1.l2.r{i}", "review", i + 10) for i in range(1, 5)],
    }
