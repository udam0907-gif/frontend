@echo off
chcp 65001 >nul
echo ============================================
echo  [현재 PC] Transfer 패키지 생성
echo ============================================

set TRANSFER_DIR=%~dp0transfer
if not exist "%TRANSFER_DIR%" mkdir "%TRANSFER_DIR%"

echo.
echo [1/2] DB 백업 중...
docker exec rnd_postgres pg_dump -U postgres rnd_expense_db > "%TRANSFER_DIR%\db_backup.sql"
if %errorlevel% neq 0 (
    echo [오류] DB 백업 실패. 컨테이너가 실행 중인지 확인하세요.
    pause & exit /b 1
)
echo      완료: transfer\db_backup.sql

echo.
echo [2/2] Storage 백업 중 (PowerShell 사용)...
powershell -Command "docker run --rm -v cm_app_storage_data:/data alpine sh -c 'tar czf - -C /data .' | Set-Content -Encoding Byte '%TRANSFER_DIR%\storage_backup.tar.gz'"
if %errorlevel% neq 0 (
    echo [오류] Storage 백업 실패.
    pause & exit /b 1
)
echo      완료: transfer\storage_backup.tar.gz

echo.
echo ============================================
echo  완료! transfer\ 폴더를 새 PC로 복사하세요.
echo  (USB 또는 네트워크 공유로 전달)
echo ============================================
pause
