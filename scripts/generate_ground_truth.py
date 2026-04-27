#!/usr/bin/env python3
"""Generate packet ground truth from generator output.

Reads ALL per-document ground truth JSON files emitted by the generator
and converts to packet format: one consolidated JSON file per packet
containing all document types.

Usage:
    python scripts/generate_ground_truth.py \
        --generator-output ~/Desktop/villify/output/nightmare \
        --output-dir ground_truth/
"""

import argparse
import json
from pathlib import Path


# ── Document Type Mapping ──────────────────────────────────────────────

DOC_TYPE_CATEGORIES = {
    # SOV / Property Schedule
    "sov": "sov",
    "sov_excel": "sov",

    # Loss Runs
    "loss_run": "loss_run",
    "loss_run_excel": "loss_run",
    "loss_run_csv": "loss_run",

    # ACORD Forms
    "acord_101": "acord_form",
    "acord_125": "acord_form",
    "acord_126": "acord_form",
    "acord_127": "acord_form",
    "acord_131": "acord_form",
    "acord_133": "acord_form",
    "acord_137": "acord_form",
    "acord_140": "acord_form",
    "acord_160": "acord_form",
    "acord_23": "acord_form",
    "acord_24": "acord_form",
    "acord_25": "acord_form",
    "acord_27": "acord_form",
    "acord_28": "acord_form",
    "acord_35": "acord_form",
    "acord_45": "acord_form",
    "acord_75": "acord_form",

    # Engineering / Inspection
    "engineering_report": "engineering_report",

    # Declarations
    "dec_page": "dec_page",

    # Driver Schedule
    "driver_schedule": "driver_schedule",
    "driver_schedule_excel": "driver_schedule",

    # Financial
    "financial_statement": "financial_statement",
    "financial_statement_excel": "financial_statement",

    # Supplemental / Narrative
    "broker_narrative": "narrative",
    "supplemental_app": "narrative",
    "supplemental_app_trucking": "narrative",
    "policy_form": "narrative",

    # Excel workbooks
    "hybrid_workbook": "workbook",
    "supplemental_schedule_excel": "workbook",
    "experience_mod_excel": "workbook",
}

PROMPT_MAPPING = {
    "sov": "sov_extraction.md",
    "loss_run": "loss_run_extraction.md",
    "acord_form": "acord_form_extraction.md",
    "engineering_report": "engineering_report_extraction.md",
    "dec_page": "dec_page_extraction.md",
    "driver_schedule": "driver_schedule_extraction.md",
    "financial_statement": "financial_statement_extraction.md",
    "narrative": "narrative_extraction.md",
    "workbook": "narrative_extraction.md",  # fallback
}


# ── Generic Ground Truth Extraction ───────────────────────────────────


def extract_generic_ground_truth(gt_path: Path, doc_type: str) -> dict:
    """Extract ground truth from any generator field_truth JSON file."""
    data = json.loads(gt_path.read_text())

    # Determine category and prompt
    category = DOC_TYPE_CATEGORIES.get(doc_type, "narrative")
    prompt_file = PROMPT_MAPPING.get(category, "narrative_extraction.md")

    result = {
        "doc_type": doc_type,
        "category": category,
        "prompt_file": prompt_file,
        "source_file": gt_path.name,
        "raw_ground_truth": data,  # Include full raw data for flexible scoring
    }

    # Extract common header fields if present
    fields = data.get("fields", {})
    result["header"] = {
        "insured_name": fields.get("insured_name", {}).get("value"),
        "insured_address": fields.get("insured_address", {}).get("value"),
        "insured_city": fields.get("insured_city", {}).get("value"),
        "insured_state": fields.get("insured_state", {}).get("value"),
        "insured_zip": fields.get("insured_zip", {}).get("value"),
        "carrier_name": fields.get("carrier_name", {}).get("value"),
        "policy_period_start": fields.get("policy_period_start", {}).get("value"),
        "policy_period_end": fields.get("policy_period_end", {}).get("value"),
    }

    # Add policy numbers if present
    policy_numbers = {}
    for key, val in fields.items():
        if key.startswith("policy_number"):
            lob = key.replace("policy_number_", "").replace("policy_number", "primary")
            policy_numbers[lob] = val.get("value") if isinstance(val, dict) else val
    if policy_numbers:
        result["header"]["policy_numbers"] = policy_numbers

    # Category-specific extraction
    if category == "sov":
        result.update(extract_sov_specific(data))
    elif category == "loss_run":
        result.update(extract_loss_run_specific(data))
    elif category == "engineering_report":
        result.update(extract_engineering_specific(data))
    elif category == "driver_schedule":
        result.update(extract_driver_schedule_specific(data))
    elif category == "acord_form":
        result.update(extract_acord_specific(data, doc_type))
    elif category == "dec_page":
        result.update(extract_dec_page_specific(data))
    elif category == "financial_statement":
        result.update(extract_financial_specific(data))

    return result


