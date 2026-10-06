# Paquete de revisión — Formulario de ruta: diagnóstico inicial

> Generado por `make review-packet UNIT=inicial` (MVP-03 REQ-08, contrato §12). No se
> edita a mano: la CI lo regenera y falla si hay diferencias. Ruta `toefl-ibt-2026-b1-b2`, catálogo v1.

## Cómo usarlo

1. Revisa cada ítem con su lista (§12) junto al panel `/admin/contenido`, que muestra
   la vista de alumno y la de autor.
2. El hash de cada ítem es el que el panel muestra en «Aprobar el hash …». Si no
   coincide, el archivo cambió después de este paquete: regenéralo.
3. Registra los hallazgos en el panel; el agente los corrige en una revisión nueva.
4. Una fuente **pendiente** no se pudo consultar: confírmala (y la regla que la cita)
   o pide otra. El audio sin revisar bloquea aprobar y publicar hasta G2.

## Resumen

| # | Ítem | Tipo | Estado | Objetivos | Actividades | Hash |
|---|---|---|---|---|---|---|
| 1 | Diagnóstico inicial (`diagnostico-inicial`) | comprobación | `ready-for-review` | U1.R, U2.R, U3.R, U5.R, U7.R, U8.R, U1.L, U2.L, U4.L, U6.L, U1.W, U2.W, U3.W, U5.W, U1.S, U4.S | 16 | `60f7f0c7848e` |

- Lint de estos archivos: 0 errores, 4 advertencias.
- Audio: 3 guiones, 0 revisados, 3 sin revisar.

## Fuentes citadas

