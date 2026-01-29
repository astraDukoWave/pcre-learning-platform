from app.db.base import SessionLocal
from app.models import Course, Class, Quiz, Question
import json

def seed_data():
    db = SessionLocal()
    
    try:
        # Check if data already exists
        existing_courses = db.query(Course).count()
        if existing_courses > 0:
            print("✅ Data already seeded")
            return
        
        # Create course
        course = Course(
            slug="ingles-b1-expresiones-tiempo",
            title="Curso de Inglés Intermedio B1: Expresiones de Tiempo y Cantidad",
            description="Desarrolla tus habilidades intermedias en inglés B1 enfocándote en expresiones de tiempo y cantidad.",
            order=1
        )
        db.add(course)
        db.commit()
        db.refresh(course)
        print(f"✅ Course created: {course.title}")
        
        # Create class
        class_ = Class(
            course_id=course.id,
            slug="clase-10-comparativos",
            title="Adjetivos Comparativos en Inglés: Uso y Reglas",
            order=10,
            markdown_content="""# Adjetivos Comparativos en Inglés

## 🧩 P — PATTERN (El patrón visual que debes reconocer)

**Idea núcleo:**
> Comparamos SOLO 2 cosas usando un adjetivo modificado + THAN.

**Patrón base universal:**
```
[Thing A] + is + [COMPARATIVE ADJ] + THAN + [Thing B]
```

**Ejemplo mental fijo:**
> A phone is **bigger than** a wallet.

## 🧠 C — CONCEPT (Qué es y para qué sirve)

Un *comparative adjective* muestra que una cosa tiene MÁS o MENOS de una cualidad que otra.

**Para qué sirve:**
- Comparar personas
- Comparar objetos
- Comparar lugares

> Si no hay dos cosas → no hay comparativo.

## 🛠️ R — RULES (Las 4 reglas reales que importan)

### 1) Adjetivos CORTOS → `-ER`
- small → smaller
- fast → faster
- easy → easier

### 2) Adjetivos LARGOS → `MORE + adj`
- modern → more modern
- beautiful → more beautiful

### 3) Irregulares
- good → better
- bad → worse

### 4) THAN es obligatorio
❌ Wrong: A car is faster a bike  
✅ Correct: A car is faster **than** a bike

## 🧪 E — EXAMPLES

- A dog is **bigger than** a cat.
- This movie is **more interesting than** the book.
- Today is **better than** yesterday.
""",
            has_quiz=True
        )
        db.add(class_)
        db.commit()
        db.refresh(class_)
        print(f"✅ Class created: {class_.title}")
        
        # Create quiz
        quiz = Quiz(class_id=class_.id)
        db.add(quiz)
        db.commit()
        db.refresh(quiz)
        print(f"✅ Quiz created for class: {class_.title}")
        
        # Create questions
        questions = [
            Question(
                quiz_id=quiz.id,
                text='Completa la frase: "My new phone is _____ than my old one."',
                options=json.dumps(["fast", "more fast", "faster", "fastest"]),
                correct_index=2,
                hint="Recuerda la regla para las palabras cortas como 'big'.",
                explanation="Usa la forma comparativa correcta para un adjetivo corto ('fast' → 'faster') y la palabra de conexión 'than'.",
                order=1
            ),
            Question(
                quiz_id=quiz.id,
                text='¿Cuál de estas oraciones está escrita correctamente?',
                options=json.dumps([
                    "My city is bigger that yours.",
                    "My city is more big than yours.",
                    "My city is bigger than yours.",
                    "My city is big than yours."
                ]),
                correct_index=2,
                hint="Verifica el uso correcto del comparativo y 'than'.",
                explanation="Usa la forma comparativa correcta para un adjetivo corto ('bigger') y la palabra de conexión 'than'.",
                order=2
            ),
            Question(
                quiz_id=quiz.id,
                text='Selecciona el comparativo correcto de "beautiful":',
                options=json.dumps([
                    "beautifuler",
                    "more beautiful",
                    "beautifuller",
                    "most beautiful"
                ]),
                correct_index=1,
                hint="Los adjetivos largos usan 'more' + adjetivo.",
                explanation="'Beautiful' es un adjetivo largo (3 sílabas), por lo tanto usa 'more beautiful', no '-er'.",
                order=3
            ),
        ]
        
        for question in questions:
            db.add(question)
        
        db.commit()
        print(f"✅ {len(questions)} questions created")
        print("\n🎉 Seed data created successfully!")
        
    except Exception as e:
        print(f"❌ Error seeding data: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()
