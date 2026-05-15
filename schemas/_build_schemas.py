#!/usr/bin/env python3
"""Generates the per-prompt and per-ACORD-form JSON Schemas for
Nightmare Extraction Test v1.0.

Strict-mode constraints honored:
  - additionalProperties: false everywhere
  - every property name appears in required
  - nullable types use ["string", "null"] / ["number", "null"] form
  - open-keyed dicts (additional_fields, keyed checkboxes) become arrays

Run:
    python _build_schemas.py

Writes one .schema.json per prompt/form into this directory.
"""
from __future__ import annotations

import json
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent

# ── Reusable enum vocabularies (per plan §2-H) ─────────────────────────

US_STATES = [
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN",
    "IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV",
    "NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN",
    "TX","UT","VT","VA","WA","WV","WI","WY","DC","PR","GU","VI","AS","MP",
]

CONSTRUCTION = [
    "Non-Combustible","Fire Resistive","Masonry Non-Combustible","Joisted Masonry",
]
ROOF_TYPE = [
    "TPO","EPDM","Concrete","Shingle","Metal","Single-Ply Membrane",
    "Built-Up","Modified Bitumen",
]
SPRINKLER_TYPE = ["Pre-Action","Wet Pipe","Deluge","Dry Pipe","None"]
FIRE_ALARM_TYPE = [
    "None","Central Station Monitored","Direct to Fire Department",
    "Proprietary System","Local Alarm Only",
]
VEHICLE_CLASS = [
    "Trailer","Light Truck","Extra Heavy Truck","Medium Truck","Heavy Truck",
    "Private Passenger",
]
CDL_CLASS = ["A","B"]
SEX = ["M","F"]
ENTITY_TYPE = ["Corporation","LLC","Limited Partnership"]
POLICY_FORM_TYPE = ["special"]
CHECKBOX_VALUE = ["Yes","No"]
CANCELLATION_REASON = [
    "Insured's Request","Non-Renewal","Other","Underwriting",
]
LOSS_RUN_STATUS = [
    "Open","Closed","Denied","Subrogation","Re-opened","Closed Without Payment",
]
LOSS_RUN_COVERAGE = ["wc","gl","auto","property","umbrella","mtc"]
MVR_STATUS = ["Clear","Minor Violations","Major Violations","Accident"]
ENGR_PRIORITY = ["Severe","Necessary","Advisable"]
ENGR_CATEGORY = [
    "structural","electrical","fire_protection","security","maintenance",
    "documentation",
]
WC_INDIVIDUAL_STATUS = ["Included","Excluded"]


# ── Strict-schema helpers ──────────────────────────────────────────────


def obj(properties: dict, *, allow_extra: bool = False) -> dict:
    """Build a strict object schema. Every property is required."""
    schema = {
        "type": "object",
        "properties": properties,
        "required": list(properties.keys()),
        "additionalProperties": allow_extra,
    }
    return schema


def nstr() -> dict:
    return {"type": ["string", "null"]}


def nnum() -> dict:
    return {"type": ["number", "null"]}


def nbool() -> dict:
    return {"type": ["boolean", "null"]}


def nint() -> dict:
    return {"type": ["integer", "null"]}


def nenum(values: list[str]) -> dict:
    return {"type": ["string", "null"], "enum": [*values, None]}


def nenum_blank(values: list[str]) -> dict:
    """Like nenum but also accepts empty string. For tabular columns where
    a blank cell is a real document phenomenon (e.g. SOV state column when
    the row's address line embeds the state, or driver_schedule cdl_class
    when a driver has no CDL). Generator emits "" not null because the
    rendered cell is visually empty, not absent."""
    return {"type": ["string", "null"], "enum": [*values, "", None]}


def arr(item_schema: dict) -> dict:
    return {"type": "array", "items": item_schema}


def narr(item_schema: dict) -> dict:
    """Nullable array (rare; most arrays are required, possibly empty)."""
    return {"type": ["array", "null"], "items": item_schema}


# Reusable substructures

def header_block(*, with_carrier=True, with_policy_period=True,
                 with_policy_number=True, extra: dict | None = None) -> dict:
    props = {
        "insured_name": nstr(),
        "insured_address": nstr(),
        "insured_city": nstr(),
        "insured_state": nenum(US_STATES),
        "insured_zip": nstr(),
    }
    if with_carrier:
        props["carrier_name"] = nstr()
    if with_policy_number:
        props["policy_number"] = nstr()
    if with_policy_period:
        props["policy_period_start"] = nstr()
        props["policy_period_end"] = nstr()
    if extra:
        props.update(extra)
    return obj(props)


