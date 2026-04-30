"""
M1.8 매핑 검증 — 전체 업체 견적서/비교견적서 일괄 출력 스크립트
코드 수정 없음. 읽기 + API 호출 + 파일 저장만 수행.
"""

import requests
import json
import os
import shutil
import math
import random
from datetime import datetime

BASE_URL = "http://localhost:8000"
OUTPUT_BASE = r"C:\Users\FORYOUCOM\cm_app\outputs\매핑검증_2026-04-30"

# 테스트 입력값 (공통)
TEST_DATE = "2026-04-01"
TEST_ITEM = "tio2"
TEST_QTY = 5
TEST_SPEC = "kg"
TEST_UNIT_PRICE = 1350000
TEST_AMOUNT = TEST_QTY * TEST_UNIT_PRICE  # 6,750,000

# 프로젝트 ID
PROJECT_ANY = "915bb465-b182-4173-ae51-5347159cc71c"       # 전사(글로벌) 업체용
PROJECT_SPECIFIC = "b315bd6b-02ba-4043-85c2-41ded0c0415f"  # 프로젝트 전용 업체용

# 업체 목록 (DB 조회 결과)
VENDORS = [
    # 글로벌 업체
    {"id": "6ac9af2b-646d-4441-95b0-20debdf732e7", "name": "민서정밀",      "biz_no": "504-31-43112", "is_global": True},
    {"id": "5870f473-fd5e-485d-81ce-6176a16e564c", "name": "태산물산",      "biz_no": "524-27-00949", "is_global": True},
    {"id": "629b082e-9d78-494d-a744-b9807c69bfc5", "name": "아이에이치캠",  "biz_no": "514-26-30584", "is_global": True},
    {"id": "6dc24381-44e0-401f-a507-f9129ae949c4", "name": "선양인터내셔날","biz_no": "549-21-00679", "is_global": True},
    {"id": "7b6b726e-0d82-45ac-b5d8-f088037f2dc4", "name": "㈜대신테크젠",  "biz_no": "515-81-47073", "is_global": True},
    # 프로젝트 전용 업체
    {"id": "339cbf90-e167-43d3-91db-1d11dd5c5f78", "name": "펀디",         "biz_no": "227-31-06281", "is_global": False},
    {"id": "8450725d-6266-4ce6-b69a-e28baf650efb", "name": "민서정밀",      "biz_no": "504-31-43112", "is_global": False},
    {"id": "c5ec2b46-0647-45a3-a3ba-df8b31973204", "name": "태산물산",      "biz_no": "524-27-00949", "is_global": False},
    {"id": "c105c63a-364c-420e-90fb-2fc34649d2ae", "name": "㈜대신테크젠",  "biz_no": "515-81-47073", "is_global": False},
]


def round_up_100(val):
    """100원 단위 올림"""
    return math.ceil(val / 100) * 100


def get_compare_vendor_id(vendor, all_vendors):
    """비교 업체 선택 (같은 is_global 풀에서 다른 업체)"""
    same_pool = [v for v in all_vendors if v["is_global"] == vendor["is_global"] and v["id"] != vendor["id"]]
    if same_pool:
        return same_pool[0]["id"]
    # fallback: 아무 다른 업체
    others = [v for v in all_vendors if v["id"] != vendor["id"]]
    return others[0]["id"] if others else None


def create_expense(vendor, project_id):
    ratio = round(random.uniform(1.1, 1.5), 2)
    compare_unit_price = round_up_100(TEST_UNIT_PRICE * ratio)
    compare_amount = compare_unit_price * TEST_QTY
    compare_vendor_id = get_compare_vendor_id(vendor, VENDORS)

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
            "line_items": [
                {
                    "item_name": TEST_ITEM,
                    "quantity": TEST_QTY,
                    "spec": TEST_SPEC,
                    "unit_price": TEST_UNIT_PRICE,
                    "amount": TEST_AMOUNT,
                }
            ],
            "purchase_purpose": "매핑검증 테스트",
            "usage_purpose": "M1.8 검증",
            "delivery_date": TEST_DATE,
            "compare_amount": compare_amount,
            "compare_vendor_id": compare_vendor_id,
        }
    }
    resp = requests.post(f"{BASE_URL}/api/v1/expenses/", json=payload)
    resp.raise_for_status()
    return resp.json(), compare_unit_price, compare_amount


def generate_document_set(expense_id):
    resp = requests.post(f"{BASE_URL}/api/v1/documents/generate-set/{expense_id}")
    resp.raise_for_status()
    return resp.json()


def download_document(doc_id, dest_path):
    resp = requests.get(f"{BASE_URL}/api/v1/documents/{doc_id}/download", stream=True)
    resp.raise_for_status()
    with open(dest_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)


