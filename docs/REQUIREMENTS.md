# Requirements Document

## Functional Requirements

### User Management
- Users can register with email/password
- Users can login with credentials
- Two roles: Admin, Student

### Course Navigation
- Display courses organized by category
- Each course contains 15-30 classes
- URL pattern: `/cursos/{course-slug}/clase-{number}-{topic}`

### Class Content
- Render markdown in PCRE format
- Display quiz (8-15 questions variable)
- Show hints per question
- Feedback:
  - ✅ Green + explanation if correct
  - ❌ Red + "Sigue intentando" if wrong

### Progress Tracking
- Mark class as completed
- Display progress per course
- No storage of individual answers

## Non-Functional Requirements

### Performance
- Page load < 2s (LCP)
- Quiz interaction < 100ms

### Security
- JWT in HttpOnly cookies
- Password hashing (bcrypt)
- HTTPS only

### Scale
- Current: 10 users
- Designed for: 100-500 users

## Out of Scope (MVP)
- Analytics
- Video/images in markdown
- Admin UI for content
- Multi-language