def checkboxes_array() -> dict:
    """Array-of-pairs replacement for the legacy keyed checkboxes dict."""
    return arr(obj({
        "field": {"type": "string"},
        "value": {"type": "string", "enum": CHECKBOX_VALUE},
    }))


def coverages_requested_block() -> dict:
    return arr(obj({
        "coverage_type": nstr(),
        "limit": {"type": ["string", "null"]},
        "deductible": nnum(),
        "premium": nnum(),
    }))


# ── Non-ACORD schemas (§1-A) ───────────────────────────────────────────


def loss_run_schema() -> dict:
    claim_obj = obj({
        "claim_number": nstr(),
        "date_of_loss": nstr(),
        "claimant": nstr(),
        "status": nenum(LOSS_RUN_STATUS),
        "coverage": nenum(LOSS_RUN_COVERAGE),
        "paid": nnum(),
        "reserved": nnum(),
        "incurred": nnum(),
        "description": nstr(),
    })
    sub_obj = obj({
        "paid": nnum(),
        "reserved": nnum(),
        "incurred": nnum(),
        "claim_count": nint(),
    })
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "loss_run",
        **obj({
            "header": obj({
                "insured_name": nstr(),
                "carrier_name": nstr(),
                "policy_numbers": obj({
                    cov: nstr() for cov in LOSS_RUN_COVERAGE
                }),
                "report_date": nstr(),
                "policy_period_start": nstr(),
                "policy_period_end": nstr(),
            }),
            "claims": arr(claim_obj),
            "subtotals_by_coverage": obj({
                cov: sub_obj for cov in LOSS_RUN_COVERAGE
            }),
            "grand_totals": obj({
                "paid": nnum(),
                "reserved": nnum(),
                "incurred": nnum(),
                "claim_count": nint(),
            }),
        }),
    }


def sov_schema() -> dict:
    location_obj = obj({
        "location_id": {"type": ["string", "null"]},
        "name": nstr(),
        "address": nstr(),
        "city": nstr(),
        "state": nenum_blank(US_STATES),
        "zip": nstr(),
        # Construction is intentionally a free string here, not an enum.
        # Real SOVs use whatever the broker typed: ACORD-formal names
        # ("Fire Resistive"), IBC codes ("III-B"), abbreviations ("MNC"),
        # ISO 1-6 class numbers ("3"), or tenant-scope flags
        # ("Tenant — contents & BI only"). Forcing the strict ACORD enum
        # would coerce away information that's literally on the page.
        "construction": nstr(),
        "occupancy": nstr(),
        "year_built": nint(),
        "stories": nint(),
        "square_feet": nnum(),
        "sprinklered": nbool(),
        "building_value": nnum(),
        "contents_value": nnum(),
        "bi_value": nnum(),
        "tiv": nnum(),
    })
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "sov",
        **obj({
            "header": obj({
                "insured_name": nstr(),
                "insured_address": nstr(),
                "policy_number": nstr(),
                "policy_period_start": nstr(),
                "policy_period_end": nstr(),
                "carrier_name": nstr(),
            }),
            "locations": arr(location_obj),
            "totals": obj({
                "building_value": nnum(),
                "contents_value": nnum(),
                "bi_value": nnum(),
                "tiv": nnum(),
                "location_count": nint(),
            }),
        }),
    }


def dec_page_schema() -> dict:
    coverage_obj = obj({
        "coverage_type": nstr(),
        "coverage_code": nstr(),
        "limit": {"type": ["string", "null"]},
        "deductible": nnum(),
        "premium": nnum(),
        "form_numbers": arr({"type": "string"}),
    })
    location_obj = obj({
        "location_number": {"type": ["string", "null"]},
        "address": nstr(),
        "city": nstr(),
        "state": nenum(US_STATES),
        "zip": nstr(),
        "description": nstr(),
    })
    endorsement_obj = obj({
        "form_number": nstr(),
        "title": nstr(),
    })
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "dec_page",
        **obj({
            "policy_info": obj({
                "policy_number": nstr(),
                "policy_type": nstr(),  # §4-C: dropped enum
                "effective_date": nstr(),
                "expiration_date": nstr(),
                "carrier_name": nstr(),
                "carrier_naic": nstr(),
            }),
            "insured": obj({
                "name": nstr(),
                "dba": nstr(),
                "address": nstr(),
                "city": nstr(),
                "state": nenum(US_STATES),
                "zip": nstr(),
                "entity_type": nenum(ENTITY_TYPE),
            }),
            "producer": obj({
                "name": nstr(),
                "address": nstr(),
                "code": nstr(),
            }),
            "coverages": arr(coverage_obj),
            "locations": arr(location_obj),
            "premium_summary": obj({
                "total_premium": nnum(),
                "taxes_fees": nnum(),
                "total_due": nnum(),
            }),
            "endorsements": arr(endorsement_obj),
            "forms_attached": arr({"type": "string"}),
        }),
    }


