"""v7 Gate 2 — recipient_with_honorific 합성 단위 테스트."""

from __future__ import annotations

from app.services.document_set_service import synthesize_recipient_with_honorific


class TestSynthesizeRecipientWithHonorific:
    def test_recipient_company_name_used_when_present(self) -> None:
        ctx: dict = {"recipient_company_name": "유담"}
        synthesize_recipient_with_honorific(ctx)
        assert ctx["recipient_with_honorific"] == "유담 귀하"

    def test_falls_back_to_our_company_name(self) -> None:
        ctx: dict = {"our_company_name": "유담"}
        synthesize_recipient_with_honorific(ctx)
        assert ctx["recipient_with_honorific"] == "유담 귀하"

    def test_recipient_company_name_takes_priority_over_our(self) -> None:
        ctx: dict = {
            "recipient_company_name": "유담",
            "our_company_name": "다른회사",
        }
        synthesize_recipient_with_honorific(ctx)
        assert ctx["recipient_with_honorific"] == "유담 귀하"

    def test_no_name_no_key_added(self) -> None:
        ctx: dict = {}
        synthesize_recipient_with_honorific(ctx)
        assert "recipient_with_honorific" not in ctx

    def test_empty_string_treated_as_missing(self) -> None:
        ctx: dict = {"recipient_company_name": "", "our_company_name": ""}
        synthesize_recipient_with_honorific(ctx)
        assert "recipient_with_honorific" not in ctx

    def test_with_special_chars(self) -> None:
        """특수문자(괄호/영문/㈜)도 그대로 결합."""
        ctx: dict = {"recipient_company_name": "(주)유담Tech ㈜"}
        synthesize_recipient_with_honorific(ctx)
        assert ctx["recipient_with_honorific"] == "(주)유담Tech ㈜ 귀하"

    def test_does_not_mutate_other_keys(self) -> None:
        ctx: dict = {"recipient_company_name": "유담", "other_key": "보존"}
        synthesize_recipient_with_honorific(ctx)
        assert ctx["recipient_with_honorific"] == "유담 귀하"
        assert ctx["recipient_company_name"] == "유담"
        assert ctx["other_key"] == "보존"

    def test_idempotent(self) -> None:
        """두 번 호출해도 동일."""
        ctx: dict = {"recipient_company_name": "유담"}
        synthesize_recipient_with_honorific(ctx)
        synthesize_recipient_with_honorific(ctx)
        assert ctx["recipient_with_honorific"] == "유담 귀하"
