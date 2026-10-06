-- Seed del esquema legado (816c80672425), equivalente a app/db/seed.py @ 133c5e3.
-- Lo usa el chequeo de migraciones: las tablas legadas y `users` sobreviven a head.
-- Sin datos reales: correos de example.com y un hash de contraseña ficticio.
INSERT INTO courses (id, slug, title, description, "order")
VALUES (1, 'ingles-b1-expresiones-tiempo', 'Curso de ejemplo B1 (legado)',
        'Contenido legado de la fase 1.', 1);

INSERT INTO classes (id, course_id, slug, title, "order", markdown_content, has_quiz)
VALUES (1, 1, 'clase-10-comparativos', 'Adjetivos comparativos (legado)', 10,
        '# Adjetivos comparativos (legado)', true);

INSERT INTO quizzes (id, class_id) VALUES (1, 1);

INSERT INTO questions (id, quiz_id, text, options, correct_index, hint, explanation, "order") VALUES
  (1, 1, 'My new phone is _____ than my old one.', '["fast", "more fast", "faster", "fastest"]', 2,
   'Adjetivo corto.', '"fast" -> "faster".', 1),
  (2, 1, 'Which sentence is correct?', '["My city is bigger that yours.", "My city is more big than yours.", "My city is bigger than yours.", "My city is big than yours."]', 2,
   'Comparativo y "than".', '"bigger than".', 2),
  (3, 1, 'Comparative of "beautiful":', '["beautifuler", "more beautiful", "beautifuller", "most beautiful"]', 1,
   'Adjetivo largo.', '"more beautiful".', 3);

SELECT setval('courses_id_seq', 1);
SELECT setval('classes_id_seq', 1);
SELECT setval('quizzes_id_seq', 1);
SELECT setval('questions_id_seq', 3);

INSERT INTO users (id, email, password_hash, role)
VALUES ('6f1c2a7e-0d4b-4a59-9a3e-2b7d9c1e5f00', 'Legacy.Admin@Example.com',
        'legacy-placeholder-not-a-hash', 'admin');
