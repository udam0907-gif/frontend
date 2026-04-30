"""
M1.8 매핑 검증 — 전체 업체 견적서/비교견적서 일괄 출력
컨테이너 내부에서 실행. output_path 기반 파일 복사.
코드 수정 없음. Read-only except file copy to outputs.
"""

import requests
import json
import os
import shutil
import math
import random
from datetime import datetime

BASE_URL = "http://localhost:8000"
APP_DIR = "/app"
OUTPUT_BASE = "/app/outputs_verify/매핑검증_2026-04-30"

# 테스트 입력값 (공통)
TEST_DATE = "2026-04-01"
TEST_ITEM = "tio2"
TEST_QTY = 5
TEST_SPEC = "kg"
TEST_UNIT_PRICE = 1350000
TEST_AMOUNT = TEST_QTY * TEST_UNIT_PRICE  # 6,750,000

PROJECT_ANY = "915bb465-b182-4173-ae51-5347159cc71c"
PROJECT_SPECIFIC = "b315bd6b-02ba-4043-85c2-41ded0c0415f"

VENDORS = [
    {"id": "6ac9af2b-646d-4441-95b0-20debdf732e7", "name": "민서정밀",       "biz_no": "504-31-43112", "is_global": True},
    {"id": "5870f473-fd5e-485d-81ce-6176a16e564c", "name": "태산물산",       "biz_no": "524-27-00949", "is_global": True},
    {"id": "629b082e-9d78-494d-a744-b9807c69bfc5", "name": "아이에이치캠",   "biz_no": "514-26-30584", "is_global": True},
    {"id": "6dc24381-44e0-401f-a507-f9129ae949c4", "name": "선양인터내셔날", "biz_no": "549-21-00679", "is_global": True},
    {"id": "7b6b726e-0d82-45ac-b5d8-f088037f2dc4", "name": "㈜대신테크젠",   "biz_no": "515-81-47073", "is_global": True},
    {"id": "339cbf90-e167-43d3-91db-1d11dd5c5f78", "name": "펀디",          "biz_no": "227-31-06281", "is_global": False},
    {"id": "8450725d-6266-4ce6-b69a-e28baf650efb", "name": "민서정밀",       "biz_no": "504-31-43112", "is_global": False},
    {"id": "c5ec2b46-0647-45a3-a3ba-df8b31973204", "name": "태산물산",       "biz_no": "524-27-00949", "is_global": False},
    {"id": "c105c63a-364c-420e-90fb-2fc34649d2ae", "name": "㈜대신테크젠",   "biz_no": "515-81-47073", "is_global": False},
]

DOC_TYPE_KR = {
    "quote": "견적서",
    "comparative_quote": "비교견적서",
    "transaction_statement": "거래명세서",
    "expense_resolution": "지출결의서",
    "inspection_confirmation": "검수확인서",
    "vendor_business_registration": "사업자등록증",
    "vendor_bank_copy": "통장사본",
}


def round_up_100(val):
    return math.ceil(val / 100) * 100


def get_compare_vendor_id(vendor):
    same_pool = [v for v in VENDORS if v["is_global"] == vendor["is_global"] and v["id"] != vendor["id"]]
    return same_pool[0]["id"] if same_pool else VENDORS[0]["id"]


def create_expense(vendor, project_id):
    ratio = round(random.uniform(1.1, 1.5), 2)
    compare_unit_price = round_up_100(TEST_UNIT_PRICE * ratio)
    compare_amount = compare_unit_price * TEST_QTY

    payload = {
        "project_id": project_id,
        "category_type": "materials",
        "title": TEST_ITEM,
        "amount": TEST_AMOUNT,
        "expense_date": TEST_DATE,
        "vendor_name": vendor["name"],
        "vendor_registration_number": vendor["biz_no"],
        "metadata": {
            "vendor_id": vendor["id"],
            "line_items": [{
                "item_name": TEST_ITEM,
                "quantity": TEST_QTY,
                "spec": TEST_SPEC,
                "unit_price": TEST_UNIT_PRICE,
                "amount": TEST_AMOUNT,
            }],
            "purchase_purpose": "매핑검증 테스트",
            "usage_purpose": "M1.8 검증",
            "delivery_date": TEST_DATE,
            "compare_amount": compare_amount,
            "compare_vendor_id": get_compare_vendor_id(vendor),
        }
    }
    resp = requests.post(f"{BASE_URL}/api/v1/expenses/", json=payload)
    resp.raise_for_status()
    return resp.json(), compare_unit_price, compare_amount


def generate_doc_set(expense_id):
    resp = requests.post(f"{BASE_URL}/api/v1/documents/generate-set/{expense_id}")
    resp.raise_for_status()
    return resp.json()


