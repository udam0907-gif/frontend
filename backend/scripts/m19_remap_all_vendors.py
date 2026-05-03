"""
M1.9 회귀-3: 5개 글로벌 vendor 전체 재매핑
강화된 mapper 프롬프트(회귀-2)를 적용하여 vendor_template_pool.cell_map 갱신.

실행: docker exec rnd_backend python3 /app/scripts/m19_remap_all_vendors.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, "/app")

from sqlalchemy import select, text

from app.database import AsyncSessionLocal
from app.models.vendor_pool import VendorTemplatePool
from app.models.vendor import Vendor
from app.services.llm_service import get_llm_service
from app.services.xlsx_cell_mapper import XlsxCellMapper

REQUIRED_KEYS = [
    "recipient_name", "issue_date",
    # vendor_name, vendor_business_no는 보존 정책으로 cell_map 제외 — 검사 불필요
    "item_name", "quantity", "unit_price", "amount", "total_amount",
]
DATE_ALT = {"issue_date_year", "issue_date_month", "issue_date_day"}

DOC_TYPES = [
    ("quote", "quote_template_path"),
    # transaction은 quote cell_map을 공유한다.
    # remap 시 transaction을 별도 분석하면 pool.cell_map을 덮어써서
    # quote 생성 시 잘못된 cell_map이 사용되는 사고가 발생한다.
]


def _check_required(cell_map: dict) -> tuple[list[str], list[str]]:
    present, missing = [], []
    for k in REQUIRED_KEYS:
        if k == "issue_date":
            has = cell_map.get("issue_date") or all(
                cell_map.get(d) for d in DATE_ALT
            )
        else:
            v = cell_map.get(k)
            has = bool(v and v != "null")
        (present if has else missing).append(k)
    return present, missing


def _cell_map_key_count(cell_map: dict) -> int:
    return sum(
        1 for k, v in cell_map.items()
        if k not in {"_meta", "sheet_name"} and isinstance(v, str) and v
    )


async def remap_all() -> None:
    print("=" * 70)
    print("M1.9 회귀-3: 전체 vendor 재매핑 시작")
    print("=" * 70)

    # ── 1. vendor 조회 (global + project-specific 모두) ──────────────────
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Vendor)
            .order_by(Vendor.created_at)
        )
        vendors: list[Vendor] = list(result.scalars().all())

    print(f"\n글로벌 vendor {len(vendors)}개:")
    for v in vendors:
        print(f"  · {v.name:<20} biz={v.business_number}")

    mapper = XlsxCellMapper(get_llm_service())

    # ── 2. 매핑 결과 수집 ─────────────────────────────────────────────────
    # results[vendor_name][doc_type] = {"cell_map": ..., "missing": ..., "prev_count": int}
    results: dict[str, dict] = {}

    for vendor in vendors:
        results[vendor.name] = {}

        for doc_label, path_attr in DOC_TYPES:
            file_path: str | None = getattr(vendor, path_attr, None)

            if not file_path or not Path(file_path).exists():
                results[vendor.name][doc_label] = {"status": "N/A"}
                print(f"\n  [{vendor.name}] {doc_label}: 파일 없음 — SKIP")
                continue

            ext = Path(file_path).suffix.lower()
            if ext not in (".xlsx", ".xls"):
                results[vendor.name][doc_label] = {"status": "N/A", "reason": f"비XLSX({ext})"}
                print(f"\n  [{vendor.name}] {doc_label}: {ext} 비지원 — SKIP")
                continue

            # 이전 cell_map 키 수 조회
            prev_count = 0
            async with AsyncSessionLocal() as db:
                pool_result = await db.execute(
                    select(VendorTemplatePool).where(
                        VendorTemplatePool.vendor_business_number == vendor.business_number
                    )
                )
                pool = pool_result.scalar_one_or_none()
                if pool and pool.cell_map:
                    prev_count = _cell_map_key_count(pool.cell_map)

            print(f"\n  [{vendor.name}] {doc_label}: analyze() 호출 중... (이전 키={prev_count})")

            try:
                remap_result = await mapper.analyze(file_path)
                new_cell_map: dict = remap_result.get("cell_map", {})
                new_count = _cell_map_key_count(new_cell_map)
                present, missing = _check_required(new_cell_map)

                print(f"    → 새 키={new_count}  누락={missing if missing else '없음'}")

                # DB 갱신 (UPSERT — pool 행 없으면 새로 생성)
                async with AsyncSessionLocal() as db:
                    pool_result = await db.execute(
                        select(VendorTemplatePool).where(
                            VendorTemplatePool.vendor_business_number == vendor.business_number
                        )
                    )
                    pool = pool_result.scalar_one_or_none()
                    if pool:
                        pool.cell_map = new_cell_map
                        if isinstance(pool.field_map, dict):
                            pool.field_map = {**pool.field_map, "_cell_map": new_cell_map}
                        await db.flush()
                        await db.commit()
                        print(f"    DB 갱신 완료 (기존 pool 행 업데이트)")
                    else:
                        new_pool = VendorTemplatePool(
                            vendor_business_number=vendor.business_number,
                            vendor_name=vendor.name,
                            cell_map=new_cell_map,
                            field_map={"_cell_map": new_cell_map},
                        )
                        db.add(new_pool)
                        await db.flush()
                        await db.commit()
                        print(f"    DB 갱신 완료 (신규 pool 행 생성)")

                results[vendor.name][doc_label] = {
                    "status": "OK",
                    "cell_map": new_cell_map,
                    "prev_count": prev_count,
                    "new_count": new_count,
                    "present": present,
                    "missing": missing,
                }

            except Exception as e:
                print(f"    ❌ 오류: {e}")
                results[vendor.name][doc_label] = {"status": "ERROR", "error": str(e)}

    # ── 3. 재매핑 결과 매트릭스 출력 ─────────────────────────────────────
    print("\n" + "=" * 70)
    print("재매핑 결과 매트릭스")
    print("=" * 70)

    print(f"\n{'vendor':<20} {'doc':<14} {'이전키':>5} {'새키':>5}  {'누락 핵심 키'}")
    print("-" * 70)
    for vname, doc_results in results.items():
        for doc_label, info in doc_results.items():
            if info.get("status") == "N/A":
                print(f"{vname:<20} {doc_label:<14} {'N/A':>5} {'N/A':>5}")
            elif info.get("status") == "ERROR":
                print(f"{vname:<20} {doc_label:<14} {'ERR':>5} {'ERR':>5}  {info['error'][:40]}")
            else:
                prev = info["prev_count"]
                new = info["new_count"]
                missing = info["missing"]
                flag = "✅" if not missing else "⚠️ "
                print(f"{vname:<20} {doc_label:<14} {prev:>5} {new:>5}  {flag} 누락: {missing if missing else '없음'}")

    # ── 4. 12개 핵심 키 커버리지 매트릭스 ────────────────────────────────
    print("\n" + "=" * 70)
    print("12개 핵심 키 커버리지 매트릭스")
    print("=" * 70)

    all_keys = REQUIRED_KEYS + [
        "vendor_address", "vendor_contact", "spec", "doc_number",
    ]
    header = f"{'vendor':<20} {'doc':<12}"
    for k in all_keys:
        header += f" {k[:8]:>8}"
    print(header)
    print("-" * (32 + len(all_keys) * 9))

    for vname, doc_results in results.items():
        for doc_label, info in doc_results.items():
            row = f"{vname:<20} {doc_label:<12}"
            if info.get("status") == "N/A":
                for _ in all_keys:
                    row += f" {'N/A':>8}"
            elif info.get("status") == "ERROR":
                for _ in all_keys:
                    row += f" {'ERR':>8}"
            else:
                cm = info["cell_map"]
                for k in all_keys:
                    if k == "issue_date":
                        has = cm.get("issue_date") or all(cm.get(d) for d in DATE_ALT)
                    else:
                        v = cm.get(k)
                        has = bool(v and v != "null")
                    row += f" {'O':>8}" if has else f" {'X':>8}"
            print(row)

    # ── 5. 핵심 결함 해결 여부 ────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("회귀-2 식별 결함 해결 여부")
    print("=" * 70)
    checks = [
        ("태산물산", "quote", "spec"),
        ("태산물산", "quote", "quantity"),
        ("태산물산", "quote", "unit_price"),
        ("선양인터내셔날", "quote", "spec"),
        ("선양인터내셔날", "quote", "issue_date"),
        ("아이에이치캠", "quote", "quantity"),
    ]
    for vname, doc_label, key in checks:
        info = results.get(vname, {}).get(doc_label, {})
        if info.get("status") != "OK":
            status = "N/A"
        else:
            cm = info["cell_map"]
            if key == "issue_date":
                has = cm.get("issue_date") or all(cm.get(d) for d in DATE_ALT)
            else:
                v = cm.get(key)
                has = bool(v and v != "null")
            status = "✅ 해결" if has else "❌ 미해결"
        print(f"  {vname:<20} {doc_label:<10} {key:<20} → {status}")

    print("\n재매핑 완료")


if __name__ == "__main__":
    asyncio.run(remap_all())
