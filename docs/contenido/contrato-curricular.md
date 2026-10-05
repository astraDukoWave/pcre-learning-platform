# Contrato curricular — ruta `toefl-ibt-2026-b1-b2`

Versión 1.0 · 5 oct 2026 · Estado: **APROBADO** por Jonathan el 5 oct 2026 (gate G0); contenido congelado en
`9aa2e2c` (solo cambia esta línea).
Aplica a MVP-01 (Unidad 1, diagnóstico inicial y escenario U1) y a MVP-03
(unidades 2–8, formulario final y escenarios 2–8). Insumo:
PCRE-MVP-20261005 §6 (privado). El esquema ejecutable vive en el código
(`apps/backend/app/modules/content/`); este contrato dice qué debe cumplir
el contenido y cómo se revisa.

---

## 1. Identidad y afirmaciones permitidas

- **Nombre visible de la ruta:** "Ruta B1 → B2 con tareas tipo TOEFL iBT
  (formato 2026)", con la etiqueta "Preparación independiente".
- **Aviso de marca**, en el pie de página y en "Cómo funciona": "TOEFL y
  TOEFL iBT son marcas registradas de ETS. Este producto no está avalado ni
  aprobado por ETS."
- **Se puede decir:** practicas habilidades de B1 hacia B2, te familiarizas
  con las tareas del formato 2026 y ves evidencia formativa de tu progreso.
- **No se puede decir:** certificado, nivel acreditado, curso oficial,
  predicción o garantía de puntuación, equivalencia con el examen, garantía
  de empleo o de aumento de sueldo. Las comprobaciones propias son
  **muestras formativas**, no simulacros.
- Completar las 32 lecciones es un alcance editorial, no una dosis
  demostrada para alcanzar B2.

## 2. Formato de referencia

TOEFL iBT desde enero de 2026 `[verified-this-session: ets.org, página de
contenido del examen, 5 oct 2026]`:

| Sección | Ítems y tiempo aprox. | Tareas (nombre oficial) |
|---|---|---|
| Reading | 50 · ~30 min | Complete the Words · Read in Daily Life · Read an Academic Passage |
| Listening | 47 · ~29 min | Listen and Choose a Response · Listen to a Conversation · Listen to an Announcement · Listen to an Academic Talk |
| Writing | 12 · ~23 min | Build a Sentence · Write an Email · Write for an Academic Discussion |
| Speaking | 11 · ~8 min | Listen and Repeat · Take an Interview |

Bandas de 1 a 6 por sección y global, con un total comparable de 0 a 120
durante una transición de dos años. No es TOEFL ITP (otra estructura).
Nuestras comprobaciones no reproducen tiempos, adaptatividad ni preguntas
de ETS: el blueprint de ETS es referencia de tareas, no un banco que
copiar. Las muestras oficiales se enlazan, no se reproducen.

## 3. Familias de tareas → formatos internos

| `task_family` | Tarea de referencia | Formato interno | Notas |
|---|---|---|---|
| `complete_the_words` | Complete the Words | `word_completion` | Palabras incompletas en un párrafo: se da el inicio y el alumno escribe el resto |
| `read_in_daily_life` | Read in Daily Life | `choice` | Avisos, correos, horarios, menús, formularios |
| `read_academic_passage` | Read an Academic Passage | `choice` | Tesis, apoyo, vocabulario en contexto, inferencia |
| `listen_choose_response` | Listen and Choose a Response | `choice` + audio | Una frase y la respuesta adecuada |
| `listen_conversation` | Listen to a Conversation | `choice` + audio | Dos o tres hablantes |
| `listen_announcement` | Listen to an Announcement | `choice` + audio | Propósito, instrucciones, cambios |
| `listen_academic_talk` | Listen to an Academic Talk | `choice` + audio | Idea principal, detalle, actitud |
| `build_a_sentence` | Build a Sentence | `sentence_order` | Admite varios órdenes válidos |
| `write_an_email` | Write an Email | `short_writing` | Propósito y puntos pedidos |
| `write_academic_discussion` | Write for an Academic Discussion | `short_writing` | Postura, apoyo y respuesta a otras ideas |
| `listen_and_repeat` | Listen and Repeat | `recorded_speaking` | Modelo en audio; grabación local |
| `take_an_interview` | Take an Interview | `recorded_speaking` | Pregunta, preparación y respuesta |
| `communicative_transfer` | — (propia) | `guided_dialogue` o coach de voz | Situación guiada de la unidad; **no** se presenta como tarea oficial |