def run():
    os.makedirs(OUTPUT_BASE, exist_ok=True)
    results = []
    errors = []

    print(f"=== M1.8 매핑 검증 시작 — 총 {len(VENDORS)}개 업체 ===\n")

    for vendor in VENDORS:
        scope = "글로벌" if vendor["is_global"] else "프로젝트"
        label = f"{vendor['name']}({scope})"
        project_id = PROJECT_ANY if vendor["is_global"] else PROJECT_SPECIFIC
        print(f"[{label}] 처리 중...")

        result = {
            "vendor_name": vendor["name"],
            "is_global": vendor["is_global"],
            "견적서": "❌", "비교견적서": "❌",
            "compare_unit_price": None,
            "note": "",
        }

        try:
            expense, compare_unit_price, compare_amount = create_expense(vendor, project_id)
            expense_id = expense["id"]
            result["compare_unit_price"] = compare_unit_price
            print(f"  expense_id: {expense_id} | 비교단가: {compare_unit_price:,}원")

            doc_set = generate_doc_set(expense_id)
            print(f"  문서세트: total={doc_set['total']}, generated={doc_set['generated']}, errors={doc_set['errors']}")

            folder_name = f"{vendor['name']}_{scope}"
            vendor_dir = os.path.join(OUTPUT_BASE, folder_name)
            os.makedirs(vendor_dir, exist_ok=True)

            for item in doc_set.get("items", []):
                doc_type = item.get("document_type", "unknown")
                status = item.get("status", "")
                output_path = item.get("output_path")
                err_msg = item.get("error_message")
                doc_kr = DOC_TYPE_KR.get(doc_type, doc_type)

                if not output_path:
                    print(f"  ⚠ {doc_kr}: {err_msg or status}")
                    result["note"] += f"[{doc_kr}] {err_msg or status}; "
                    continue

                src = os.path.join(APP_DIR, output_path)
                if not os.path.exists(src):
                    print(f"  ⚠ {doc_kr}: 파일 없음 ({src})")
                    result["note"] += f"[{doc_kr}] 파일 없음; "
                    continue

                ext = os.path.splitext(src)[1]
                dest_name = f"{doc_kr}_{vendor['name']}_20260401{ext}"
                dest = os.path.join(vendor_dir, dest_name)
                shutil.copy2(src, dest)
                print(f"  ✅ {dest_name}")

                if doc_type == "quote":
                    result["견적서"] = "✅"
                elif doc_type == "comparative_quote":
                    result["비교견적서"] = "✅"

        except Exception as e:
            import traceback
            print(f"  ❌ 오류: {e}")
            traceback.print_exc()
            result["note"] = str(e)
            errors.append({"vendor": label, "error": str(e)})

        results.append(result)
        print()

    write_report(results, errors)
    print(f"\n출력 폴더: {OUTPUT_BASE}")
    print(f"Windows 경로: C:\\Users\\FORYOUCOM\\cm_app\\backend\\outputs_verify\\매핑검증_2026-04-30\\")
    return results, errors


def write_report(results, errors):
    path = os.path.join(OUTPUT_BASE, "_검증보고서.md")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# 매핑 검증 보고서 — 2026-04-30",
        f"\n생성 시각: {now}",
        f"\n## 대상 vendor (총 {len(results)}개)",
    ]
    for i, r in enumerate(results, 1):
        scope = "글로벌" if r["is_global"] else "프로젝트"
        lines.append(f"{i}. {r['vendor_name']} ({scope})")

    lines += [
        "\n## 출력 결과\n",
        "| vendor | 구분 | 견적서 | 비교견적서 | 비교단가 | 비고 |",
        "|--------|------|--------|-----------|---------|------|",
    ]
    for r in results:
        scope = "글로벌" if r["is_global"] else "프로젝트"
        cp = f"{r['compare_unit_price']:,}" if r["compare_unit_price"] else "-"
        lines.append(f"| {r['vendor_name']} | {scope} | {r['견적서']} | {r['비교견적서']} | {cp} | {r.get('note','')} |")

    ok_quote = all(r["견적서"] == "✅" for r in results)
    ok_compare = all(r["비교견적서"] == "✅" for r in results)
    lines += [
        "\n## 자동 게이트 통과 여부",
        f"- 모든 vendor 견적서 생성됨: {'✅' if ok_quote else '❌'}",
        f"- 모든 vendor 비교견적서 생성됨: {'✅' if ok_compare else '❌'}",
        f"- HTTP 5xx 에러 발생 없음: {'✅' if not errors else '❌'}",
        "\n## 테스트 입력값",
        f"- 집행일자: {TEST_DATE}",
        f"- 품목명: {TEST_ITEM}",
        f"- 수량: {TEST_QTY} / 규격: {TEST_SPEC}",
        f"- 단가: {TEST_UNIT_PRICE:,}원 / 금액: {TEST_AMOUNT:,}원",
        f"- 비교단가: 단가 × 1.1~1.5 랜덤, 100원 단위 올림",
        "\n## 사용자 시각 검증 대기",
        "§7 체크리스트로 직접 확인 요청.",
        f"\n출력 위치: `C:\\\\Users\\\\FORYOUCOM\\\\cm_app\\\\backend\\\\outputs_verify\\\\매핑검증_2026-04-30\\\\`",
    ]
    if errors:
        lines += ["\n## 오류 목록"]
        for e in errors:
            lines.append(f"- **{e['vendor']}**: {e['error']}")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"검증보고서 저장: {path}")


if __name__ == "__main__":
    run()
