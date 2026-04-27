"""default_manager_name 관련 코드 전부 제거"""
import ast, re

PATH = "/app/app/services/company_setting_extractor.py"

with open(PATH, "r", encoding="utf-8") as f:
    content = f.read()

original = content
applied = []

# 1. AUTO_EXTRACT_FIELDS에서 제거
old = '    "default_manager_name",\n)'
new = ')'
if old in content:
    content = content.replace(old, new)
    applied.append("AUTO_EXTRACT_FIELDS: default_manager_name 제거")

# 2. _FIELD_SOURCE_PRIORITY에서 default_manager_name 블록 제거
import re as _re
pattern = r'\s+"default_manager_name":\s*\([^)]*\),'
match = _re.search(pattern, content, _re.DOTALL)
if match:
    content = content[:match.start()] + content[match.end():]
    applied.append("_FIELD_SOURCE_PRIORITY: default_manager_name 제거")

# 3. _LABEL_PATTERNS에서 default_manager_name 블록 제거
pattern2 = r'\s+"default_manager_name":\s*\([^)]*\),'
match2 = _re.search(pattern2, content, _re.DOTALL)
if match2:
    content = content[:match2.start()] + content[match2.end():]
    applied.append("_LABEL_PATTERNS: default_manager_name 제거")

# 4. _is_plausible_value에서 default_manager_name 블록 제거
pattern3 = r'\n\s+if field == "default_manager_name":.*?return bool\(_KOR_OR_ENG_RE\.search\(stripped\)\)\n'
match3 = _re.search(pattern3, content, _re.DOTALL)
if match3:
    content = content[:match3.start()] + "\n" + content[match3.end():]
    applied.append("_is_plausible_value: default_manager_name 블록 제거")

# 5. 폴백 로직 전체 제거 (기본 담당자 폴백 주석~코드)
pattern4 = r'\n    # 기본 담당자 폴백.*?source_by_field\["default_manager_name"\] = "fallback_representative"\n'
match4 = _re.search(pattern4, content, _re.DOTALL)
if match4:
    content = content[:match4.start()] + "\n" + content[match4.end():]
    applied.append("폴백 로직 제거")

# 6. _SOURCE_EXCLUSIVE_FIELDS에서 default_manager_name 관련 줄 제거 (있으면)
content = content.replace(
    '    "quote_template": ("company_registration_number", "representative_name", "business_type", "business_item"),\n    "transaction_statement_template": ("company_registration_number", "representative_name", "business_type", "business_item"),',
    '    "quote_template": ("company_registration_number", "representative_name", "business_type", "business_item"),\n    "transaction_statement_template": ("company_registration_number", "representative_name", "business_type", "business_item"),'
)

# 7. fields_to_clear return에서 default_manager_name 언급 제거 (자동으로 처리됨)

# 8. logger.info found_fields에서 default_manager_name 관련 제거 - 자동으로 merged에 없으므로 OK

# 저장
if content != original:
    try:
        ast.parse(content)
    except SyntaxError as e:
        print(f"문법 오류! 저장 취소: line {e.lineno}: {e.msg} | {e.text}")
        exit(1)
    with open(PATH, "w", encoding="utf-8") as f:
        f.write(content)
    print("저장 완료")
else:
    print("변경 없음 (이미 적용됐거나 패턴 불일치)")

print("\n적용 결과:")
for a in applied:
    print(f"  ✓ {a}")

# 확인
with open(PATH) as f:
    final = f.read()
count = final.count("default_manager_name")
print(f"\n남은 'default_manager_name' 언급 수: {count}")
if count > 0:
    for i, line in enumerate(final.split("\n"), 1):
        if "default_manager_name" in line:
            print(f"  line {i}: {line.strip()}")

try:
    ast.parse(final)
    print("문법 검사: OK")
except SyntaxError as e:
    print(f"문법 오류: {e}")