Las seis clases internas son componentes reutilizables. No se convierte
todo en selección múltiple para simplificar la programación.

## 4. Mapa de unidades y objetivos

Cada unidad tiene cuatro lecciones (lectura, escucha, escritura y habla),
un escenario de transferencia y un checkpoint. Códigos de objetivo:
`U{n}.R`, `U{n}.L`, `U{n}.W`, `U{n}.S` y `U{n}.T`, con subobjetivos `.1`,
`.2` cuando hacen falta (`U1.R.1`). Los códigos son estables: una vez
publicados no se renumeran.

| Unidad | Lectura (`R`) | Escucha (`L`) | Escritura (`W`) | Habla (`S`) | Transferencia (`T`) |
|---|---|---|---|---|---|
| U1 · Información y decisiones cotidianas | Localizar condiciones y datos explícitos en mensajes y horarios; una inferencia simple | Identificar propósito e instrucciones en avisos breves | Construir oraciones correctas y una petición clara | Presentarse y responder preguntas familiares | Pedir información para resolver una gestión |
| U2 · Pedir y aclarar | Entender solicitudes y restricciones | Elegir respuestas adecuadas y pedir aclaración | Correo con propósito y detalles | Aclarar una necesidad y reformular | Resolver un malentendido |
| U3 · Experiencias y cambios | Seguir secuencias temporales | Distinguir hechos, planes y cambios | Relatar y conectar eventos con precisión | Narrar una experiencia; repetir mensajes breves | Explicar un cambio de planes |
| U4 · Comparar y justificar | Contrastar alternativas y evidencias | Reconocer preferencias y razones | Recomendar una opción y reconocer una objeción | Defender una decisión y responder preguntas | Elegir entre dos opciones con otra persona |
| U5 · Ideas académicas | Tesis, apoyo y vocabulario en contexto | Tomar notas de una explicación breve | Aportar una opinión con apoyo a una discusión | Explicar un concepto con ejemplos | Explicar una idea a un compañero |
| U6 · Resolver problemas | Inferir causas y condiciones | Entender desacuerdos y propuestas | Proponer una solución por correo | Negociar una alternativa y sus consecuencias | Negociar una solución |
| U7 · Evaluar argumentos | Distinguir afirmación, evidencia e inferencia | Reconocer postura e intención | Comparar argumentos y responder con matices | Elaborar y sostener una respuesta coherente | Defender una postura con matices |
| U8 · Integración con menor apoyo | Lecturas nuevas y completado en contexto | Mezcla de conversaciones, avisos y exposiciones | Oraciones, correo y discusión sin ayudas | Repetición y entrevista con temas nuevos | Situación integradora sin apoyo |

Apoyo: en U1–U4 la **práctica** admite apoyo en español y ejemplos
resueltos; U5–U8 lo reducen hasta eliminarlo en U8. Las comprobaciones
nunca muestran apoyos.

Familias por unidad (mínimo; el resto es libre si el objetivo lo pide):

| Unidad | Lectura | Escucha | Escritura | Habla |
|---|---|---|---|---|
| U1 | `read_in_daily_life`, `complete_the_words` | `listen_announcement`, `listen_choose_response` | `build_a_sentence`, `write_an_email` (breve) | `take_an_interview`, `listen_and_repeat` |
| U2 | `read_in_daily_life` | `listen_choose_response`, `listen_conversation` | `write_an_email` | `take_an_interview` |
| U3 | `read_in_daily_life`, `complete_the_words` | `listen_conversation`, `listen_announcement` | `build_a_sentence`, `write_an_email` | `listen_and_repeat`, `take_an_interview` |
| U4 | `read_in_daily_life`, `read_academic_passage` (breve) | `listen_conversation` | `write_an_email` | `take_an_interview` |
| U5 | `read_academic_passage`, `complete_the_words` | `listen_academic_talk` | `write_academic_discussion` | `take_an_interview` |
| U6 | `read_academic_passage`, `read_in_daily_life` | `listen_conversation` | `write_an_email` | `take_an_interview` |
| U7 | `read_academic_passage` | `listen_academic_talk`, `listen_conversation` | `write_academic_discussion` | `take_an_interview` |
| U8 | todas las de lectura | todas las de escucha | todas las de escritura | `listen_and_repeat`, `take_an_interview` |

## 5. Mínimos de contenido

**Por lección:**

