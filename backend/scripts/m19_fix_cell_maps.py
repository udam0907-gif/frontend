"""
M1.9 회귀-3: 4개 verify FAIL 수정

Fix 1. 펀디       issue_date G3 → C3  (G3 = '공 급 자' 정적 라벨)
Fix 2. 선양에스피티  A1:D1 병합 → year/month/day 전부 A1 anchor 덮어쓰기
         → issue_date_year/month/day 삭제, issue_date = "A1"
Fix 3. 아이에이치켐  issue_date + recipient_name 둘 다 H5 (정적 라벨) 오류
         → 템플릿 스캔 후 실제 셀 탐색, recipient_name 수정
         (날짜 입력칸 없는 양식이면 issue_date 제거)

실행: docker exec rnd_backend python3 /app/scripts/m19_fix_cell_maps.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, "/app")

import openpyxl


# ── 헬퍼: anchor 셀 탐색 ────────────────────────────────────────────────────

def _anchor(ws, cell_addr: str) -> str:
    """병합 셀이면 좌상단 앵커를 반환."""
    for merged in ws.merged_cells.ranges:
        if openpyxl.utils.cell.coordinate_to_tuple(cell_addr) in [
            (r, c) for r in range(merged.min_row, merged.max_row + 1)
            for c in range(merged.min_col, merged.max_col + 1)
        ]:
            return openpyxl.utils.cell.get_column_letter(merged.min_col) + str(merged.min_row)
    return cell_addr


def _scan_date_cell(template_path: str) -> str | None:
    """
    템플릿에서 날짜 입력 가능한 셀 탐색.
    '발행', '작성', '일자', '날짜' 라벨 근처의 빈 셀 또는 연도 값을 가진 셀 반환.
    None이면 날짜 입력칸 없는 양식.
    """
    wb = openpyxl.load_workbook(template_path, data_only=True)
    ws = wb.active
    date_labels = ["작성일", "작성일자", "발행일", "발행일자", "날짜", "일자"]

    for row in ws.iter_rows():
        for cell in row:
            val = str(cell.value or "").strip()
            for label in date_labels:
                if label in val:
                    # 오른쪽 셀부터 탐색
                    col = cell.column
                    r = cell.row
                    for dc in range(1, 5):
                        neighbor_col = col + dc
                        if neighbor_col > ws.max_column:
                            break
                        nc = ws.cell(row=r, column=neighbor_col)
                        nv = str(nc.value or "").strip()
                        # 빈 셀이거나 연도처럼 보이는 숫자/날짜 값이면 입력칸으로 판단
                        if nv == "" or (nv.isdigit() and 2020 <= int(nv) <= 2030):
                            anchor = _anchor(ws, nc.coordinate)
                            wb.close()
                            return anchor
    wb.close()
    return None


def _scan_recipient_cell(template_path: str) -> str | None:
    """
    '수신', '수 신', 'To:', 'TO:' 라벨 근처 빈 셀 탐색 → recipient_name 후보.
    """
    wb = openpyxl.load_workbook(template_path, data_only=True)
    ws = wb.active
    labels = ["수신", "수 신", "To:", "TO:", "귀중", "귀하", "ATTN"]

    for row in ws.iter_rows():
        for cell in row:
            val = str(cell.value or "").strip()
            for label in labels:
                if label in val:
                    col = cell.column
                    r = cell.row
                    # 같은 행 오른쪽 셀
                    for dc in range(1, 8):
                        nc = ws.cell(row=r, column=col + dc)
                        nv = str(nc.value or "").strip()
                        if nv == "":
                            anchor = _anchor(ws, nc.coordinate)
                            wb.close()
                            return anchor
    wb.close()
    return None


# ── DB 패치 ─────────────────────────────────────────────────────────────────

async def fix_vendor_cell_map(vendor_name: str, patch_fn) -> None:
    """patch_fn(cell_map: dict) → dict"""
    # 지연 import (컨테이너 환경 의존)
    from sqlalchemy import select
    from app.database import AsyncSessionLocal
    from app.models.vendor import Vendor
    from app.models.vendor_pool import VendorTemplatePool

    async with AsyncSessionLocal() as db:
        vendor = (await db.execute(
            select(Vendor).where(Vendor.name == vendor_name)
        )).scalar_one_or_none()
        if not vendor:
            print(f"  ❌ vendor '{vendor_name}' not found")
            return

        pool = (await db.execute(
            select(VendorTemplatePool).where(
                VendorTemplatePool.vendor_business_number == vendor.business_number
            )
        )).scalar_one_or_none()
        if not pool or not pool.cell_map:
            print(f"  ❌ pool 없음 ({vendor_name})")
            return

        old_map = dict(pool.cell_map)
        new_map = patch_fn(old_map)
        pool.cell_map = new_map
        if isinstance(pool.field_map, dict):
            pool.field_map = {**pool.field_map, "_cell_map": new_map}
        await db.commit()
        print(f"  ✅ {vendor_name} cell_map 업데이트 완료")
        changed = {k: (old_map.get(k), v) for k, v in new_map.items() if old_map.get(k) != v}
        removed = {k for k in old_map if k not in new_map}
        if changed:
            for k, (ov, nv) in changed.items():
                print(f"     변경: {k}: {ov!r} → {nv!r}")
        if removed:
            print(f"     삭제: {removed}")


# ── Fix 1: 펀디 ──────────────────────────────────────────────────────────────

def patch_fundy(cm: dict) -> dict:
    """issue_date G3 → C3"""
    new_cm = dict(cm)
    if new_cm.get("issue_date") == "G3":
        new_cm["issue_date"] = "C3"
    return new_cm


# ── Fix 2: 선양에스피티 ──────────────────────────────────────────────────────

def patch_sunyang_spt(cm: dict) -> dict:
    """
    issue_date_year/month/day (모두 A1 anchor로 수렴) → issue_date = "A1" (단일 셀)
    """
    new_cm = {k: v for k, v in cm.items()
              if k not in ("issue_date_year", "issue_date_month", "issue_date_day")}
    new_cm["issue_date"] = "A1"
    return new_cm


# ── Fix 3: 아이에이치켐 ──────────────────────────────────────────────────────

async def fix_ih_chem() -> None:
    """
    issue_date + recipient_name 둘 다 H5 (정적 라벨) — 각각 수정.
    - 날짜 입력칸 스캔 → 없으면 issue_date 제거 (no-date 양식)
    - recipient_name 스캔 → 탐색 결과 셀
    """
    # 지연 import (컨테이너 환경 의존)
    from sqlalchemy import select
    from app.database import AsyncSessionLocal
    from app.models.vendor import Vendor
    from app.models.vendor_pool import VendorTemplatePool

    vendor_name = "아이에이치켐"
    async with AsyncSessionLocal() as db:
        vendor = (await db.execute(
            select(Vendor).where(Vendor.name == vendor_name)
        )).scalar_one_or_none()
        if not vendor:
            vendor = (await db.execute(
                select(Vendor).where(Vendor.name.ilike("%아이에이치%"))
            )).scalar_one_or_none()
        if not vendor:
            print(f"  ❌ vendor '{vendor_name}' not found — 이름 확인 필요")
            return

        print(f"  아이에이치켐 실제 이름: {vendor.name!r}")
        template_path = vendor.quote_template_path
        if not template_path or not Path(template_path).exists():
            print(f"  ❌ template 없음")
            return

        # 날짜 셀 탐색
        date_cell = _scan_date_cell(template_path)
        print(f"  날짜 입력 셀 탐색 결과: {date_cell!r}")

        # recipient 셀 탐색
        recip_cell = _scan_recipient_cell(template_path)
        print(f"  수신 셀 탐색 결과: {recip_cell!r}")

        pool = (await db.execute(
            select(VendorTemplatePool).where(
                VendorTemplatePool.vendor_business_number == vendor.business_number
            )
        )).scalar_one_or_none()
        if not pool or not pool.cell_map:
            print(f"  ❌ pool 없음")
            return

        old_map = dict(pool.cell_map)
        new_map = dict(old_map)

        # issue_date 처리
        if date_cell:
            new_map["issue_date"] = date_cell
            print(f"  issue_date: H5 → {date_cell}")
        else:
            # 날짜 입력칸 없는 양식 → 제거
            new_map.pop("issue_date", None)
            new_map.pop("issue_date_year", None)
            new_map.pop("issue_date_month", None)
            new_map.pop("issue_date_day", None)
            print(f"  issue_date: 날짜 입력칸 없는 양식 — 제거")

        # recipient_name 처리
        if recip_cell:
            new_map["recipient_name"] = recip_cell
            print(f"  recipient_name: H5 → {recip_cell}")
        else:
            # 탐색 실패 — H5 그대로 두되 issue_date 충돌은 해소됨
            print(f"  recipient_name: 탐색 실패 — H5 유지 (issue_date 충돌은 해소됨)")

        pool.cell_map = new_map
        if isinstance(pool.field_map, dict):
            pool.field_map = {**pool.field_map, "_cell_map": new_map}
        await db.commit()
        print(f"  ✅ 아이에이치켐 cell_map 업데이트 완료")


# ── 메인 ─────────────────────────────────────────────────────────────────────

async def main() -> None:
    # 지연 import (컨테이너 환경 의존)
    from sqlalchemy import select
    from app.database import AsyncSessionLocal
    from app.models.vendor import Vendor

    print("=" * 60)
    print("M1.9 회귀-3: cell_map 4개 수정 패치")
    print("=" * 60)

    print("\n[ Fix 1 ] 펀디 — issue_date G3 → C3")
    await fix_vendor_cell_map("펀디", patch_fundy)

    print("\n[ Fix 2 ] 선양에스피티 — year/month/day(A1병합) → issue_date=A1")
    async with AsyncSessionLocal() as db:
        vendors = list((await db.execute(
            select(Vendor).where(Vendor.name.ilike("%선양%"))
        )).scalars().all())
        print(f"  '선양' 포함 vendor: {[v.name for v in vendors]}")
    if vendors:
        actual_name = vendors[0].name
        await fix_vendor_cell_map(actual_name, patch_sunyang_spt)
    else:
        print("  ❌ 선양에스피티 vendor 없음")

    print("\n[ Fix 3 ] 아이에이치켐 — H5 중복 매핑 수정")
    await fix_ih_chem()

    print("\n" + "=" * 60)
    print("패치 완료. m19_verify.py 재실행 전 내용 확인 권장.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