| Fuente | Editor | Estado | Consultada | Usada en |
|---|---|---|---|---|
| [TOEFL iBT Test Content](https://www.ets.org/toefl/test-takers/ibt/about/content.html) (`ets-toefl-ibt-content`) | ETS | consultada | 2026-10-05 | diagnostico-inicial |

## 1. Diagnóstico inicial

- Archivo: `content/toefl-ibt-2026-b1-b2/assessments/inicial.yaml` · comprobación (diagnóstico inicial, 25 min) · estado `ready-for-review`
- Hash del contenido: `60f7f0c7848e…` (el panel lo muestra en «Aprobar el hash»)
- Objetivos:
  - `U1.R`: Localizar condiciones y datos explícitos en mensajes y horarios y hacer una inferencia simple al comparar opciones
  - `U2.R`: Entender solicitudes y restricciones en textos cotidianos
  - `U3.R`: Seguir secuencias temporales en un texto
  - `U5.R`: Identificar tesis, apoyo y vocabulario en contexto
  - `U7.R`: Distinguir afirmación, evidencia e inferencia
  - `U8.R`: Comprender lecturas nuevas y completar palabras en contexto
  - `U1.L`: Identificar el propósito y las instrucciones en avisos breves
  - `U2.L`: Elegir respuestas adecuadas y reconocer cuándo pedir aclaración
  - `U4.L`: Reconocer preferencias y razones
  - `U6.L`: Entender desacuerdos y propuestas
  - `U1.W`: Construir oraciones correctas y escribir una petición clara
  - `U2.W`: Escribir un correo con propósito y detalles
  - `U3.W`: Relatar y conectar eventos con precisión
  - `U5.W`: Aportar una opinión con apoyo a una discusión
  - `U1.S`: Presentarse y responder preguntas familiares
  - `U4.S`: Defender una decisión y responder preguntas
- Afirmaciones y fuentes:
  - Las familias de tareas del formato vigente se usan como referencia de formato; los ítems son originales. — `ets-toefl-ibt-content` (consultada), alcance: formato de las tareas

**Pasaje `dp1` — Notice to all residents of Maple Court** (112 palabras)

> Water service will be turned off on Thursday, March 12, from 9:00 a.m. to 3:00 p.m., while workers replace the main pipe. Before the work starts, please fill a few bottles with water for drinking and cooking.
>
> Residents may not use the washing machines in the basement during the work, because they will be disconnected. When the water comes back, it may look brown for a few minutes; let it run until it is clear.
>
> If you have a medical need for water during these hours, call the building office by Tuesday so we can deliver bottled water to your door.
>
> Thank you for your patience.
> Building Management

**Pasaje `dp2` — Trees and Summer Heat in Cities** (141 palabras)

> On hot afternoons, a city street lined with trees can feel much cooler than a street with no trees. Researchers who study urban heat say this difference is not only a feeling. Trees block sunlight before it reaches the pavement, and they release water vapor through their leaves, which cools the air around them. In one measurement on a summer afternoon, a sidewalk under trees was several degrees cooler than a sidewalk in full sun.
>
> Because of results like these, several cities have started programs to plant more trees in low-income neighborhoods, where there are usually fewer parks. However, trees are not a quick solution. A young tree needs regular water for several years, and in dry regions that water can be expensive. For this reason, some experts argue that cities should choose species that are adapted to the local climate.

### Actividades (16)

- **`dx.r1`** · choice · `read_in_daily_life` · pool `assessment` · U2.R
  - Consigna: What should a resident with a medical need for water do?
  - `a` (✔ clave): Call the building office by Tuesday.
  - `b` (distractor): Fill some bottles on Thursday morning. — Llenar botellas es lo que todos deben hacer antes de la obra; quien tiene una necesidad médica además debe llamar.
  - `c` (distractor): Use the washing machines before 9:00 a.m. — El aviso habla de las lavadoras como una restricción, no como una solución.
  - `d` (distractor): Wait at the door until 3:00 p.m. — El agua embotellada se entrega a la puerta, pero hay que pedirla antes.
  - Explicación: «If you have a medical need for water…, call the building office by Tuesday»: la solicitud tiene un plazo (by Tuesday).
- **`dx.r2`** · choice · `read_in_daily_life` · pool `assessment` · U3.R
  - Consigna: According to the notice, what should residents do when the water comes back?
  - `a` (✔ clave): Let the water run until it is clear.
  - `b` (distractor): Fill bottles for drinking and cooking. — Eso se hace antes de que empiece la obra.
  - `c` (distractor): Call the office to report brown water. — El aviso explica que el color café es normal unos minutos; no pide reportarlo.
  - `d` (distractor): Turn on the washing machines in the basement. — El aviso no dice nada de las lavadoras después de la obra.
  - Explicación: «When the water comes back, it may look brown…; let it run until it is clear»: when marca el momento del paso.
- **`dx.r3`** · word_completion · `complete_the_words` · pool `assessment` · U8.R
  - Consigna: Complete the words in the paragraph.
  - Texto: Many people now work from home at least one day a we{{g1}}. Some say they get more do{{g2}} at home because there are fewer interruptions. Oth{{g3}} miss talking to their coworkers and sometimes feel isol{{g4}}.
  - `g1` (se ve «we»): `week`
  - `g2` (se ve «do»): `done`
  - `g3` (se ve «Oth»): `Others`
  - `g4` (se ve «isol»): `isolated`
  - Explicación: week («one day a week»), done («get more done», terminar más trabajo), Others (contrasta con «Some») e isolated (aislado).
- **`dx.r4`** · choice · `read_academic_passage` · pool `assessment` · U5.R
  - Consigna: What is the main idea of the passage?
  - `a` (✔ clave): Trees can make city streets cooler, but planting them takes planning.
  - `b` (distractor): Cities should build fewer sidewalks in low-income neighborhoods. — Las aceras aparecen solo en la medición; el texto no propone construir menos.
  - `c` (distractor): Young trees grow faster in dry regions. — El texto dice que en regiones secas regarlos es caro, no que crezcan más rápido.
  - `d` (distractor): Water vapor is the main cause of summer heat. — El vapor de agua que liberan las hojas enfría el aire; no causa el calor.
  - Explicación: El primer párrafo explica por qué los árboles enfrían la calle y el segundo, que no son una solución rápida: la idea principal une ambas partes.
- **`dx.r5`** · choice · `read_academic_passage` · pool `assessment` · U5.R
  - Consigna: The word "adapted" in the last sentence is closest in meaning to
  - `a` (✔ clave): suited
  - `b` (distractor): imported — Traer especies de otro lugar es casi lo contrario de lo que se recomienda.
  - `c` (distractor): protected — El texto no habla de proteger a los árboles.
  - `d` (distractor): watered — El riego es el problema que se quiere evitar, no el sentido de la palabra.
  - Explicación: «Species that are adapted to the local climate» son especies que se ajustan (suited) al clima del lugar, por eso necesitan menos agua.
- **`dx.r6`** · choice · `read_academic_passage` · pool `assessment` · U7.R
  - Consigna: Which sentence from the passage gives evidence that trees cool city streets?
  - `a` (✔ clave): In one measurement on a summer afternoon, a sidewalk under trees was several degrees cooler than a sidewalk in full sun.
  - `b` (distractor): For this reason, some experts argue that cities should choose species that are adapted to the local climate. — Es una recomendación de expertos, no un dato que pruebe el enfriamiento.
  - `c` (distractor): However, trees are not a quick solution. — Es una afirmación del autor sobre los límites de la solución.
  - `d` (distractor): On hot afternoons, a city street lined with trees can feel much cooler than a street with no trees. — Describe una sensación; el texto dice justamente que hace falta algo más que la sensación.
  - Explicación: La evidencia es una medición concreta (dos aceras comparadas); las otras opciones son sensaciones, afirmaciones o recomendaciones.
- **`dx.l1`** · choice · `listen_announcement` · pool `assessment` · U1.L
  - Consigna: What are customers asked to do?
  - `a` (✔ clave): Pay for their items with a cashier.
  - `b` (distractor): Use the self-checkout machines. — El aviso dice que hoy no funcionan.
  - `c` (distractor): Come back before eight a.m. — A las ocho de la mañana abren mañana; no es una instrucción para hoy.
  - `d` (distractor): Leave their items at the entrance. — Piden llevar los artículos a las cajas, al frente de la tienda.
  - Ayudas: transcripción
  - Explicación: «The self-checkout machines are not working tonight, so please pay with a cashier»: la instrucción va después de please.
- **`dx.l2`** · choice · `listen_choose_response` · pool `assessment` · U2.L
  - Consigna: Choose the best response.
  - `a` (✔ clave): Sorry, which building do you mean?
  - `b` (distractor): Yes, I moved to a new apartment last year. — Toma «moved» en otro sentido y no responde al aviso.
  - `c` (distractor): The meeting was very long. — Habla de una reunión pasada, no del cambio de lugar.
  - `d` (distractor): I can help you build it. — Confunde «building» (edificio) con el verbo build.
  - Ayudas: transcripción
  - Explicación: «The other building» es ambiguo si hay varios edificios: pedir aclaración («which building do you mean?») es la respuesta adecuada.
- **`dx.l3`** · choice · `listen_conversation` · pool `assessment` · U4.L
  - Consigna: Why does Lucía not want to go to the Italian place?
  - `a` (✔ clave): It is too noisy on Fridays.
  - `b` (distractor): It is too far from the office. — Martín dice que está cerca.
  - `c` (distractor): It is too expensive for the team. — El precio es el problema del restaurante peruano.
  - `d` (distractor): It does not accept group bookings. — No se dice nada de reservas en el lugar italiano.
  - Ayudas: transcripción
  - Explicación: Lucía da su razón con un ejemplo: «it's really noisy on Fridays. Last time we could hardly hear each other».
- **`dx.l4`** · choice · `listen_conversation` · pool `assessment` · U6.L
  - Consigna: What does Martín propose to solve the problem with the price?
  - `a` (✔ clave): Asking the restaurant for a group menu.
  - `b` (distractor): Going back to the Italian place. — Ya la descartaron por el ruido.
  - `c` (distractor): Moving the dinner to another day. — Nadie propone cambiar el día.
  - `d` (distractor): Inviting fewer people to the dinner. — No se habla de invitar a menos personas.
  - Ayudas: transcripción
  - Explicación: «Why don't we ask them for a group menu?» es la propuesta; la condición es que cueste menos de treinta dólares por persona.
- **`dx.w1`** · sentence_order · `build_a_sentence` · pool `assessment` · U1.W
  - Consigna: Ask a classmate if they know when the library opens.
  - Orden aceptado 1: Do you know / when / the library / opens?
  - Explicación: Después de «Do you know when», va sujeto + verbo: «the library opens», sin does.
- **`dx.w2`** · sentence_order · `build_a_sentence` · pool `assessment` · U3.W
  - Consigna: Tell a friend what you did yesterday after work.
  - Orden aceptado 1: After I / finished work, / I went / to the gym.
  - Explicación: «After I finished work» marca el primer evento y la coma lo separa de lo que pasó después: «I went to the gym».
- **`dx.e1`** · short_writing · `write_an_email` · pool `assessment` · U2.W
  - Consigna: You ordered a desk online, but it arrived with a broken leg. Write an email to the store. In your email: say what you ordered and when; describe the problem; say what you would like the store to do.
  - 50–110 palabras · rúbrica `email` · respuesta modelo de 72 palabras
  - Modelo: Dear Customer Service, I am writing about a desk that I ordered on your website on May 3 (order 4821). It arrived yesterday, but one of the legs is broken, so I cannot use it. I have attached two photos of the damage. Could you please send me a new leg or replace the desk? If that is not possible, I would like a full refund. Thank you, Sofía Ramírez
  - Comentario: Cubre los tres puntos en orden: qué pidió y cuándo (con un número de pedido), el problema concreto y lo que solicita, con una alternativa. El tono es firme y cortés.
- **`dx.e2`** · short_writing · `write_academic_discussion` · pool `assessment` · U5.W
  - Consigna: Your professor asks: "Should universities require all students to take a public speaking course?" Ana writes: "Yes. Most jobs require presenting ideas, and many students are afraid of speaking in public." Kevin writes: "No. Students should choose their own courses; a required course takes time away from their major." Write a post that gives your opinion and supports it. Respond to at least one of your classmates.
  - 70–140 palabras · rúbrica `academic-discussion` · respuesta modelo de 99 palabras
  - Modelo: I agree with Ana that universities should require a public speaking course, but I understand Kevin's concern about time. In my experience, presenting is part of almost every job, even technical ones. For example, my cousin is an engineer, and she has to explain her projects to clients every month. A short course would help students like her feel less nervous. To respond to Kevin, the course does not have to be long: a one-semester class with two hours a week would not take much time from a major, and the skill would be useful in every other class.
  - Comentario: Toma postura en la primera oración y reconoce la otra idea. Apoya la opinión con una razón general y un ejemplo concreto, y responde a la objeción de Kevin con una propuesta (un curso corto).
- **`dx.s1`** · recorded_speaking · `take_an_interview` · pool `assessment` · U1.S
  - Pregunta: Can you tell me about the place where you live? (preparación 15 s, respuesta 45 s)
  - Rúbrica `interview` · modelo: I live in a small apartment in the center of Mérida, close to the main square. It has two bedrooms, and I share it with my brother. What I like most is that I can walk to work in ten minutes. The only problem is the noise on weekends, because there are many restaurants on my street.
  - Comentario: Responde directo (dónde vive), agrega detalles (tamaño, con quién) y cierra con algo que le gusta y algo que no, con una razón.
- **`dx.s2`** · recorded_speaking · `take_an_interview` · pool `assessment` · U4.S
  - Pregunta: Some people prefer to study in a group, and others prefer to study alone. Which do you prefer, and why? (preparación 15 s, respuesta 45 s)
  - Rúbrica `interview` · modelo: I prefer to study alone, at least most of the time. When I study with a group, we often start talking about other things, and I lose time. Alone, I can go at my own speed and repeat the parts that are difficult for me. That said, before an exam I sometimes meet with one or two classmates to compare answers, because they notice mistakes I don't see.
  - Comentario: Toma una postura clara, la defiende con dos razones y reconoce un caso en el que la otra opción también sirve: es una respuesta matizada y coherente.

### Lint

- warning `pending_audio` [dx.l1]: audio sin revisar: inicial-aviso (bloquea aprobar y publicar)
- warning `pending_audio` [dx.l2]: audio sin revisar: inicial-respuesta (bloquea aprobar y publicar)
- warning `pending_audio` [dx.l3]: audio sin revisar: inicial-conversacion (bloquea aprobar y publicar)
- warning `pending_audio` [dx.l4]: audio sin revisar: inicial-conversacion (bloquea aprobar y publicar)

### Guiones de audio

- `inicial-aviso` · sin MP3 (se genera en G2) · sin revisar
  - Narrator: Good evening, shoppers. The store will close in fifteen minutes, at nine o'clock.
  - Narrator: Please bring your items to the registers at the front of the store.
  - Narrator: The self-checkout machines are not working tonight, so please pay with a cashier.
  - Narrator: We will open again tomorrow at eight a.m. Thank you for shopping with us.
- `inicial-respuesta` · sin MP3 (se genera en G2) · sin revisar
  - A: Just so you know, the meeting has moved to the other building.
- `inicial-conversacion` · sin MP3 (se genera en G2) · sin revisar
  - Lucía: Martín, have you decided where we should have the team dinner on Friday?
  - Martín: I was thinking about the Italian place near the office. It's close, so nobody needs to drive.
  - Lucía: It's close, but it's really noisy on Fridays. Last time we could hardly hear each other.
  - Martín: That's true. What about the Peruvian restaurant on Fifth Street? It's quieter.
  - Lucía: I like that one, but it's a bit expensive for the whole team.
  - Martín: Then why don't we ask them for a group menu? If the price per person is under thirty dollars, we can go there.
  - Lucía: Good idea. I'll call them this afternoon.
  - Martín: Great. And let's book for seven thirty, so people can come straight from work.

### Lista de revisión (contrato §12)

- [ ] 1. El objetivo es observable y coincide con el mapa.
- [ ] 2. La explicación es correcta y cada regla tiene fuente y alcance.
- [ ] 3. Los ejemplos son originales y no ambiguos.
- [ ] 4. Las claves están verificadas y las variantes válidas, listadas.
- [ ] 5. Los distractores son plausibles y no hay dos respuestas defendibles.
- [ ] 6. El apoyo en español aparece solo donde se permite.
- [ ] 7. El audio coincide con el guion y se entiende.
- [ ] 8. Hay alternativas de accesibilidad (transcripción, texto alternativo).
- [ ] 9. No hay marcadores pendientes y el lint está limpio.