- Objetivo observable (qué hará el alumno) con su código.
- Explicación breve con el bloque PCRE (§6.4), dos ejemplos propios y una
  tarea de aplicación.
- Lectura y escucha: al menos **4 ítems** en el pool `practice` y **4
  alternativos** en el pool `review` (alimentan el repaso espaciado).
- Escritura y habla: **2 consignas distintas**, rúbrica y un ejemplo
  comentado.

**Por unidad:** 4 lecciones, un escenario (§7) y un checkpoint con ítems
nuevos del pool `assessment` (al menos 6 cerrados y una producción breve).

**Formularios de ruta:** diagnóstico inicial y final, con el mismo reparto
de objetivos y sin ítems repetidos entre ellos ni con la práctica: **12
ítems cerrados, 2 consignas escritas y 2 orales**. Son comparables por
diseño, sin calibración estadística. Duración objetivo del diagnóstico: 25
minutos o menos.

**Cobertura:** todas las familias de la §3 aparecen en práctica y en una
comprobación posterior (§10).

Son mínimos editoriales para acotar el trabajo, no un umbral científico.
No se genera relleno para alcanzar el conteo: si un objetivo no tiene
evidencia suficiente, la matriz lo declara pendiente y el ciclo no se
marca terminado.

## 6. Reglas de redacción

### 6.1 Originalidad

- Todo texto, audio, ítem y ejemplo es original.
- No se copian preguntas de ETS ni de exámenes o cursos comerciales
  (Platzi incluido), ni transcripciones de terceros.
- Los descriptores del MCER se parafrasean y se citan; no se copian
  literalmente.

### 6.2 Nivel y extensión

- Lectura: 120–250 palabras en U1–U3, hasta 350 en U4–U6 y 300–450 en los
  pasajes académicos de U5–U8.
- Escucha: avisos de 20–40 s, conversaciones de 45–90 s, exposiciones de
  90–150 s, con ritmo natural de B1–B2.
- Vocabulario por encima de B2 solo con glosa en práctica, nunca como
  clave de una respuesta.

### 6.3 Ítems

- Una sola clave por ítem de selección (o selección múltiple declarada
  como tal). Distractores plausibles y de longitud parecida. Sin "todas las
  anteriores", sin negaciones tramposas.
- Completados y órdenes: listar **todas las variantes válidas**
  (`accepted`, `accepted_orders`). Una respuesta correcta no puede quedar
  marcada como error.
- Cada ítem declara su objetivo y su familia.
- Contextos diversos (México y Latinoamérica, ámbitos académicos y
  laborales internacionales), nombres variados y sin estereotipos. Sin
  temas sensibles. Moneda y fechas coherentes con el contexto (USD en
  contextos de EE. UU.).

### 6.4 Explicaciones con el método PCRE

PCRE es el formato propio de explicación y se usa cuando aclara:

1. **Patrón:** el fragmento que el alumno debe reconocer (se resalta en la
   interfaz).
2. **Concepto:** qué hace y para qué sirve.
3. **Reglas:** incluyen cuándo **no** aplican.
4. **Ejemplos:** dos originales.

Prohibidas las reglas absolutas falsas. El lint marca "siempre", "nunca",
"always", "never" y "must" dentro de una regla como advertencia que el
revisor confirma o corrige. No se anuncia PCRE como un método de eficacia
demostrada.

### 6.5 Apoyo en español

Solo en práctica de U1–U4: instrucciones, glosas y explicaciones. Las
consignas en inglés no se traducen en las comprobaciones.

### 6.6 Guiones de audio

Hablantes etiquetados (`A`, `B`, `Narrator`), voces distintas por hablante
y pausas marcadas. Sin efectos ni música. El guion completo se guarda con
el audio (§11).

### 6.7 Problemas conocidos del borrador que se corrigen

- El texto de ejemplo de Alex (spec de producto v0.3 §10) dice que Alex
  puede estudiar "tres tardes" (*afternoons*) y el curso A es de 6 a 8 p.m.
  (*evenings*). Además usa libras esterlinas. Se reescribe sin la
  ambigüedad y en USD.
- El contenido legado afirma "THAN es obligatorio". Es falso como regla
  absoluta: *than* introduce el segundo término y se omite cuando el
  contexto lo hace claro ("This one is better."). Además "easy → easier"
  sigue la regla de dos sílabas terminadas en -y, no la de adjetivos cortos.

## 7. Escenarios de transferencia

Uno por unidad (`content_items.kind = scenario`). Un mismo escenario sirve
para dos modos:

- **Modo texto** (`guided_dialogue`, MVP-01): grafo determinista de turnos.
  El agente dice una línea y el alumno elige o escribe; cada opción tiene
  retroalimentación propia.
- **Modo voz** (MVP-02): el coach usa la situación, el objetivo, la
  persona, la línea de apertura, los movimientos requeridos y las pistas
  del mismo archivo.

Campos: situación, objetivos, rol del alumno, persona del agente (en
inglés, nivel B1–B2), apertura, movimientos requeridos (p. ej. pedir
aclaración, dar una razón, aceptar una objeción), pistas, duración máxima
(300 s) y rúbrica. La persona del agente nunca concede progreso, publica
contenido ni pide datos personales.

## 8. Rúbricas formativas

Cuatro criterios con descriptores de 0 a 3. Versionadas; cada resultado
guarda su versión.

- **Correo (`write_an_email`):** cumplimiento de la tarea (todos los puntos
  pedidos) · organización (saludo, propósito, detalles, cierre) · control
  del lenguaje (errores que dificultan entender) · registro y tono.
- **Discusión académica:** postura clara · apoyo (razón y ejemplo) ·
  diálogo con otras ideas · variedad y precisión del lenguaje.
- **Entrevista oral:** relevancia · desarrollo (detalle o ejemplo) ·
  coherencia (conectores) · lenguaje recuperable. La pronunciación y la
  fluidez **no** se evalúan desde una transcripción; si se piden, son
  autoevaluación identificada como tal.
- **Repetición (`listen_and_repeat`):** palabras reconocidas sobre el total
  (desde MVP-02, con transcripción) más autoevaluación. Un fallo del
  reconocimiento no es un error del alumno por defecto.

En MVP-01, la escritura y el habla se cierran con **autoevaluación guiada**:
el alumno marca los criterios de la rúbrica y luego ve el ejemplo
comentado. El resultado se guarda con `evaluation_source = self`.

## 9. Formato de los archivos

```
content/toefl-ibt-2026-b1-b2/
├── path.yaml              # ruta, unidades (slug, posición, título) y versión del catálogo
├── objectives.yaml        # códigos, descripción, referencia MCER parafraseada, familias
├── sources.yaml           # registro de fuentes (url, título, editor, fecha de consulta)
├── rubrics.yaml           # rúbricas versionadas
├── units/
│   └── u1-informacion-decisiones/
│       ├── l1-lectura.yaml
│       ├── l2-escucha.yaml
│       ├── l3-escritura.yaml
│       ├── l4-habla.yaml
│       ├── escenario.yaml
│       └── checkpoint.yaml
├── assessments/
│   ├── inicial.yaml
│   └── final.yaml
└── audio/
    ├── manifest.yaml      # procedencia de cada archivo (§11)
    └── <sha8>-<slug>.mp3
content/_legacy/           # referencia histórica; nunca se importa ni se publica
```

Campos comunes de una actividad: `key` (única en toda la ruta), `format`,
`task_family`, `pool`, `objectives`, `instructions_es`, `prompt_en`,
`stimulus` (texto o `audio` + `transcript`), `hints`, `support_es` (solo
U1–U4 práctica), `explanation_es` (se muestra después de enviar), `solution`
(según formato), `rubric` (referencia) y `sources` (referencias al
registro).

Por formato:

- `choice`: `options` (`id`, `text`) y `correct` (lista de ids); motivo por
  opción opcional.
- `word_completion`: texto con huecos `{{id}}`; cada hueco con `shown`
  (inicio visible), `accepted` (lista) y sensibilidad a mayúsculas
  (desactivada por defecto).
- `sentence_order`: `tokens` en orden canónico y `accepted_orders` (lista
  de listas).
- `short_writing`: `min_words`, `max_words`, `rubric`, `model_answer` y
  `model_commentary_es`.
- `recorded_speaking`: `subtype` (`listen_and_repeat` con
  `target_sentence` y `audio`; `interview` con pregunta, `prep_seconds` y
  `response_seconds`), `rubric` y `model_answer`.
- `guided_dialogue`: `nodes` (`id`, `speaker`, `text_en`, `options`
  con `text`, `next` y `feedback_es`) y `success_paths`.

Prohibidos en cualquier archivo publicable: `TODO`, `TBD`, `lorem`,
`placeholder`, `XXX`, audio inexistente y enlaces rotos.

## 10. Cobertura