def driver_schedule_schema() -> dict:
    driver_obj = obj({
        "name": nstr(),
        "date_of_birth": nstr(),
        "sex": nenum(SEX),
        "license_number": nstr(),
        "license_state": nenum(US_STATES),
        "license_class": nstr(),  # §4-C: dropped enum
        "license_expiration": nstr(),
        "hire_date": nstr(),
        "years_experience": nnum(),
        "mvr_status": nenum(MVR_STATUS),
        "violations_count": nint(),
        "accidents_count": nint(),
        "endorsements": arr({"type": "string"}),  # §4-C: free
        "assigned_vehicle": nstr(),
        "excluded": nbool(),
    })
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "driver_schedule",
        **obj({
            "header": obj({
                "insured_name": nstr(),
                "policy_number": nstr(),
                "effective_date": nstr(),
                "as_of_date": nstr(),
            }),
            "drivers": arr(driver_obj),
            "summary": obj({
                "total_drivers": nint(),
                "cdl_drivers": nint(),
                "clear_mvr_count": nint(),
                "drivers_with_violations": nint(),
                "drivers_with_accidents": nint(),
                "excluded_drivers": nint(),
            }),
        }),
    }


def engineering_report_schema() -> dict:
    location_obj = obj({
        "name": nstr(),
        "address": nstr(),
        "city": nstr(),
        "state": nenum(US_STATES),
        # Construction left as a free string; engineering reports often quote
        # the SOV's verbatim construction value (IBC code / abbreviation /
        # ISO class) rather than re-mapping to ACORD-formal names.
        "construction": nstr(),
        "occupancy": nstr(),
        "year_built": nint(),
        "stories": nint(),
        "square_feet": nnum(),
        "sprinklered": nbool(),
        "protection_class": nint(),
        "condition_rating": nstr(),
        "findings": arr({"type": "string"}),
        "deficiencies": arr({"type": "string"}),
    })
    rec_obj = obj({
        "priority": nenum(ENGR_PRIORITY),
        "category": nenum(ENGR_CATEGORY),
        "description": nstr(),
        "estimated_cost": nnum(),
        "deadline": nstr(),
    })
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "engineering_report",
        **obj({
            "report_info": obj({
                "report_type": nstr(),  # §4-C dropped enum
                "report_date": nstr(),
                "inspector_name": nstr(),
                "inspector_company": nstr(),
                "risk_grade": nstr(),
                "grading_scale": nstr(),
            }),
            "insured": obj({
                "name": nstr(),
                "address": nstr(),
                "city": nstr(),
                "state": nenum(US_STATES),
                "zip": nstr(),
            }),
            "carrier_info": obj({
                "carrier_name": nstr(),
                "policy_number": nstr(),
                "policy_period_start": nstr(),
                "policy_period_end": nstr(),
            }),
            "locations_inspected": arr(location_obj),
            "recommendations": arr(rec_obj),
            "overall_assessment": obj({
                "summary": nstr(),
                "risk_level": nstr(),       # §4-C dropped enum
                "insurability": nstr(),     # §4-C dropped enum
            }),
        }),
    }


