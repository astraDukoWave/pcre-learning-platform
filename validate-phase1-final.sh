#!/bin/bash
echo "🔍 VALIDACIÓN FINAL - FASE 1"
echo "========================================"
echo ""

cd apps/backend

# Test 1: Contenedores
echo "📦 Test 1: Docker Containers"
if docker ps | grep -q "pcre_backend\|pcre_postgres"; then
    echo "   ✅ Containers running"
else
    echo "   ❌ Containers not running"
    exit 1
fi
echo ""

# Test 2: Health
echo "🏥 Test 2: Health Endpoint"
HEALTH=$(curl -s http://localhost:8000/health)
if echo "$HEALTH" | grep -q "ok"; then
    echo "   ✅ Health OK: $HEALTH"
else
    echo "   ❌ Health failed"
    exit 1
fi
echo ""

# Test 3: Courses endpoint
echo "📚 Test 3: Courses API"
COURSES=$(curl -s http://localhost:8000/api/v1/courses)
if echo "$COURSES" | grep -q "ingles-b1"; then
    echo "   ✅ Courses endpoint OK"
    echo "   Found: $(echo "$COURSES" | grep -o '"title":"[^"]*"' | head -1)"
else
    echo "   ❌ Courses endpoint failed"
    exit 1
fi
echo ""

# Test 4: Database tables
echo "🗄️  Test 4: Database Schema"
TABLES=$(docker-compose exec -T db psql -U dev_user -d dev_db -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_name IN ('courses', 'classes', 'quizzes', 'questions');" 2>/dev/null | xargs)
if [ "$TABLES" = "4" ]; then
    echo "   ✅ 4 tables in PostgreSQL"
else
    echo "   ❌ Expected 4 tables, found: $TABLES"
    exit 1
fi
echo ""

# Test 5: Seed data
echo "🌱 Test 5: Seed Data"
COURSE_COUNT=$(docker-compose exec -T db psql -U dev_user -d dev_db -t -c "SELECT COUNT(*) FROM courses;" 2>/dev/null | xargs)
CLASS_COUNT=$(docker-compose exec -T db psql -U dev_user -d dev_db -t -c "SELECT COUNT(*) FROM classes;" 2>/dev/null | xargs)
QUESTION_COUNT=$(docker-compose exec -T db psql -U dev_user -d dev_db -t -c "SELECT COUNT(*) FROM questions;" 2>/dev/null | xargs)

if [ "$COURSE_COUNT" -ge "1" ] && [ "$CLASS_COUNT" -ge "1" ] && [ "$QUESTION_COUNT" -ge "3" ]; then
    echo "   ✅ Seed data loaded"
    echo "      - Courses: $COURSE_COUNT"
    echo "      - Classes: $CLASS_COUNT"
    echo "      - Questions: $QUESTION_COUNT"
else
    echo "   ❌ Seed data incomplete"
    exit 1
fi
echo ""

# Test 6: Class detail with quiz
echo "📝 Test 6: Class with Quiz"
CLASS_DATA=$(curl -s "http://localhost:8000/api/v1/courses/ingles-b1-expresiones-tiempo/classes/clase-10-comparativos")
if echo "$CLASS_DATA" | grep -q "markdown_content" && echo "$CLASS_DATA" | grep -q "quiz"; then
    echo "   ✅ Class endpoint with quiz OK"
    QUESTION_COUNT_API=$(echo "$CLASS_DATA" | grep -o '"text":' | wc -l)
    echo "      - Questions in API: $QUESTION_COUNT_API"
else
    echo "   ❌ Class endpoint failed"
    exit 1
fi
echo ""

# Test 7: Migration applied
echo "🔄 Test 7: Alembic Migration"
MIGRATION=$(docker-compose exec -T backend alembic current 2>/dev/null | grep "bc0bb9a48e10")
if [ -n "$MIGRATION" ]; then
    echo "   ✅ Migration applied: bc0bb9a48e10"
else
    echo "   ❌ Migration not applied"
    exit 1
fi
echo ""

echo "========================================"
echo "🎉 FASE 1 COMPLETADA EXITOSAMENTE 🎉"
echo "========================================"
echo ""
echo "📊 Backend Status:"
echo "   🌐 FastAPI:    http://localhost:8000"
echo "   📖 Swagger:    http://localhost:8000/docs"
echo "   🐘 PostgreSQL: Running on port 5432"
echo ""
echo "📁 Data Summary:"
echo "   - Tables:   courses, classes, quizzes, questions"
echo "   - Courses:  $COURSE_COUNT"
echo "   - Classes:  $CLASS_COUNT"
echo "   - Questions: $QUESTION_COUNT"
echo ""
echo "✅ Ready for Phase 2: Frontend Development"