def run():
    results = []
    errors = []

    print(f"=== M1.8 매핑 검증 시작 — 총 {len(VENDORS)}개 업체 ===\n")

    for vendor in VENDORS:
        label = f"{vendor['name']}({'글로벌' if vendor['is_global'] else '프로젝트'})"
        project_id = PROJECT_ANY if vendor["is_global"] else PROJECT_SPECIFIC
        print(f"[{label}] 처리 중...")

        result = {
            "vendor_name": vendor["name"],
            "vendor_id": vendor["id"],
            "is_global": vendor["is_global"],
            "견적서": "❌",
            "비교견적서": "❌",
            "note": "",
        }

        try:
            # 1. Expense 생성
            expense, compare_unit_price, compare_amount = create_expense(vendor, project_id)
            expense_id = expense["id"]
            print(f"  expense_id: {expense_id}")

            # 2. 문서세트 생성
            doc_set = generate_document_set(expense_id)
            print(f"  문서세트: total={doc_set['total']}, generated={doc_set['generated']}, errors={doc_set['errors']}")

            # 3. 출력 폴더
            folder_name = f"{vendor['name']}_{'글로벌' if vendor['is_global'] else '프로젝트'}"
            vendor_dir = os.path.join(OUTPUT_BASE, folder_name)
            os.makedirs(vendor_dir, exist_ok=True)

            # 4. 각 문서 다운로드
            for item in doc_set.get("items", []):
                doc_id = item.get("document_id") or item.get("id")
                doc_type = item.get("document_type", "unknown")
                status = item.get("status", "")
                file_name = item.get("file_name") or item.get("filename") or ""

                if status == "error" or not doc_id:
                    print(f"  ⚠ {doc_type} — {item.get('error', '생성 실패')}")
                    result["note"] += f"{doc_type} 오류; "
                    continue

                # 파일 확장자 추정
                ext = ".xlsx"
                if file_name:
                    ext = os.path.splitext(file_name)[1] or ext

                # 파일명 결정
                date_str = "20260401"
                if "비교" in doc_type or "comparative" in doc_type.lower():
                    dest_name = f"비교견적서_{vendor['name']}_{date_str}{ext}"
                    result["비교견적서"] = "✅"
                elif "견적" in doc_type or "quote" in doc_type.lower():
                    dest_name = f"견적서_{vendor['name']}_{date_str}{ext}"
                    result["견적서"] = "✅"
                elif "거래명세" in doc_type or "transaction" in doc_type.lower():
                    dest_name = f"거래명세서_{vendor['name']}_{date_str}{ext}"
                elif "지출결의" in doc_type or "payment" in doc_type.lower():
                    dest_name = f"지출결의서_{vendor['name']}_{date_str}.docx"
                elif "검수" in doc_type or "inspection" in doc_type.lower():
                    dest_name = f"검수확인서_{vendor['name']}_{date_str}.docx"
                else:
                    dest_name = f"{doc_type}_{vendor['name']}_{date_str}{ext}"

                dest_path = os.path.join(vendor_dir, dest_name)
                try:
                    download_document(doc_id, dest_path)
                    print(f"  ✅ {dest_name}")
                except Exception as e:
                    print(f"  ❌ {dest_name} 다운로드 실패: {e}")
                    result["note"] += f"{dest_name} 다운로드 실패; "

            result["compare_unit_price"] = compare_unit_price
            result["compare_amount"] = compare_amount

        except Exception as e:
            print(f"  ❌ 오류: {e}")
            result["note"] = str(e)
            errors.append({"vendor": label, "error": str(e)})

        results.append(result)
        print()

    # 5. 검증보고서 작성
    write_report(results, errors)
    print("=== 완료 ===")
    return results, errors


def write_report(results, errors):
    report_path = os.path.join(OUTPUT_BASE, "_검증보고서.md")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = [
        "# 매핑 검증 보고서 — 2026-04-30",
        f"\n생성 시각: {now}",
        f"\n## 대상 vendor (총 {len(results)}개)",
    ]
    for i, r in enumerate(results, 1):
        scope = "글로벌" if r["is_global"] else "프로젝트"
        lines.append(f"{i}. {r['vendor_name']} ({scope})")

    lines.append("\n## 출력 결과\n")
    lines.append("| vendor | 구분 | 견적서 | 비교견적서 | 비교단가 | 비고 |")
    lines.append("|--------|------|--------|-----------|---------|------|")
    for r in results:
        scope = "글로벌" if r["is_global"] else "프로젝트"
        compare_price = f"{r.get('compare_unit_price', '-'):,}" if r.get('compare_unit_price') else "-"
        lines.append(f"| {r['vendor_name']} | {scope} | {r['견적서']} | {r['비교견적서']} | {compare_price} | {r.get('note', '')} |")

    all_ok = all(r["견적서"] == "✅" for r in results)
    compare_ok = all(r["비교견적서"] == "✅" for r in results)
    no_errors = len(errors) == 0

    lines.append("\n## 자동 게이트 통과 여부")
    lines.append(f"- 모든 vendor 견적서 생성됨: {'✅' if all_ok else '❌'}")
    lines.append(f"- 모든 vendor 비교견적서 생성됨: {'✅' if compare_ok else '❌'}")
    lines.append(f"- HTTP 5xx 에러 발생 없음: {'✅' if no_errors else '❌'}")

    lines.append("\n## 테스트 입력값")
    lines.append(f"- 집행일자: {TEST_DATE}")
    lines.append(f"- 품목명: {TEST_ITEM}")
    lines.append(f"- 수량: {TEST_QTY}")
    lines.append(f"- 규격: {TEST_SPEC}")
    lines.append(f"- 단가: {TEST_UNIT_PRICE:,}원")
    lines.append(f"- 금액: {TEST_AMOUNT:,}원")
    lines.append(f"- 비교단가: 단가 × 1.1~1.5 랜덤, 100원 단위 올림")

    lines.append("\n## 사용자 시각 검증 대기")
    lines.append(f"각 업체 폴더의 견적서·비교견적서를 §7 체크리스트로 직접 확인해주세요.")
    lines.append(f"\n출력 위치: `{OUTPUT_BASE}`")

    if errors:
        lines.append("\n## 오류 목록")
        for e in errors:
            lines.append(f"- **{e['vendor']}**: {e['error']}")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"검증보고서 저장: {report_path}")


if __name__ == "__main__":
    run()