def financial_statement_schema() -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "financial_statement",
        **obj({
            "header": obj({
                "company_name": nstr(),
                "statement_type": nstr(),   # §4-D / §4-G drop enum
                "period_end_date": nstr(),
                "period_type": nstr(),      # §4-C drop enum
                "fiscal_year": nint(),
                "audited": nbool(),
                "preparer": nstr(),
            }),
            "balance_sheet": obj({
                "assets": obj({
                    "current_assets": obj({
                        "cash": nnum(),
                        "accounts_receivable": nnum(),
                        "inventory": nnum(),
                        "prepaid_expenses": nnum(),
                        "other_current": nnum(),
                        "total_current_assets": nnum(),
                    }),
                    "fixed_assets": obj({
                        "property_plant_equipment": nnum(),
                        "accumulated_depreciation": nnum(),
                        "net_fixed_assets": nnum(),
                    }),
                    "other_assets": nnum(),
                    "total_assets": nnum(),
                }),
                "liabilities": obj({
                    "current_liabilities": obj({
                        "accounts_payable": nnum(),
                        "accrued_expenses": nnum(),
                        "current_debt": nnum(),
                        "other_current": nnum(),
                        "total_current_liabilities": nnum(),
                    }),
                    "long_term_liabilities": obj({
                        "long_term_debt": nnum(),
                        "other_long_term": nnum(),
                        "total_long_term": nnum(),
                    }),
                    "total_liabilities": nnum(),
                }),
                "equity": obj({
                    "common_stock": nnum(),
                    "retained_earnings": nnum(),
                    "total_equity": nnum(),
                }),
            }),
            "income_statement": obj({
                "revenue": obj({
                    "gross_revenue": nnum(),
                    "net_revenue": nnum(),
                }),
                "cost_of_goods_sold": nnum(),
                "gross_profit": nnum(),
                "operating_expenses": obj({
                    "salaries_wages": nnum(),
                    "rent": nnum(),
                    "utilities": nnum(),
                    "depreciation": nnum(),
                    "insurance": nnum(),
                    "other_operating": nnum(),
                    "total_operating_expenses": nnum(),
                }),
                "operating_income": nnum(),
                "interest_expense": nnum(),
                "income_before_tax": nnum(),
                "income_tax": nnum(),
                "net_income": nnum(),
            }),
            "ratios": obj({
                "current_ratio": nnum(),
                "debt_to_equity": nnum(),
                "profit_margin": nnum(),
            }),
        }),
    }


def narrative_schema() -> dict:
    coverage_obj = obj({
        "coverage_type": nstr(),
        "current_limit": {"type": ["string", "null"]},
        "requested_limit": {"type": ["string", "null"]},
        "current_carrier": nstr(),
        "expiring_premium": nnum(),
        "notes": nstr(),
    })
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "narrative",
        **obj({
            "document_info": obj({
                "document_type": nstr(),   # §4-C drop enum
                "date": nstr(),
                "prepared_by": nstr(),
                "recipient": nstr(),
            }),
            "insured": obj({
                "name": nstr(),
                "address": nstr(),
                "city": nstr(),
                "state": nenum(US_STATES),
                "zip": nstr(),
            }),
            "business_description": obj({
                "nature_of_business": nstr(),
                "sic_code": nstr(),
                "naics_code": nstr(),
                "years_in_business": nint(),
                "annual_revenue": nnum(),
                "employee_count": nint(),
            }),
            "coverages_discussed": arr(coverage_obj),
            "risk_highlights": obj({
                "positives": arr({"type": "string"}),
                "concerns": arr({"type": "string"}),
                "loss_history_summary": nstr(),
            }),
            "locations_summary": obj({
                "location_count": nint(),
                "states_of_operation": arr({"type": "string", "enum": US_STATES}),
                "total_insured_value": nnum(),
            }),
            "fleet_summary": obj({
                "vehicle_count": nint(),
                "driver_count": nint(),
                "radius_of_operation": nstr(),
            }),
            "key_dates": obj({
                "current_policy_effective": nstr(),
                "current_policy_expiration": nstr(),
                "requested_effective": nstr(),
            }),
            "extracted_text_sections": obj({
                "executive_summary": nstr(),
                "operations_description": nstr(),
                "safety_programs": nstr(),
                "claims_narrative": nstr(),
            }),
        }),
    }


# ── ACORD per-form schemas (§1-B) ──────────────────────────────────────


def acord_base_form_info() -> dict:
    return obj({
        "form_number": nstr(),
        "form_edition": nstr(),
        "form_title": nstr(),
    })


def acord_base_header(*, with_producer=True) -> dict:
    props = {
        "insured_name": nstr(),
        "insured_address": nstr(),
        "insured_city": nstr(),
        "insured_state": nenum(US_STATES),
        "insured_zip": nstr(),
        "carrier_name": nstr(),
        "policy_number": nstr(),
        "effective_date": nstr(),
        "expiration_date": nstr(),
    }
    if with_producer:
        props["producer_name"] = nstr()
        props["producer_code"] = nstr()
    return obj(props)


