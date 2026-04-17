from enum import Enum


class ProjectStatus(str, Enum):
    active = "active"
    closed = "closed"
    suspended = "suspended"


class CategoryType(str, Enum):
    outsourcing = "outsourcing"
    labor = "labor"
    test_report = "test_report"
    materials = "materials"
    meeting = "meeting"
    other = "other"


class ExpenseStatus(str, Enum):
    draft = "draft"
    pending_validation = "pending_validation"
    validated = "validated"
    rejected = "rejected"
    exported = "exported"


class DocumentType(str, Enum):
    # Outsourcing
    quote = "quote"
    comparative_quote = "comparative_quote"
    service_contract = "service_contract"
    work_order = "work_order"
    transaction_statement = "transaction_statement"
    inspection_photos = "inspection_photos"
    vendor_business_registration = "vendor_business_registration"
    vendor_bank_copy = "vendor_bank_copy"
    # Labor
    cash_expense_resolution = "cash_expense_resolution"
    in_kind_expense_resolution = "in_kind_expense_resolution"
    researcher_status_sheet = "researcher_status_sheet"
    # Test/Report
    expense_resolution = "expense_resolution"
    # Materials
    inspection_confirmation = "inspection_confirmation"
    # Meeting
    receipt = "receipt"
    meeting_minutes = "meeting_minutes"
    # Generic
    other = "other"


class UploadStatus(str, Enum):
    pending = "pending"
    uploaded = "uploaded"
    failed = "failed"


class ParseStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class QuestionType(str, Enum):
    rcms_procedure = "rcms_procedure"
    legal_policy = "legal_policy"
    mixed = "mixed"
    definition = "definition"


class ConclusionType(str, Enum):
    allowed = "allowed"
    not_allowed = "not_allowed"
    conditional = "conditional"
    approval_required = "approval_required"
    unclear = "unclear"


class AnswerStatusType(str, Enum):
    answered_with_direct_evidence = "answered_with_direct_evidence"
    answered_with_mixed_sources = "answered_with_mixed_sources"
    related_context_only = "related_context_only"
    insufficient_evidence = "insufficient_evidence"
    not_found_in_uploaded_materials = "not_found_in_uploaded_materials"
    routing_error = "routing_error"
