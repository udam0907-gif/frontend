#!/bin/bash
# .claude/hooks/pre-bash.sh
# 위험 명령 실행 전 차단 훅
#
# Claude Code가 Bash 도구를 실행하기 직전에 호출된다.
# stdin으로 JSON {"command": "..."}을 받음.
# exit 0 → 허용, exit 2 → 차단 (사용자에게 stderr 메시지 표시)

# Read command from stdin JSON
INPUT=$(cat)
PYTHON_CMD=$(which py 2>/dev/null || which python3 2>/dev/null || which python 2>/dev/null || echo "")
if [ -z "$PYTHON_CMD" ]; then
    exit 0
fi
COMMAND=$(echo "$INPUT" | "$PYTHON_CMD" -c "import sys, json; print(json.load(sys.stdin).get('tool_input', {}).get('command', ''))" 2>/dev/null)

# 빈 명령이면 통과 (다른 도구일 수 있음)
if [ -z "$COMMAND" ]; then
    exit 0
fi

# 위험 패턴 정의
DANGEROUS_PATTERNS=(
    'rm[[:space:]]+-rf'
    'rm[[:space:]]+-fr'
    'rm[[:space:]]+-r[[:space:]]+/'
    'docker[[:space:]]+volume[[:space:]]+rm'
    'docker[[:space:]]+compose[[:space:]]+down[[:space:]]+.*-v'
    'DROP[[:space:]]+TABLE'
    'DROP[[:space:]]+DATABASE'
    'TRUNCATE[[:space:]]+TABLE'
    'TRUNCATE[[:space:]]+[a-zA-Z_]'
    'git[[:space:]]+push[[:space:]]+.*--force'
    'git[[:space:]]+push[[:space:]]+.*-f'
    'git[[:space:]]+reset[[:space:]]+--hard'
    'git[[:space:]]+clean[[:space:]]+.*-f'
    'alembic[[:space:]]+downgrade'
    '>[[:space:]]*/dev/sda'
    'mkfs\.'
    'dd[[:space:]]+if=.*of=/dev/'
    ':\(\)\{[[:space:]]*:|:&[[:space:]]*\};'
)

# 보호 영역 직접 수정 시도 차단
PROTECTED_PATHS=(
    'backend/app/services/rag_service\.py'
    'backend/app/services/legal_'
    'backend/app/services/qa_orchestrator\.py'
    'backend/app/services/question_understanding'
    'backend/app/api/v1/rcms'
    'backend/app/models/rcms_'
    'backend/app/models/legal_'
    'backend/migrations/versions/001_'
    'backend/migrations/versions/002_'
)

# 위험 패턴 검사
for pattern in "${DANGEROUS_PATTERNS[@]}"; do
    if echo "$COMMAND" | grep -qE "$pattern"; then
        cat >&2 <<EOF
🚨 위험 명령 차단됨

명령어: $COMMAND
매치된 패턴: $pattern

이 명령은 시스템 레벨 hook에 의해 차단되었습니다.

진행하려면:
1. 사용자에게 명시적 승인 받기
2. 백업 수행
3. 사용자가 직접 실행

자동 실행은 절대 허용되지 않습니다.
EOF
        exit 2
    fi
done

# 보호 영역 직접 수정 (rm, mv, > 리다이렉션 등) 차단
for path in "${PROTECTED_PATHS[@]}"; do
    if echo "$COMMAND" | grep -qE "(rm|mv|cp).*$path"; then
        cat >&2 <<EOF
🚨 보호 영역 침범 시도 차단

명령어: $COMMAND
보호 파일 경로: $path

이 영역은 RCMS 완성 영역으로 수정/삭제가 금지됩니다.
EOF
        exit 2
    fi

    # > 또는 >>로 보호 파일에 쓰는 시도 차단
    if echo "$COMMAND" | grep -qE ">>?[[:space:]]*[^|&]*$path"; then
        cat >&2 <<EOF
🚨 보호 영역 쓰기 시도 차단

명령어: $COMMAND
대상 파일: $path

이 영역은 수정 금지입니다.
EOF
        exit 2
    fi
done

# 모든 검사 통과
exit 0
