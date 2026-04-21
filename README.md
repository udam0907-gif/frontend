# R&D 비용 집행 관리 시스템

연구과제 비용집행 문서 자동화 플랫폼 (FastAPI + Next.js + PostgreSQL)

---

## 빠른 시작 (Docker Compose)

### 1. 저장소 클론

```bash
git clone https://github.com/udam0907-gif/frontend.git
cd frontend
```

### 2. 환경 변수 설정

```bash
# 루트 .env (포트 등 Docker Compose 설정)
cp .env.example .env

# 백엔드 .env (API 키 등 서버 설정)
cp backend/.env.example backend/.env
```

`backend/.env` 파일을 열어 아래 항목을 반드시 채우세요:

| 항목 | 설명 |
|------|------|
| `ANTHROPIC_API_KEY` | https://console.anthropic.com 에서 발급 |
| `SECRET_KEY` | 32자 이상 임의 문자열 |
| `LAW_API_OC` | https://law.go.kr 가입 이메일 (선택) |

### 3. 실행

```bash
docker compose up --build
```

| 서비스 | URL |
|--------|-----|
| 프론트엔드 | http://localhost:3001 |
| 백엔드 API | http://localhost:8000 |
| API 문서 | http://localhost:8000/docs |

### 4. DB 마이그레이션

처음 실행 시 또는 스키마 변경 후:

```bash
docker exec rnd_backend alembic upgrade head
```

---

## 포트 변경

`.env` 파일에서 변경 가능합니다:

```env
FRONTEND_PORT=3001
BACKEND_PORT=8000
POSTGRES_PORT=5432
```

---

## 개발 환경 (로컬 직접 실행)

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # 편집 후
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install --legacy-peer-deps
npm run dev
```

---

## 기술 스택

- **Backend**: Python 3.12 · FastAPI · SQLAlchemy (async) · Alembic · pgvector
- **Frontend**: Next.js 14 · TypeScript · Tailwind CSS · shadcn/ui · TanStack Query
- **DB**: PostgreSQL 16 + pgvector
- **AI**: Anthropic Claude (claude-sonnet-4-6)
- **문서 생성**: docxtpl (DOCX 서식 직접 채움)
