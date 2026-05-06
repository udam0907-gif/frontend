"""
M2.6 Phase 2a — 내부 서식 템플릿 seed script

역할:
- 3개 docx v2/v3 파일을 /app/storage/templates/ 에 복사
- 기존 파일 .bak 백업
- templates 테이블 in-place 업데이트:
    becdb521: 지출결의서 (expense_resolution, docx)
    abbad44f: 검수확인서 (inspection_confirmation, docx)
    1da3bb3e: 품의서 (other → purchase_request, docx)
- render_profile = {"render_strategy": "docxtpl"} 세팅

실행:
    docker exec rnd_backend python3 /app/scripts/seed_m26_internal_templates.py
"""
import hashlib
import json
import os
import shutil
import sys

import psycopg2

# ── 경로 설정 ──────────────────────────────────────────────────────────────
STAGING_DIR = "/app/scripts/uploads_staging"
STORAGE_DIR = "/app/storage/templates"

_raw_dsn = os.environ.get("DATABASE_URL", "postgresql://postgres:password@postgres:5432/rnd_expense_db")
# asyncpg driver prefix → psycopg2 compatible
DB_DSN = _raw_dsn.replace("postgresql+asyncpg://", "postgresql://")

# template id → (docx filename, document_type after update)
TARGETS = {
    "becdb521-0000-0000-0000-000000000000": ("지출결의서_v2.docx", "expense_resolution"),
    "abbad44f-0000-0000-0000-000000000000": ("검수확인서_v3.docx", "inspection_confirmation"),
    "1da3bb3e-0000-0000-0000-000000000000": ("품의서_v2.docx", "purchase_request"),
}

RENDER_PROFILE = json.dumps({"render_strategy": "docxtpl"})


def md5_of(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def get_real_id(cur, partial_id: str) -> str | None:
    """partial_id prefix로 실제 UUID 조회"""
    cur.execute(
        "SELECT id::text FROM templates WHERE id::text LIKE %s LIMIT 1",
        (partial_id[:8] + "%",),
    )
    row = cur.fetchone()
    return row[0] if row else None


def main() -> None:
    os.makedirs(STORAGE_DIR, exist_ok=True)

    conn = psycopg2.connect(DB_DSN)
    cur = conn.cursor()

    for partial_id, (filename, new_doc_type) in TARGETS.items():
        src = os.path.join(STAGING_DIR, filename)
        if not os.path.exists(src):
            print(f"[ERROR] staging file not found: {src}", file=sys.stderr)
            sys.exit(1)

        # 실제 UUID 조회
        real_id = get_real_id(cur, partial_id)
        if not real_id:
            print(f"[ERROR] template row not found for id prefix: {partial_id[:8]}", file=sys.stderr)
            sys.exit(1)

        # 현재 file_path 조회
        cur.execute("SELECT file_path FROM templates WHERE id = %s", (real_id,))
        row = cur.fetchone()
        old_file_path: str = row[0] if row else ""

        # hash 기반 신규 경로 계산
        file_hash = md5_of(src)
        new_filename = f"{file_hash}.docx"
        dest = os.path.join(STORAGE_DIR, new_filename)
        new_file_path = f"storage/templates/{new_filename}"

        # 기존 파일 .bak 백업
        if old_file_path:
            old_abs = os.path.join("/app", old_file_path)
            if os.path.exists(old_abs):
                bak_path = old_abs + ".bak"
                shutil.copy2(old_abs, bak_path)
                print(f"  backed up: {old_abs} → {bak_path}")

        # 신규 파일 복사
        shutil.copy2(src, dest)
        print(f"  copied: {src} → {dest}")

        # DB 업데이트
        new_category = "materials"
        cur.execute(
            """
            UPDATE templates
            SET file_path = %s,
                document_type = %s,
                category_type = %s,
                render_profile = %s::jsonb
            WHERE id = %s
            """,
            (new_file_path, new_doc_type, new_category, RENDER_PROFILE, real_id),
        )
        print(f"  updated templates id={real_id[:8]}... doc_type={new_doc_type} file={new_filename}")

    conn.commit()
    cur.close()
    conn.close()

    # ── 결과 검증 ──────────────────────────────────────────────────────────
    print("\n── 최종 검증 ──")
    conn2 = psycopg2.connect(DB_DSN)
    cur2 = conn2.cursor()
    cur2.execute(
        """
        SELECT id::text, name, document_type, file_path, render_profile
        FROM templates
        WHERE document_type IN ('expense_resolution','inspection_confirmation','purchase_request')
        AND file_format = 'docx'
        ORDER BY name
        """
    )
    rows = cur2.fetchall()
    for r in rows:
        file_exists = os.path.exists(os.path.join("/app", r[3]))
        print(
            f"  id={r[0][:8]}  name={r[1]}  type={r[2]}\n"
            f"    path={r[3]}  exists={file_exists}\n"
            f"    render_profile={r[4]}"
        )
    cur2.close()
    conn2.close()
    print("\n[DONE] Phase 2a seed 완료")


if __name__ == "__main__":
    main()
