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