def remarks_field() -> tuple[str, dict]:
    return "remarks", nstr()


def applicant_info(*, with_entity_type=True) -> dict:
    props = {
        "fein": nstr(),
        "sic_code": nstr(),
        "naics_code": nstr(),
        "years_in_business": nint(),
        "nature_of_business": nstr(),
    }
    if with_entity_type:
        props["entity_type"] = nenum(ENTITY_TYPE)
    return obj(props)


def acord_premises_obj() -> dict:
    return obj({
        "location_number": {"type": ["string", "null"]},
        "address": nstr(),
        "city": nstr(),
        "state": nenum(US_STATES),
        "zip": nstr(),
        "construction": nenum(CONSTRUCTION),
        "occupancy": nstr(),
        "year_built": nint(),
        "stories": nint(),
        "square_feet": nnum(),
        "sprinklered": nbool(),
        "roof_type": nenum(ROOF_TYPE),
        "sprinkler_type": nenum(SPRINKLER_TYPE),
        "fire_alarm_type": nenum(FIRE_ALARM_TYPE),
        "building_value": nnum(),
        "contents_value": nnum(),
        "bi_value": nnum(),
        "tiv": nnum(),
    })


def acord_vehicle_obj() -> dict:
    return obj({
        "vehicle_id": {"type": ["string", "null"]},
        "year": nint(),
        "make": nstr(),
        "model": nstr(),
        "vin": nstr(),
        "vehicle_class": nenum(VEHICLE_CLASS),
        "garage_state": nenum(US_STATES),
        "stated_value": nnum(),
    })


def acord_driver_obj() -> dict:
    return obj({
        "name": nstr(),
        "date_of_birth": nstr(),
        "sex": nenum(SEX),
        "license_number": nstr(),
        "license_state": nenum(US_STATES),
        "cdl_class": nenum_blank(CDL_CLASS),
        "mvr_status": nenum(MVR_STATUS),
    })


def acord_schema(form_number: str, body: dict) -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": f"acord_{form_number}",
        **obj(body),
    }


def acord_101() -> dict:
    """101 — Additional Remarks Schedule."""
    return acord_schema("101", {
        "form_info": acord_base_form_info(),
        "header": acord_base_header(),
        "applicant_info": applicant_info(),
        "additional_remarks": arr(obj({
            "section_reference": nstr(),
            "remark": nstr(),
        })),
        "checkboxes": checkboxes_array(),
        "remarks": nstr(),
    })


def acord_125() -> dict:
    """125 — Commercial Insurance Application."""
    return acord_schema("125", {
        "form_info": acord_base_form_info(),
        "header": acord_base_header(),
        "applicant_info": applicant_info(),
        "premises": arr(acord_premises_obj()),
        "uw_questions": arr(obj({
            "question": nstr(),
            "answer": nstr(),
        })),
        "coverages_requested": coverages_requested_block(),
        "checkboxes": checkboxes_array(),
        "remarks": nstr(),
    })


def acord_126() -> dict:
    """126 — Commercial General Liability."""
    return acord_schema("126", {
        "form_info": acord_base_form_info(),
        "header": acord_base_header(),
        "applicant_info": applicant_info(with_entity_type=False),
        "gl_class_codes": arr(obj({
            "class_code": nstr(),
            "description": nstr(),
            "premium_basis": nstr(),
            "exposure": nnum(),
            "rate": nnum(),
            "premium": nnum(),
        })),
        "gl_limits": obj({
            "each_occurrence": nnum(),
            "general_aggregate": nnum(),
            "products_completed_ops": nnum(),
            "personal_advertising": nnum(),
            "damage_rented_premises": nnum(),
            "medical_expense": nnum(),
        }),
        "gl_premium": obj({
            "base_premium": nnum(),
            "tria_surcharge": nnum(),
            "total_premium": nnum(),
            "deductible": nnum(),
            "form_type": nstr(),
        }),
        "coverages_requested": coverages_requested_block(),
        "checkboxes": checkboxes_array(),
        "remarks": nstr(),
    })


