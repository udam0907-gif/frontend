@echo off
chcp 65001 >nul
echo ============================================
echo  [새 PC] R&D 비용 집행 관리 시스템 설치
echo ============================================

set PROJECT_DIR=%~dp0
set TRANSFER_DIR=%PROJECT_DIR%transfer

echo.
echo 사전 확인 중...

REM transfer 폴더 확인
if not exist "%TRANSFER_DIR%\db_backup.sql" (
    echo [오류] transfer\db_backup.sql 파일이 없습니다.
    echo   transfer\ 폴더를 이 폴더 안에 복사했는지 확인하세요.
    pause & exit /b 1
)
if not exist "%TRANSFER_DIR%\storage_backup.tar.gz" (
    echo [오류] transfer\storage_backup.tar.gz 파일이 없습니다.
    pause & exit /b 1
)

REM backend/.env 파일 확인
if not exist "%PROJECT_DIR%backend\.env" (
    echo [오류] backend\.env 파일이 없습니다.
    echo   backend\.env.example 을 복사해서 값을 채워주세요.
    pause & exit /b 1
)

REM 루트 .env 자동 생성 (없으면 backend/.env 에서 비밀번호 추출)
if not exist "%PROJECT_DIR%.env" (
    echo      루트 .env 없음 — backend\.env 에서 비밀번호 추출 중...
    powershell -Command ^
        "$content = Get-Content '%PROJECT_DIR%backend\.env' -Raw;" ^
        "if ($content -match 'postgresql[^:]*://[^:]+:([^@]+)@') {" ^
        "    $pw = $Matches[1];" ^
        "    Set-Content -Path '%PROJECT_DIR%.env' -Encoding utf8 -Value " ^
        "        ('POSTGRES_USER=postgres' + [char]10 + 'POSTGRES_PASSWORD=' + $pw + [char]10 + 'POSTGRES_DB=rnd_expense_db' + [char]10 + 'BACKEND_PORT=8000' + [char]10 + 'FRONTEND_PORT=3001' + [char]10 + 'NEXT_PUBLIC_API_URL=http://localhost:8000');" ^
        "    Write-Host '     완료: 루트 .env 생성';" ^
        "} else { Write-Host '[경고] DATABASE_URL 파싱 실패 — 루트 .env 를 직접 만들어주세요.'; }"
)

echo      OK: 파일 확인 완료

echo.
echo [1단계] Docker 서비스 시작 (postgres만 먼저)...
docker compose up -d postgres
if %errorlevel% neq 0 (
    echo [오류] docker compose 실패. Docker Desktop이 실행 중인지 확인하세요.
    pause & exit /b 1
)

echo      postgres 준비 대기 중...
:wait_postgres
docker exec rnd_postgres pg_isready -U postgres >nul 2>&1
if %errorlevel% neq 0 (
    timeout /t 2 /nobreak >nul
    goto wait_postgres
)
echo      postgres 준비 완료!

echo.
echo [2단계] DB 복원 중...
docker cp "%TRANSFER_DIR%\db_backup.sql" rnd_postgres:/tmp/db_backup.sql
docker exec rnd_postgres psql -U postgres -d rnd_expense_db -f /tmp/db_backup.sql >nul 2>&1
if %errorlevel% neq 0 (
    echo [경고] DB 복원 중 일부 오류가 발생했을 수 있습니다 (이미 존재하는 객체 등은 무시 가능).
)
echo      완료: DB 복원

echo.
echo [3단계] 전체 서비스 시작...
docker compose up -d
echo      backend/frontend 시작 중...
timeout /t 10 /nobreak >nul

echo.
echo [4단계] Storage 복원 중...
docker cp "%TRANSFER_DIR%\storage_backup.tar.gz" rnd_backend:/tmp/storage_backup.tar.gz
docker exec rnd_backend tar xzf /tmp/storage_backup.tar.gz -C /app/storage
if %errorlevel% neq 0 (
    echo [오류] Storage 복원 실패.
    pause & exit /b 1
)
echo      완료: Storage 복원

echo.
echo [5단계] Backend 재시작...
docker compose restart backend
echo      재시작 완료

echo.
echo ============================================
echo  설치 완료!
echo  - 프론트엔드: http://localhost:3001
echo  - 백엔드 API: http://localhost:8000
echo  - API 문서:   http://localhost:8000/docs
echo ============================================
pause