`make content-lint` genera `docs/contenido/cobertura.md`, que se versiona y
que la CI regenera para comprobar que está al día. Contiene:

- Matriz familia × pool (`practice`, `review`, `assessment`) con las claves
  de actividad.
- Conteo por objetivo y por formato.
- Lo pendiente, marcado como "pendiente" (nunca omitido).
- Estado editorial por ítem de contenido: `draft`, `ready-for-review`,
  `approved` o `published` (este último se lee de la base de datos en el
  panel, no del archivo).

**Ruta completa** solo cuando: las 32 lecciones, 8 escenarios, 8
checkpoints y los 2 formularios están publicados; cada familia aparece en
práctica y en una comprobación posterior; y todo audio está revisado. La
etiqueta "ruta completa" la calcula el sistema; nadie la escribe a mano.

## 11. Audio

- Se genera con TTS en el workflow `content-audio.yml` (ADR-12): solo con
  aprobación del environment, con tope de caracteres por ejecución y
  costo estimado en el resumen del run. Abre un PR con los MP3 y el
  manifiesto.
- `manifest.yaml`, por archivo: `file`, `sha256`, `script_hash`, voces por
  hablante, proveedor, modelo, `generated_at`, `reviewed_by` y
  `reviewed_at`.
- MP3 mono de 48–64 kbps; nombre por hash del guion, de modo que un guion
  cambiado produce un archivo nuevo.
- Una actividad de escucha no se publica sin audio revisado (`reviewed_by`
  lleno). Un botón sin sonido no cumple.
- Accesibilidad: en práctica, la transcripción se ofrece después de
  responder o como ayuda registrada; en comprobación no se muestra antes de
  enviar. Una adaptación accesible se ofrece indicando que cambia la
  condición de evaluación.

## 12. Flujo editorial

Estados: `draft` → `ready-for-review` (lint limpio, cobertura al día,
audio presente) → `approved` (Jonathan, por hash) → `published`. Editar
crea otra revisión que vuelve a `draft`; la publicada sigue vigente hasta
reemplazarla. Retirar no borra historial.

Lista de revisión por lección (el panel la muestra):

1. El objetivo es observable y coincide con el mapa.
2. La explicación es correcta y cada regla tiene fuente y alcance.
3. Los ejemplos son originales y no ambiguos.
4. Las claves están verificadas y las variantes válidas, listadas.
5. Los distractores son plausibles y no hay dos respuestas defendibles.
6. El apoyo en español aparece solo donde se permite.
7. El audio coincide con el guion y se entiende.
8. Hay alternativas de accesibilidad (transcripción, texto alternativo).
9. No hay marcadores pendientes y el lint está limpio.

Jerarquía de fuentes por propósito: MCER para objetivos; ETS para formato;
diccionarios y gramáticas de referencia (Cambridge Dictionary, British
Council LearnEnglish o equivalentes) para uso; estudios originales para
afirmaciones pedagógicas. Cada lección cita ETS para el formato y una
fuente para cada regla lingüística que enuncia. Una fuente que no pudo
consultarse queda como pendiente, nunca como verificada.

Revisión por lotes: una unidad por lote. El modelo nunca se aprueba a sí
mismo. Hanademi u otras herramientas pueden apoyar la investigación fuera
de la app, sin datos de alumnos y sin cambiar estados editoriales.

## 13. Primer contenido que se programa (U1 · L1, lectura)

- **Objetivo `U1.R`:** localizar condiciones y datos explícitos y hacer una
  inferencia simple al comparar dos opciones.
- **Situación:** una persona que trabaja hasta las 5 p.m. y puede estudiar
  tres noches por semana compara dos cursos con horarios, costo, tamaño de
  grupo y recursos distintos. Uno es compatible con su horario; el otro
  tiene ventajas diferentes.
- **Ítems:** compatibilidad de horario, recurso para repasar, dato
  explícito, inferencia y, en el pool `review`, un caso alternativo con
  otro personaje y otras restricciones.
- Es un problema de comprensión, no una pregunta que se resuelve
  recordando una regla gramatical.
- El agente redacta el contenido completo y su solución como borrador
  revisable; el ejemplo del spec de producto puede reutilizarse corregido
  (§6.7).

## 14. Contenido legado

La lección legada de comparativos se exporta a `content/_legacy/` como
referencia histórica, con la regla corregida y una nota de procedencia. No
se importa ni se publica: su título reproduce el de un curso comercial y su
texto no pasó revisión. U4 escribe su propia explicación original.
