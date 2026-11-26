"""
TechPulse - Job Market Intelligence Platform.

Streamlit frontend foundation communicating with the FastAPI backend via HTTP.
Features:
- Minimalist dark SaaS theme (black, charcoal, slate).
- Zero emojis.
- Real-time backend connectivity detection and error handling.
- Multi-section sidebar navigation.
- Foundation views for Market Overview, Skills, Locations, and Jobs.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from frontend.api.client import (
    APIConnectionError,
    APIResponseError,
    TechPulseClient,
    get_api_client,
)
from frontend.components.sidebar import render_sidebar
from frontend.config import APP_TITLE, get_api_base_url


def configure_page() -> None:
    """Set global Streamlit page configuration and inject custom dark CSS."""
    st.set_page_config(
        page_title=APP_TITLE,
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Clean dark theme styling overrides (minimalist, subtle borders, no emojis)
    st.markdown(
        """
        <style>
            /* Global background and typography */
            .stApp {
                background-color: #0b0f17;
                color: #e2e8f0;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            }
            
            /* Sidebar styling */
            section[data-testid="stSidebar"] {
                background-color: #111827;
                border-right: 1px solid #1f2937;
            }

            /* Headers */
            h1, h2, h3, h4 {
                color: #f8fafc !important;
                font-weight: 600 !important;
                letter-spacing: -0.02em !important;
            }

            /* Metric cards */
            div[data-testid="stMetric"] {
                background-color: #111827;
                border: 1px solid #1f2937;
                border-radius: 6px;
                padding: 14px 18px;
            }
            div[data-testid="stMetricLabel"] {
                color: #94a3b8 !important;
                font-size: 0.8rem !important;
                text-transform: uppercase;
                letter-spacing: 0.05em;
            }
            div[data-testid="stMetricValue"] {
                color: #f1f5f9 !important;
                font-size: 1.8rem !important;
                font-weight: 700 !important;
            }

            /* Buttons and inputs */
            .stButton > button {
                background-color: #1f2937;
                color: #f1f5f9;
                border: 1px solid #374151;
                border-radius: 4px;
                font-weight: 500;
                transition: all 0.15s ease-in-out;
            }
            .stButton > button:hover {
                background-color: #374151;
                border-color: #4b5563;
                color: #ffffff;
            }

            /* Radio navigation in sidebar */
            div[data-testid="stRadio"] > div {
                gap: 6px;
            }
            div[data-testid="stRadio"] label {
                padding: 6px 12px;
                border-radius: 4px;
                transition: background-color 0.1s ease;
            }
            div[data-testid="stRadio"] label:hover {
                background-color: #1f2937;
            }

            /* Subtle horizontal rule */
            hr {
                border-color: #1f2937;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_disconnected_state(api_url: str) -> None:
    """Render an informative error screen when the backend API is unreachable."""
    st.markdown(
        f"""
        <div style="background-color: #111827; border: 1px solid #374151; border-left: 4px solid #ef4444; border-radius: 6px; padding: 24px 28px; margin-top: 20px;">
            <div style="font-size: 1.15rem; font-weight: 700; color: #f8fafc; letter-spacing: -0.01em;">
                Backend Service Unavailable
            </div>
            <div style="color: #94a3b8; font-size: 0.92rem; margin-top: 8px; line-height: 1.5;">
                The TechPulse dashboard cannot connect to the FastAPI backend at 
                <code style="background-color: #1f2937; color: #e2e8f0; padding: 2px 6px; border-radius: 3px;">{api_url}</code>.
            </div>
            <div style="margin-top: 18px; padding-top: 16px; border-top: 1px solid #1f2937; font-size: 0.85rem; color: #cbd5e1;">
                <div style="font-weight: 600; color: #e2e8f0; margin-bottom: 6px;">How to resolve:</div>
                <div>1. Ensure the backend server process is started:</div>
                <div style="background-color: #0b0f17; border: 1px solid #1f2937; border-radius: 4px; padding: 8px 12px; margin: 6px 0 10px 0; font-family: monospace; color: #38bdf8;">
                    python -m uvicorn src.techpulse.api.main:app --reload
                </div>
                <div>2. If running on a different port or host, set the environment variable:</div>
                <div style="background-color: #0b0f17; border: 1px solid #1f2937; border-radius: 4px; padding: 8px 12px; margin: 6px 0 0 0; font-family: monospace; color: #38bdf8;">
                    $env:TECHPULSE_API_URL="http://127.0.0.1:8000"
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_market_overview(client: TechPulseClient) -> None:
    """Render Market Overview dashboard view."""
    st.subheader("Market Overview")
    st.caption("Macro aggregate labor market distribution and posting volume.")

    try:
        overview = client.get_analytics_overview()
        remote = client.get_remote_distribution()

        # KPI Metric Cards
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Total Jobs", f"{overview.get('total_jobs', 0):,}")
        with col2:
            st.metric("Unique Companies", f"{overview.get('unique_companies', 0):,}")
        with col3:
            st.metric("Unique Locations", f"{overview.get('unique_locations', 0):,}")
        with col4:
            st.metric(
                "Remote Positions",
                f"{remote.get('remote_jobs', 0):,}",
                help=f"{remote.get('remote_percentage', 0.0)}% of total listings",
            )
        with col5:
            st.metric(
                "On-Site / Hybrid",
                f"{remote.get('non_remote_jobs', 0):,}",
                help=f"{remote.get('non_remote_percentage', 0.0)}% of total listings",
            )

        st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

        # Overview Summary Box
        st.markdown(
            f"""
            <div style="background-color: #111827; border: 1px solid #1f2937; border-radius: 6px; padding: 20px; font-size: 0.88rem; color: #94a3b8;">
                <div style="color: #f1f5f9; font-weight: 600; margin-bottom: 6px;">Dataset Status</div>
                Active job market pipeline synchronized with PostgreSQL. Total indexed listings: 
                <strong style="color: #f8fafc;">{overview.get('total_jobs', 0)}</strong> across 
                <strong style="color: #f8fafc;">{overview.get('unique_companies', 0)}</strong> hiring organizations.
            </div>
            """,
            unsafe_allow_html=True,
        )

    except (APIConnectionError, APIResponseError) as exc:
        st.error(f"Error loading market overview: {exc}")


def render_skills_intelligence(client: TechPulseClient) -> None:
    """Render Skills Intelligence dashboard view."""
    st.subheader("Skills Intelligence")
    st.caption("Canonical technical skill demand ranking and category distribution.")

    try:
        skills_data = client.get_top_skills(limit=5)
        categories_data = client.get_skill_categories(limit=5)

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Identified Skills", f"{skills_data.get('total_skills', 0):,}")
        with col2:
            st.metric("Skill Categories", f"{categories_data.get('total_categories', 0):,}")

        st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
        st.markdown(
            """
            <div style="background-color: #111827; border: 1px solid #1f2937; border-radius: 6px; padding: 20px; font-size: 0.88rem; color: #94a3b8;">
                <div style="color: #f1f5f9; font-weight: 600; margin-bottom: 6px;">Technical Taxonomy</div>
                Canonical taxonomy covers 66 technical skills mapped across 9 software engineering domains.
                Full analytics visualizations will be populated in subsequent dashboard milestones.
            </div>
            """,
            unsafe_allow_html=True,
        )

    except (APIConnectionError, APIResponseError) as exc:
        st.error(f"Error loading skills intelligence: {exc}")


def render_location_intelligence(client: TechPulseClient) -> None:
    """Render Location Intelligence dashboard view."""
    st.subheader("Location Intelligence")
    st.caption("Geographic labor concentration and location-specific skill demand.")

    try:
        locations_data = client.get_locations(limit=5)
        st.metric("Active Locations", f"{locations_data.get('total_locations', 0):,}")

        st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
        st.markdown(
            """
            <div style="background-color: #111827; border: 1px solid #1f2937; border-radius: 6px; padding: 20px; font-size: 0.88rem; color: #94a3b8;">
                <div style="color: #f1f5f9; font-weight: 600; margin-bottom: 6px;">Geographic Analytics</div>
                Normalized geographic posting counts and cross-location skill demand analysis.
                Interactive location breakdown will be expanded in the next phase.
            </div>
            """,
            unsafe_allow_html=True,
        )

    except (APIConnectionError, APIResponseError) as exc:
        st.error(f"Error loading location intelligence: {exc}")


def render_job_explorer(client: TechPulseClient) -> None:
    """Render Job Explorer dashboard view."""
    st.subheader("Job Explorer")
    st.caption("Search, filter, and inspect verified technical job postings.")

    try:
        jobs_data = client.get_jobs(skip=0, limit=5)
        st.metric("Total Indexed Jobs", f"{jobs_data.get('total', 0):,}")

        st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
        st.markdown(
            """
            <div style="background-color: #111827; border: 1px solid #1f2937; border-radius: 6px; padding: 20px; font-size: 0.88rem; color: #94a3b8;">
                <div style="color: #f1f5f9; font-weight: 600; margin-bottom: 6px;">Job Repository</div>
                Direct access to raw and structured job listings with skill tags and company attributes.
                Search and filtering interface will be added in upcoming foundation updates.
            </div>
            """,
            unsafe_allow_html=True,
        )

    except (APIConnectionError, APIResponseError) as exc:
        st.error(f"Error loading job explorer: {exc}")


def main() -> None:
    """Main application lifecycle."""
    configure_page()

    client = get_api_client()
    selected_page = render_sidebar(client)

    # Check backend availability
    is_healthy = client.check_health()
    if not is_healthy:
        render_disconnected_state(client.base_url)
        return

    # Route navigation to respective view
    if selected_page == "Market Overview":
        render_market_overview(client)
    elif selected_page == "Skills Intelligence":
        render_skills_intelligence(client)
    elif selected_page == "Location Intelligence":
        render_location_intelligence(client)
    elif selected_page == "Job Explorer":
        render_job_explorer(client)


if __name__ == "__main__":
    main()