# ── SOV Extraction ─────────────────────────────────────────────────────


def extract_sov_specific(data: dict) -> dict:
    """Extract SOV-specific ground truth."""
    # Prefer excel_metadata.locations if available
    if "excel_metadata" in data and "locations" in data["excel_metadata"]:
        raw_locations = data["excel_metadata"]["locations"]
    else:
        raw_locations = data.get("locations", [])

    locations = []
    for loc in raw_locations:
        locations.append({
            "location_id": loc.get("schedule_id") or loc.get("original_schedule_id", ""),
            "name": loc.get("name"),
            "address": loc.get("address", ""),
            "city": loc.get("city", ""),
            "state": loc.get("state", ""),
            "zip": loc.get("zip_code"),
            "construction": loc.get("construction"),
            "occupancy": loc.get("occupancy"),
            "year_built": loc.get("year_built"),
            "stories": loc.get("stories"),
            "square_feet": loc.get("square_feet"),
            "sprinklered": loc.get("sprinklered") if loc.get("sprinkler") is None else loc.get("sprinkler") == "Yes",
            "building_value": loc.get("building_value", 0),
            "contents_value": loc.get("contents_value", 0),
            "bi_value": loc.get("bi_value"),
            "tiv": loc.get("tiv", 0),
            "is_sub_building": loc.get("is_sub_building", False),
        })

    # Calculate totals
    total_building = sum(loc.get("building_value", 0) or 0 for loc in locations)
    total_contents = sum(loc.get("contents_value", 0) or 0 for loc in locations)
    total_bi = sum(loc.get("bi_value", 0) or 0 for loc in locations)
    total_tiv = sum(loc.get("tiv", 0) or 0 for loc in locations)

    if "excel_metadata" in data and "true_tiv_values" in data["excel_metadata"]:
        tv = data["excel_metadata"]["true_tiv_values"]
        total_building = tv.get("total_building", total_building)
        total_contents = tv.get("total_contents", total_contents)
        total_bi = tv.get("total_bi", total_bi)
        total_tiv = tv.get("total_tiv", total_tiv)

    return {
        "locations": locations,
        "totals": {
            "building_value": total_building,
            "contents_value": total_contents,
            "bi_value": total_bi,
            "tiv": total_tiv,
            "location_count": len(locations),
        },
        "metadata": {
            "has_sub_buildings": any(loc.get("is_sub_building") for loc in locations),
            "has_zero_building_value": any((loc.get("building_value") or 0) == 0 for loc in locations),
        }
    }


# ── Loss Run Extraction ────────────────────────────────────────────────


def extract_loss_run_specific(data: dict) -> dict:
    """Extract loss run-specific ground truth."""
    raw_claims = data.get("claims", [])

    claims = []
    for claim in raw_claims:
        claims.append({
            "claim_number": claim.get("claim_number", {}).get("value"),
            "date_of_loss": claim.get("date_of_loss", {}).get("value"),
            "claimant": claim.get("claimant", {}).get("value"),
            "status": claim.get("status", {}).get("value"),
            "coverage": claim.get("coverage", {}).get("value"),
            "paid": claim.get("total_paid", {}).get("value", 0),
            "reserved": claim.get("total_reserved", {}).get("value", 0),
            "incurred": claim.get("total_incurred", {}).get("value", 0),
            "description": claim.get("description", {}).get("value"),
        })

    # Subtotals by coverage
    subtotals = {}
    for cov in ["wc", "gl", "auto", "property", "umbrella", "mtc", "professional"]:
        cov_claims = [c for c in claims if c.get("coverage") == cov]
        if cov_claims:
            subtotals[cov] = {
                "paid": sum(c.get("paid", 0) or 0 for c in cov_claims),
                "reserved": sum(c.get("reserved", 0) or 0 for c in cov_claims),
                "incurred": sum(c.get("incurred", 0) or 0 for c in cov_claims),
                "claim_count": len(cov_claims),
            }

    grand_totals = {
        "paid": sum(c.get("paid", 0) or 0 for c in claims),
        "reserved": sum(c.get("reserved", 0) or 0 for c in claims),
        "incurred": sum(c.get("incurred", 0) or 0 for c in claims),
        "claim_count": len(claims),
    }

    return {
        "claims": claims,
        "subtotals_by_coverage": subtotals,
        "grand_totals": grand_totals,
        "metadata": {
            "coverages_present": list(subtotals.keys()),
        }
    }


# ── Engineering Report Extraction ──────────────────────────────────────


