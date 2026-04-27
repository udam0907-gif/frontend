"""
1) cell_mapped=0 템플릿 4개에 셀 매핑 일괄 적용
2) 물구매 expense 문서세트 재생성
3) mapping_needed → excel_rendered 상태 변화 확인
4) 결과 xlsx 셀 값 검증
"""
import requests, sys
from pathlib import Path
import openpyxl

BASE = "http://localhost:8000/api/v1"
EXPENSE_ID = "b4b93a01-9edc-45e5-b9b7-36bdb05eb738"   # 물구매

ZERO_CELL_TEMPLATES = [
    "bfe80856-5bcf-4938-b3b3-6cd6d11daed0",  # 재료비 검수확인서
    "86e34c26-e742-4767-bd4b-b84ee5e36eaf",  # 전내 지출결의서 (1)
    "07ca8fcb-f9d2-4b44-a58f-487638d50744",  # 전내 검수확인서 양식
    "ec146f1d-2f94-447a-a768-46dbe04c1b94",  # 전내 지출결의서 (2)
]

MAPPING = {
    "company_name":   "B3",
    "execution_date": "E3",
    "budget_item":    "B5",
    "note":           "E5",
    "item_name":      "A9",
    "quantity":       "C9",
    "unit_price":     "D9",
    "amount":         "E9",
}

print("[1] cell_mapped=0 템플릿 4개 셀 매핑 적용")
for tid in ZERO_CELL_TEMPLATES:
    r = requests.put(f"{BASE}/templates/{tid}/cell-mapping", json={"mapping": MAPPING})
    fm = r.json().get("field_map", {})
    saved = {k: v["cell"] for k,v in fm.items() if isinstance(v,dict) and v.get("cell")}
    print(f"  {tid[:8]}... → {len(saved)}개 저장 {'OK' if r.status_code==200 else 'FAIL'}")

print("\n[2] 전체 템플릿 셀 매핑 현황")
templates = requests.get(f"{BASE}/templates").json()
for t in templates:
    cells = sum(1 for v in t["field_map"].values() if isinstance(v,dict) and v.get("cell"))
    print(f"  {t['name'][:20]:20} | {t['document_type']:25} | cell={cells}")

print(f"\n[3] 물구매 문서세트 재생성 (expense_id={EXPENSE_ID[:8]}...)")
r = requests.post(f"{BASE}/documents/generate-set/{EXPENSE_ID}")
assert r.status_code == 200, f"생성 실패: {r.status_code} {r.text}"
result = r.json()
print(f"  total={result['total']} generated={result['generated']} errors={result['errors']}")

print("\n[4] 문서별 상태 변화")
for item in result["items"]:
    did = item.get("generated_document_id","")
    print(f"  {item['document_type']:35} → {item['status']}")

print("\n[5] xlsx 셀 값 검증 (excel_rendered 문서만)")
OUTPUT_DIR = Path("test_outputs")
OUTPUT_DIR.mkdir(exist_ok=True)

xlsx_docs = [i for i in result["items"] if i["status"] == "excel_rendered" and i.get("generated_document_id")]
if not xlsx_docs:
    print("  excel_rendered 문서 없음 — mapping_needed 확인 필요")
else:
    for item in xlsx_docs[:2]:
        did = item["generated_document_id"]
        r = requests.get(f"{BASE}/documents/{did}/download")
        assert r.status_code == 200
        out = OUTPUT_DIR / f"regen_{item['document_type']}_{did[:6]}.xlsx"
        out.write_bytes(r.content)
        wb = openpyxl.load_workbook(out)
        ws = wb.active
        ok, fail = [], []
        for field, cell in MAPPING.items():
            actual = ws[cell].value
            if actual is not None:
                ok.append(f"{field}({cell})={actual}")
            else:
                fail.append(f"{field}({cell})=EMPTY")
        print(f"\n  [{item['document_type']}]")
        print(f"    OK   : {', '.join(ok[:4])}")
        if len(ok) > 4: print(f"           {', '.join(ok[4:])}")
        if fail: print(f"    EMPTY: {fail}")

print("\n=== 완료 ===")