def acord_127() -> dict:
    """127 — Business Auto."""
    return acord_schema("127", {
        "form_info": acord_base_form_info(),
        "header": acord_base_header(),
        "applicant_info": applicant_info(with_entity_type=False),
        "vehicles": arr(acord_vehicle_obj()),
        "drivers": arr(acord_driver_obj()),
        "auto_limits": obj({
            "combined_single_limit": nnum(),
            "uninsured_motorist": nnum(),
            "medical_payments": nnum(),
        }),
        "auto_premium": obj({
            "base_premium": nnum(),
            "tria_surcharge": nnum(),
            "total_premium": nnum(),
            "deductible": nnum(),
            "form_type": nstr(),
        }),
        "coverages_requested": coverages_requested_block(),
        "checkboxes": checkboxes_array(),
        "remarks": nstr(),
    })


def acord_130() -> dict:
    """130 — Workers Compensation Application (categorized as narrative in GT,
    but kept as its own ACORD schema per §1-B). Includes Included/Excluded
    individuals (§4-H).
    """
    return acord_schema("130", {
        "form_info": acord_base_form_info(),
        "header": acord_base_header(),
        "applicant_info": applicant_info(),
        "wc_class_codes": arr(obj({
            "class_code": nstr(),
            "description": nstr(),
            "state": nenum(US_STATES),
            "payroll": nnum(),
            "rate": nnum(),
            "premium": nnum(),
        })),
        "individuals": arr(obj({
            "name": nstr(),
            "title": nstr(),
            "status": {"type": ["string", "null"], "enum": [*WC_INDIVIDUAL_STATUS, None]},
        })),
        "experience_mod": nnum(),
        "wc_premium": obj({
            "base_premium": nnum(),
            "total_premium": nnum(),
        }),
        "checkboxes": checkboxes_array(),
        "remarks": nstr(),
    })


def acord_131() -> dict:
    """131 — Umbrella / Excess. §2-L: only `state` enum; umbrella_form_type
    has N=1 in current corpus, kept as free string."""
    return acord_schema("131", {
        "form_info": acord_base_form_info(),
        "header": acord_base_header(),
        "applicant_info": applicant_info(with_entity_type=False),
        "underlying_policies": arr(obj({
            "carrier": nstr(),
            "policy_number": nstr(),
            "coverage_type": nstr(),
            "limit": nnum(),
        })),
        "umbrella_limits": obj({
            "per_occurrence": nnum(),
            "aggregate": nnum(),
            "retention": nnum(),
        }),
        "umbrella_premium": nnum(),
        "umbrella_form_type": nstr(),  # v2-generator note: expand for enum
        "checkboxes": checkboxes_array(),
        "remarks": nstr(),
    })


def acord_133() -> dict:
    """133 — Workers Compensation State Supplement. §2-L: only `state` enum."""
    return acord_schema("133", {
        "form_info": acord_base_form_info(),
        "header": acord_base_header(),
        "applicant_info": applicant_info(),
        "state": nenum(US_STATES),
        "class_codes": arr(obj({
            "class_code": nstr(),
            "description": nstr(),
            "payroll": nnum(),
            "rate": nnum(),
            "premium": nnum(),
        })),
        "experience_mod": nnum(),
        "total_premium": nnum(),
        "checkboxes": checkboxes_array(),
        "remarks": nstr(),
    })


def acord_137() -> dict:
    """137 — Vehicle Schedule (commercial auto)."""
    return acord_schema("137", {
        "form_info": acord_base_form_info(),
        "header": acord_base_header(),
        "applicant_info": applicant_info(with_entity_type=False),
        "vehicles": arr(acord_vehicle_obj()),
        "auto_limits": obj({
            "combined_single_limit": nnum(),
            "uninsured_motorist": nnum(),
            "medical_payments": nnum(),
        }),
        "auto_premium": obj({
            "base_premium": nnum(),
            "tria_surcharge": nnum(),
            "total_premium": nnum(),
            "deductible": nnum(),
            "form_type": nstr(),
        }),
        "checkboxes": checkboxes_array(),
        "remarks": nstr(),
    })


def acord_140() -> dict:
    """140 — Property Section. Promotes 5 vocabularies (§2-H)."""
    return acord_schema("140", {
        "form_info": acord_base_form_info(),
        "header": acord_base_header(),
        "applicant_info": applicant_info(with_entity_type=False),
        "locations": arr(acord_premises_obj()),
        "blanket_summary": obj({
            "blanket_number": nstr(),
            "blanket_type": nstr(),
            "blanket_limit": nnum(),
        }),
        "interest_holders": arr(obj({
            "name": nstr(),
            "address": nstr(),
            "interest_type": nstr(),
            "loan_number": nstr(),
        })),
        "property_premium": nnum(),
        "property_deductible": nnum(),
        "valuation_method": nstr(),
        "coinsurance": nnum(),
        "checkboxes": checkboxes_array(),
        "remarks": nstr(),
    })