def extract_engineering_specific(data: dict) -> dict:
    """Extract engineering report-specific ground truth."""
    fields = data.get("fields", {})
    locations = data.get("locations", [])
    recommendations = data.get("recommendations", [])

    return {
        "report_info": {
            "report_type": fields.get("report_type", {}).get("value"),
            "risk_grade": fields.get("risk_grade", {}).get("value"),
            "grading_scale": fields.get("grading_scale", {}).get("value"),
        },
        "locations_inspected": locations,
        "recommendations": recommendations,
        "metadata": {
            "location_count": data.get("locations_inspected", len(locations)),
            "recommendation_count": data.get("recommendation_count", len(recommendations)),
        }
    }


# ── Driver Schedule Extraction ─────────────────────────────────────────


def extract_driver_schedule_specific(data: dict) -> dict:
    """Extract driver schedule-specific ground truth."""
    drivers = data.get("drivers", [])

    # Normalize driver data
    normalized_drivers = []
    for d in drivers:
        if isinstance(d, dict):
            normalized_drivers.append({
                "name": d.get("name", {}).get("value") if isinstance(d.get("name"), dict) else d.get("name"),
                "license_number": d.get("license_number", {}).get("value") if isinstance(d.get("license_number"), dict) else d.get("license_number"),
                "license_state": d.get("license_state", {}).get("value") if isinstance(d.get("license_state"), dict) else d.get("license_state"),
                "dob": d.get("dob", {}).get("value") if isinstance(d.get("dob"), dict) else d.get("dob"),
                "sex": d.get("sex", {}).get("value") if isinstance(d.get("sex"), dict) else d.get("sex"),
                "hire_date": d.get("hire_date", {}).get("value") if isinstance(d.get("hire_date"), dict) else d.get("hire_date"),
                "mvr_status": d.get("mvr_status", {}).get("value") if isinstance(d.get("mvr_status"), dict) else d.get("mvr_status"),
            })

    return {
        "drivers": normalized_drivers,
        "summary": {
            "total_drivers": len(normalized_drivers),
        }
    }


# ── ACORD Form Extraction ──────────────────────────────────────────────


def extract_acord_specific(data: dict, doc_type: str) -> dict:
    """Extract ACORD form-specific ground truth."""
    fields = data.get("fields", {})

    # Extract form number from doc_type
    form_num = doc_type.replace("acord_", "").upper()

    result = {
        "form_info": {
            "form_number": f"ACORD {form_num}",
            "form_type": doc_type,
        },
        "all_fields": {},
    }

    # Extract all fields with their values
    for key, val in fields.items():
        if isinstance(val, dict) and "value" in val:
            result["all_fields"][key] = val["value"]
        else:
            result["all_fields"][key] = val

    # Extract any lists (locations, vehicles, etc.)
    for key in ["locations", "vehicles", "drivers", "class_codes", "coverages"]:
        if key in data:
            result[key] = data[key]

    return result


# ── Dec Page Extraction ────────────────────────────────────────────────


def extract_dec_page_specific(data: dict) -> dict:
    """Extract dec page-specific ground truth."""
    fields = data.get("fields", {})
    coverages = data.get("coverages", [])
    locations = data.get("locations", [])

    return {
        "coverages": coverages,
        "locations": locations,
        "premium_info": {
            "total_premium": fields.get("total_premium", {}).get("value"),
        },
        "forms": data.get("forms", []),
        "endorsements": data.get("endorsements", []),
    }


# ── Financial Statement Extraction ─────────────────────────────────────


def extract_financial_specific(data: dict) -> dict:
    """Extract financial statement-specific ground truth."""
    return {
        "balance_sheet": data.get("balance_sheet", {}),
        "income_statement": data.get("income_statement", {}),
        "ratios": data.get("ratios", {}),
    }


# ── Packet Processing ──────────────────────────────────────────────────


def find_document_path(docs_dir: Path, doc_type: str, seed: str) -> str | None:
    """Find the document file path for a given doc type."""
    # Try common extensions
    for ext in [".pdf", ".xlsx", ".csv"]:
        # Standard naming: doc_type_seed.ext
        path = docs_dir / f"{doc_type}_{seed}{ext}"
        if path.exists():
            return str(path)

        # Without seed in name
        path = docs_dir / f"{doc_type}{ext}"
        if path.exists():
            return str(path)

    return None


