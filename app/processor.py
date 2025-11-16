"""PDF processing and OpenAI integration."""

import os
import io
import json
import re
from typing import Dict, Any, Tuple, Optional
from datetime import date
import pdfplumber
import pytesseract
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def extract_text_from_pdf(pdf_content: bytes) -> str:
    """Extract text from PDF."""
    text = ""
    try:
        with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        if not text.strip():
            from pdf2image import convert_from_bytes
            images = convert_from_bytes(pdf_content)
            text = "\n".join(pytesseract.image_to_string(img) for img in images)
    except Exception as e:
        raise Exception(f"Error extracting text: {str(e)}")
    return text.strip()


def parse_date(date_str: str) -> date | None:
    """Parse date string."""
    if not date_str:
        return None
    from datetime import datetime
    for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y", "%m-%d-%Y"]:
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except:
            continue
    return None


def extract_structured_fields(text: str) -> Tuple[Dict[str, Any], Dict[str, Any], bool, Optional[str]]:
    """Extract structured fields using OpenAI."""
    if not text:
        return {}, {}, False, "Empty document"

    prompt = f"""Determine if this is a logistics/shipping document. If not, return {{"is_valid_logistics_document": false, "validation_message": "Not a valid logistics document"}}.

If valid, extract:
- tracking_number, shipper_name, shipper_address, receiver_name, receiver_address
- shipment_date (YYYY-MM-DD), delivery_date (YYYY-MM-DD)
- weight, dimensions, carrier, shipping_method, status, special_instructions

Return JSON: {{"is_valid_logistics_document": true/false, "validation_message": "...", ...fields}}

Document text:
{text[:4000]}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a logistics document parser. Return valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=1000
        )

        response_text = response.choices[0].message.content.strip()
        if response_text.startswith("```"):
            response_text = re.split(r"```(?:json)?", response_text)[1] if "```" in response_text else response_text
        response_text = response_text.strip()

        parsed_data = json.loads(response_text)
        is_valid = parsed_data.get("is_valid_logistics_document", False)

        if not is_valid:
            return {}, {}, False, parsed_data.get("validation_message", "Not a valid logistics document")

        structured_fields = {
            "tracking_number": parsed_data.get("tracking_number"),
            "shipper_name": parsed_data.get("shipper_name"),
            "shipper_address": parsed_data.get("shipper_address"),
            "receiver_name": parsed_data.get("receiver_name"),
            "receiver_address": parsed_data.get("receiver_address"),
            "shipment_date": parse_date(parsed_data.get("shipment_date") or ""),
            "delivery_date": parse_date(parsed_data.get("delivery_date") or ""),
            "weight": parsed_data.get("weight"),
            "dimensions": parsed_data.get("dimensions"),
            "carrier": parsed_data.get("carrier"),
            "shipping_method": parsed_data.get("shipping_method"),
            "status": parsed_data.get("status"),
            "special_instructions": parsed_data.get("special_instructions"),
        }

        return structured_fields, {"raw": parsed_data}, True, None
    except Exception as e:
        return {}, {}, False, f"Error: {str(e)}"


def process_document(pdf_content: bytes, filename: str) -> Tuple[str, Dict[str, Any], Dict[str, Any], bool, Optional[str]]:
    """Process PDF document."""
    extracted_text = extract_text_from_pdf(pdf_content)
    structured_fields, additional_data, is_valid, validation_message = extract_structured_fields(extracted_text)
    return extracted_text, structured_fields, additional_data, is_valid, validation_message