def acord_160() -> dict:
    """160 — Contractor Supplement (uses applicant entity_type, construction)."""
    return acord_schema("160", {
        "form_info": acord_base_form_info(),
        "header": acord_base_header(),
        "applicant_info": applicant_info(),
        "locations": arr(acord_premises_obj()),
        "additional_coverages": arr(obj({
            "coverage_type": nstr(),
            "limit": nnum(),
            "premium": nnum(),
        })),
        "interests": arr(obj({
            "name": nstr(),
            "loan_number": nstr(),
            "interest_type": nstr(),
        })),
        "property_premium": nnum(),
        "property_deductible": nnum(),
        "total_tiv": nnum(),
        "checkboxes": checkboxes_array(),
        "remarks": nstr(),
    })


def acord_23() -> dict:
    """23 — Vehicle Certificate of Insurance."""
    return acord_schema("23", {
        "form_info": acord_base_form_info(),
        "header": acord_base_header(),
        "vehicles": arr(acord_vehicle_obj()),
        "auto_limits": obj({
            "combined_single_limit": nnum(),
            "uninsured_motorist": nnum(),
            "medical_payments": nnum(),
        }),
        "auto_deductible": nnum(),
        "insurer_panel": arr(obj({
            "carrier": nstr(),
            "naic": nstr(),
        })),
        "checkboxes": checkboxes_array(),
        "remarks": nstr(),
    })


def acord_24() -> dict:
    """24 — Certificate of Property Insurance."""
    return acord_schema("24", {
        "form_info": acord_base_form_info(),
        "header": acord_base_header(),
        "document_date": nstr(),
        "policy_form_type": nenum(POLICY_FORM_TYPE),
        "locations": arr(acord_premises_obj()),
        "property_limits": obj({
            "building": nnum(),
            "contents": nnum(),
            "business_income": nnum(),
        }),
        "property_deductible": nnum(),
        "insurer_panel": arr(obj({
            "carrier": nstr(),
            "naic": nstr(),
        })),
        "checkboxes": checkboxes_array(),
        "remarks": nstr(),
    })


def acord_25() -> dict:
    """25 — Certificate of Liability Insurance (cert of insurance, free
    long-form coverage strings per §1-B)."""
    return acord_schema("25", {
        "form_info": acord_base_form_info(),
        "header": acord_base_header(),
        "document_date": nstr(),
        "certificate_holders": arr(obj({
            "name": nstr(),
            "address": nstr(),
        })),
        "carrier_name_per_lob": arr(obj({
            "lob": nstr(),
            "carrier": nstr(),
            "naic": nstr(),
            "policy_number": nstr(),
        })),
        "coverages_certified": arr(obj({
            "coverage_type": nstr(),
            "policy_number": nstr(),
            "effective_date": nstr(),
            "expiration_date": nstr(),
            "limit": {"type": ["string", "null"]},
        })),
        "checkboxes": checkboxes_array(),
        "remarks": nstr(),
    })


def acord_27() -> dict:
    """27 — Evidence of Property Insurance."""
    return acord_schema("27", {
        "form_info": acord_base_form_info(),
        "header": acord_base_header(),
        "document_date": nstr(),
        "policy_form_type": nenum(POLICY_FORM_TYPE),
        "locations": arr(acord_premises_obj()),
        "property_deductible": nnum(),
        "interests": arr(obj({
            "name": nstr(),
            "address": nstr(),
            "interest_type": nstr(),
            "loan_number": nstr(),
        })),
        "checkboxes": checkboxes_array(),
        "remarks": nstr(),
    })


def acord_28() -> dict:
    """28 — Evidence of Commercial Property Insurance."""
    return acord_schema("28", {
        "form_info": acord_base_form_info(),
        "header": acord_base_header(),
        "policy_form_type": nenum(POLICY_FORM_TYPE),
        "cause_of_loss": nstr(),
        "coinsurance": nnum(),
        "naic_code": nstr(),
        "cancellation_notice_days": nint(),
        "loan_number": nstr(),
        "locations": arr(acord_premises_obj()),
        "location_totals": obj({
            "building": nnum(),
            "contents": nnum(),
            "business_income": nnum(),
            "tiv": nnum(),
        }),
        "interest_holders": arr(obj({
            "name": nstr(),
            "address": nstr(),
            "interest_type": nstr(),
            "loan_number": nstr(),
        })),
        "property_deductible": nnum(),
        "checkboxes": checkboxes_array(),
        "remarks": nstr(),
    })


