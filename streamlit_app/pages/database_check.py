"""Streamlit page for viewing database content."""

import streamlit as st
import requests
import os
from dotenv import load_dotenv

load_dotenv()
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8080/api/v1")

st.set_page_config(page_title="Database View", layout="wide")
st.title("Database Content")

# Get documents
if st.button("Refresh"):
    st.experimental_rerun()

try:
    response = requests.get(f"{API_BASE_URL}/documents", timeout=10)

    if response.status_code == 200:
        data = response.json()
        total = data.get("total", 0)
        documents = data.get("documents", [])

        st.info(f"Total documents: {total}")

        if documents:
            for doc in documents:
                with st.expander(f"ID: {doc['id']} - {doc.get('filename', 'N/A')}"):
                    col1, col2 = st.columns(2)

                    with col1:
                        st.write(f"**Tracking Number:** {doc.get('tracking_number') or 'N/A'}")
                        st.write(f"**Shipper:** {doc.get('shipper_name') or 'N/A'}")
                        st.write(f"**Receiver:** {doc.get('receiver_name') or 'N/A'}")
                        st.write(f"**Carrier:** {doc.get('carrier') or 'N/A'}")

                    with col2:
                        st.write(f"**Status:** {doc.get('status') or 'N/A'}")
                        st.write(f"**Shipment Date:** {doc.get('shipment_date') or 'N/A'}")
                        st.write(f"**Created:** {doc.get('created_at', 'N/A')}")
                        if doc.get('storage_url'):
                            st.write(f"**Storage:** {doc['storage_url']}")

                    # Display more details
                    if doc.get('shipper_address'):
                        st.write(f"**Shipper Address:** {doc['shipper_address']}")
                    if doc.get('receiver_address'):
                        st.write(f"**Receiver Address:** {doc['receiver_address']}")
                    if doc.get('weight'):
                        st.write(f"**Weight:** {doc['weight']}")
                    if doc.get('dimensions'):
                        st.write(f"**Dimensions:** {doc['dimensions']}")

                    # View full details button
                    if f"show_details_{doc['id']}" not in st.session_state:
                        st.session_state[f"show_details_{doc['id']}"] = False

                    if st.button(f"View Full Details", key=f"view_{doc['id']}"):
                        st.session_state[f"show_details_{doc['id']}"] = not st.session_state[f"show_details_{doc['id']}"]

                    if st.session_state[f"show_details_{doc['id']}"]:
                        try:
                            detail_response = requests.get(f"{API_BASE_URL}/documents/{doc['id']}", timeout=10)
                            if detail_response.status_code == 200:
                                detail = detail_response.json()
                                st.markdown("---")
                                st.subheader(f"Full Details - Document {doc['id']}")
                                st.json(detail)
                            else:
                                st.error("Could not fetch details")
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
        else:
            st.info("No documents in database")

    else:
        st.error(f"Error: {response.text or 'Unknown error'}")

except Exception as e:
    st.error(f"Error: {str(e)}")