def process_packet(packet_dir: Path, output_dir: Path) -> dict:
    """Process a single packet directory and generate ground truth."""
    gt_dir = packet_dir / "ground_truth"
    docs_dir = packet_dir / "documents"

    if not gt_dir.exists():
        print(f"  SKIP: No ground_truth dir in {packet_dir.name}")
        return {}

    packet_name = packet_dir.parent.name  # e.g., "N5_nightmare"
    seed = packet_dir.name.split("_")[-1]  # e.g., "70005"

    result = {
        "packet_id": f"{packet_name}_{seed}",
        "difficulty": packet_name,
        "seed": seed,
        "documents": {},
        "summary": {
            "total_documents": 0,
            "by_category": {},
        }
    }

    # Process all field_truth files
    for gt_file in sorted(gt_dir.glob("field_truth_*.json")):
        # Extract doc type from filename: field_truth_sov_excel.json -> sov_excel
        doc_type = gt_file.stem.replace("field_truth_", "")

        try:
            doc_gt = extract_generic_ground_truth(gt_file, doc_type)

            # Find document path
            doc_path = find_document_path(docs_dir, doc_type, seed)
            if doc_path:
                doc_gt["document_path"] = doc_path

            result["documents"][doc_type] = doc_gt
            result["summary"]["total_documents"] += 1

            # Track by category
            category = doc_gt.get("category", "other")
            result["summary"]["by_category"][category] = \
                result["summary"]["by_category"].get(category, 0) + 1

        except Exception as e:
            print(f"  ERROR processing {gt_file.name}: {e}")

    # Save packet ground truth
    out_path = output_dir / f"{packet_name}_{seed}.json"
    out_path.write_text(json.dumps(result, indent=2))

    return result


def generate_summary(all_packets: list, output_dir: Path):
    """Generate summary files for the benchmark."""
    import csv

    # CSV summary
    csv_path = output_dir / "ground_truth_summary.csv"
    rows = []

    for packet in all_packets:
        for doc_type, doc_data in packet.get("documents", {}).items():
            row = {
                "packet_id": packet["packet_id"],
                "difficulty": packet["difficulty"],
                "doc_type": doc_type,
                "category": doc_data.get("category", ""),
                "prompt_file": doc_data.get("prompt_file", ""),
            }

            # Add type-specific summary fields
            if doc_data.get("category") == "sov":
                row["entity_count"] = doc_data.get("totals", {}).get("location_count", 0)
                row["total_value"] = doc_data.get("totals", {}).get("tiv", 0)
            elif doc_data.get("category") == "loss_run":
                row["entity_count"] = doc_data.get("grand_totals", {}).get("claim_count", 0)
                row["total_value"] = doc_data.get("grand_totals", {}).get("incurred", 0)
            elif doc_data.get("category") == "driver_schedule":
                row["entity_count"] = doc_data.get("summary", {}).get("total_drivers", 0)
            elif doc_data.get("category") == "engineering_report":
                row["entity_count"] = doc_data.get("metadata", {}).get("location_count", 0)

            rows.append(row)

    fieldnames = ["packet_id", "difficulty", "doc_type", "category", "prompt_file",
                  "entity_count", "total_value"]

    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)

    # Category summary
    category_counts = {}
    for packet in all_packets:
        for cat, count in packet.get("summary", {}).get("by_category", {}).items():
            category_counts[cat] = category_counts.get(cat, 0) + count

    summary_json = {
        "total_packets": len(all_packets),
        "total_documents": sum(p.get("summary", {}).get("total_documents", 0) for p in all_packets),
        "by_category": category_counts,
        "by_difficulty": {},
    }

    for packet in all_packets:
        diff = packet.get("difficulty", "unknown")
        summary_json["by_difficulty"][diff] = \
            summary_json["by_difficulty"].get(diff, 0) + packet.get("summary", {}).get("total_documents", 0)

    (output_dir / "benchmark_summary.json").write_text(json.dumps(summary_json, indent=2))

    print(f"\n  Summary: {summary_json['total_documents']} documents across {summary_json['total_packets']} packets")
    print(f"  By category: {category_counts}")


def main():
    parser = argparse.ArgumentParser(description="Generate packet ground truth from generator output")
    parser.add_argument("--generator-output", type=Path, required=True,
                        help="Path to generator nightmare output directory")
    parser.add_argument("--output-dir", type=Path, default=Path("ground_truth"),
                        help="Output directory for ground truth files")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Processing generator output from: {args.generator_output}")
    print(f"Writing ground truth to: {args.output_dir}")
    print()

    all_packets = []

    # Process each difficulty level
    for level_dir in sorted(args.generator_output.iterdir()):
        if not level_dir.is_dir() or level_dir.name.startswith("."):
            continue

        print(f"Processing {level_dir.name}...")

        for packet_dir in sorted(level_dir.glob("doc_*")):
            result = process_packet(packet_dir, args.output_dir)
            if result:
                all_packets.append(result)
                total = result.get("summary", {}).get("total_documents", 0)
                cats = result.get("summary", {}).get("by_category", {})
                print(f"  {packet_dir.name}: {total} documents ({cats})")

    generate_summary(all_packets, args.output_dir)

    print(f"\nGenerated ground truth for {len(all_packets)} packets")


if __name__ == "__main__":
    main()