def acord_35() -> dict:
    """35 — Cancellation Request / Policy Release. New cancellation_reason
    enum per §2-L."""
    return acord_schema("35", {
        "form_info": acord_base_form_info(),
        "header": acord_base_header(),
        "document_date": nstr(),
        "producer_phone": nstr(),
        "producer_fax": nstr(),
        "producer_license_number": nstr(),
        "cancellation_date": nstr(),
        "cancellation_reason": nenum(CANCELLATION_REASON),
        "checkboxes": checkboxes_array(),
        "remarks": nstr(),
    })


def acord_45() -> dict:
    """45 — Increased Limits Underlying Carriers (uses construction)."""
    return acord_schema("45", {
        "form_info": acord_base_form_info(),
        "header": acord_base_header(),
        "locations": arr(acord_premises_obj()),
        "underlying_carriers": arr(obj({
            "carrier": nstr(),
            "policy_number": nstr(),
            "coverage_type": nstr(),
            "limit": nnum(),
        })),
        "checkboxes": checkboxes_array(),
        "remarks": nstr(),
    })


def acord_75() -> dict:
    """75 — Insurance Binder (cert of insurance, long-form coverage strings
    per §1-B)."""
    return acord_schema("75", {
        "form_info": acord_base_form_info(),
        "header": acord_base_header(),
        "binder_number": nstr(),
        "binder_date": nstr(),
        "expiring_carriers": arr(obj({
            "lob": nstr(),
            "carrier": nstr(),
            "policy_number": nstr(),
        })),
        "endorsements": arr(obj({
            "form_number": nstr(),
            "title": nstr(),
            "coverage": nstr(),
        })),
        "mortgagees": arr(obj({
            "name": nstr(),
            "address": nstr(),
            "loan_number": nstr(),
        })),
        "property_premium": nnum(),
        "property_deductible": nnum(),
        "form_type_property": nstr(),
        "limit_property_building": nnum(),
        "limit_property_contents": nnum(),
        "limit_property_business_income": nnum(),
        "limit_property_coinsurance": nnum(),
        "coinsurance_property": nnum(),
        "checkboxes": checkboxes_array(),
        "remarks": nstr(),
    })


def acord_823() -> dict:
    """823 — Agent of Record / Notice of Cancellation. §2-L: state only."""
    return acord_schema("823", {
        "form_info": acord_base_form_info(),
        "header": acord_base_header(),
        "policy_number": nstr(),
        "start_date": nstr(),
        "checkboxes": checkboxes_array(),
        "remarks": nstr(),
    })


SCHEMAS = {
    # Non-ACORD (§1-A)
    "loss_run.schema.json": loss_run_schema,
    "sov.schema.json": sov_schema,
    "dec_page.schema.json": dec_page_schema,
    "driver_schedule.schema.json": driver_schedule_schema,
    "engineering_report.schema.json": engineering_report_schema,
    "financial_statement.schema.json": financial_statement_schema,
    "narrative.schema.json": narrative_schema,
    # ACORD per-form (§1-B)
    "acord_101.schema.json": acord_101,
    "acord_125.schema.json": acord_125,
    "acord_126.schema.json": acord_126,
    "acord_127.schema.json": acord_127,
    "acord_130.schema.json": acord_130,
    "acord_131.schema.json": acord_131,
    "acord_133.schema.json": acord_133,
    "acord_137.schema.json": acord_137,
    "acord_140.schema.json": acord_140,
    "acord_160.schema.json": acord_160,
    "acord_23.schema.json": acord_23,
    "acord_24.schema.json": acord_24,
    "acord_25.schema.json": acord_25,
    "acord_27.schema.json": acord_27,
    "acord_28.schema.json": acord_28,
    "acord_35.schema.json": acord_35,
    "acord_45.schema.json": acord_45,
    "acord_75.schema.json": acord_75,
    "acord_823.schema.json": acord_823,
}


def main():
    for filename, builder in SCHEMAS.items():
        schema = builder()
        path = OUT_DIR / filename
        path.write_text(json.dumps(schema, indent=2) + "\n")
        print(f"  wrote {filename}")
    print(f"\nTotal: {len(SCHEMAS)} schemas")


if __name__ == "__main__":
    main()
