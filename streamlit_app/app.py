"""Streamlit UI for document upload."""

import streamlit as st
import requests
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8080/api/v1")

st.set_page_config(page_title="Logistics Document Processor", layout="wide", page_icon="📦")
st.title("📦 Logistics Document Automation")

# Check API and database connection
if "api_status" not in st.session_state:
    st.session_state.api_status = None
if "db_status" not in st.session_state:
    st.session_state.db_status = None

# Check API health on load
try:
    health_response = requests.get(f"{API_BASE_URL}/health", timeout=5)
    if health_response.status_code == 200:
        health_data = health_response.json()
        st.session_state.api_status = "connected"
        st.session_state.db_status = health_data.get("database", "unknown")
    else:
        st.session_state.api_status = "error"
except:
    st.session_state.api_status = "disconnected"

# Display status
col1, col2 = st.columns(2)
with col1:
    if st.session_state.api_status == "connected":
        st.success("✅ API Connected")
    else:
        st.error("❌ API Disconnected")
with col2:
    if st.session_state.db_status == "connected":
        st.success("✅ Database Connected")
    else:
        st.warning("⚠️ Database Disconnected")

if "extracted_data" not in st.session_state:
    st.session_state.extracted_data = None
if "document_hash" not in st.session_state:
    st.session_state.document_hash = None

uploaded_file = st.file_uploader("Upload PDF", type=["pdf"])

# Extract
if uploaded_file and st.session_state.extracted_data is None:
    if st.button("Extract Document"):
        with st.spinner("Processing..."):
            try:
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                response = requests.post(f"{API_BASE_URL}/extract", files=files, timeout=90)

                if response.status_code == 200:
                    st.session_state.extracted_data = response.json()
                    st.session_state.document_hash = st.session_state.extracted_data.get("document_hash")
                    st.experimental_rerun()
                else:
                    try:
                        st.error(response.json().get("detail", "Error"))
                    except:
                        st.error(f"Error: {response.text or 'Unknown error'}")
            except Exception as e:
                st.error(f"Error: {str(e)}")

# Review and save
if st.session_state.extracted_data:
    result = st.session_state.extracted_data

    if not result.get("is_valid"):
        st.error(result.get("validation_message", "Not a valid logistics document"))
        if st.button("Try Again"):
            st.session_state.extracted_data = None
            st.experimental_rerun()
    else:
        fields = result.get("structured_fields", {})

        with st.form("review_form"):
            st.subheader("Review Extracted Fields")

            col1, col2 = st.columns(2)

            with col1:
                reviewed_fields = {
                    "shipper_name": st.text_input("Shipper Name", value=fields.get("shipper_name") or ""),
                    "shipper_address": st.text_area("Shipper Address", value=fields.get("shipper_address") or ""),
                    "receiver_name": st.text_input("Receiver Name", value=fields.get("receiver_name") or ""),
                    "receiver_address": st.text_area("Receiver Address", value=fields.get("receiver_address") or ""),
                }

            with col2:
                reviewed_fields.update({
                    "tracking_number": st.text_input("Tracking Number", value=fields.get("tracking_number") or ""),
                    "carrier": st.text_input("Carrier", value=fields.get("carrier") or ""),
                    "weight": st.text_input("Weight", value=fields.get("weight") or ""),
                    "dimensions": st.text_input("Dimensions", value=fields.get("dimensions") or ""),
                    "status": st.text_input("Status", value=fields.get("status") or ""),
                    "shipment_date": st.text_input("Shipment Date", value=str(fields.get("shipment_date")) if fields.get("shipment_date") else ""),
                    "delivery_date": st.text_input("Delivery Date", value=str(fields.get("delivery_date")) if fields.get("delivery_date") else ""),
                })

            reviewed_fields["special_instructions"] = st.text_area("Special Instructions", value=fields.get("special_instructions") or "")

            col1, col2 = st.columns(2)
            with col1:
                save_btn = st.form_submit_button("Save")
            with col2:
                cancel_btn = st.form_submit_button("Cancel")

            if save_btn:
                with st.spinner("Saving..."):
                    try:
                        # Clean empty strings
                        clean_fields = {k: (None if v == "" or (isinstance(v, str) and not v.strip()) else v)
                                      for k, v in reviewed_fields.items()}

                        save_request = {
                            "document_hash": st.session_state.document_hash,
                            "filename": uploaded_file.name,
                            "structured_fields": clean_fields
                        }

                        response = requests.post(f"{API_BASE_URL}/save", json=save_request, timeout=30)

                        if response.status_code == 200:
                            st.success(f"Saved! Document ID: {response.json().get('document_id')}")
                            st.session_state.extracted_data = None
                            st.session_state.document_hash = None
                            if st.button("Upload Another"):
                                st.experimental_rerun()
                        else:
                            try:
                                st.error(response.json().get("detail", "Error saving"))
                            except:
                                st.error(f"Error: {response.text or 'Unknown error'}")
                    except Exception as e:
                        st.error(f"Error: {str(e)}")

            if cancel_btn:
                st.session_state.extracted_data = None
                st.session_state.document_hash = None
                st.experimental_rerun()
