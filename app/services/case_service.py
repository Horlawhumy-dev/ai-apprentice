from typing import Any

CASES: dict[str, dict[str, Any]] = {
    "case_default": {
        "case_id": "case_default",
        "title": "Invoice INV-4471",
        "supplier": "Northwind Industrial",
        "amount": 7200,
        "proposed_cost_center": "CAPEX",
        "required_asset_number": True,
        "note": "Equipment above the capitalization threshold.",
    },
    "case_alpha": {
        "case_id": "case_alpha",
        "title": "Invoice INV-5120",
        "supplier": "Acme Tooling",
        "amount": 8400,
        "proposed_cost_center": "CAPEX",
        "required_asset_number": True,
        "note": "New CNC machine above threshold.",
    },
    "case_beta": {
        "case_id": "case_beta",
        "title": "Invoice INV-6002",
        "supplier": "Office Depot",
        "amount": 240,
        "proposed_cost_center": "OPEX",
        "required_asset_number": False,
        "note": "Consumables below threshold.",
    },
}


class CaseService:
    def list_cases(self) -> list[dict[str, Any]]:
        return list(CASES.values())

    def get_case(self, case_id: str) -> dict[str, Any] | None:
        return CASES.get(case_id)
