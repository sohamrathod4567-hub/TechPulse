"""
Sidebar Navigation and Status Component for TechPulse Dashboard.

Renders navigation options, system connection status indicator, and environment
details adhering to the dark, professional, minimalist SaaS aesthetic.
"""

from __future__ import annotations

import streamlit as st

from frontend.api.client import TechPulseClient
from frontend.config import APP_TITLE, get_api_base_url

# Navigation sections
NAVIGATION_PAGES = (
    "Market Overview",
    "Skills Intelligence",
    "Location Intelligence",
    "Job Explorer",
)


def render_sidebar(client: TechPulseClient) -> str:
    """
    Render the dashboard sidebar with navigation and backend status indicator.

    Args:
        client: Active TechPulseClient instance.

    Returns:
        str: Name of the selected navigation page.
    """
    with st.sidebar:
        # Application Branding
        st.markdown(
            """
            <div style="padding: 10px 0 20px 0; border-bottom: 1px solid #2d3139;">
                <div style="font-size: 1.3rem; font-weight: 700; letter-spacing: 0.08em; color: #f1f5f9;">
                    TECHPULSE
                </div>
                <div style="font-size: 0.78rem; font-weight: 400; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; margin-top: 2px;">
                    Job Market Intelligence
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

        # Backend Connection Status Check
        is_healthy = client.check_health()
        api_url = client.base_url

        if is_healthy:
            status_html = f"""
            <div style="padding: 10px 14px; background-color: #111827; border: 1px solid #1f2937; border-left: 3px solid #10b981; border-radius: 4px; margin-bottom: 24px;">
                <div style="font-size: 0.72rem; font-weight: 600; color: #10b981; text-transform: uppercase; letter-spacing: 0.06em;">
                    System Status: Online
                </div>
                <div style="font-size: 0.75rem; color: #9ca3af; margin-top: 3px; word-break: break-all;">
                    Connected to API
                </div>
            </div>
            """
        else:
            status_html = f"""
            <div style="padding: 10px 14px; background-color: #111827; border: 1px solid #374151; border-left: 3px solid #ef4444; border-radius: 4px; margin-bottom: 24px;">
                <div style="font-size: 0.72rem; font-weight: 600; color: #ef4444; text-transform: uppercase; letter-spacing: 0.06em;">
                    System Status: Offline
                </div>
                <div style="font-size: 0.75rem; color: #9ca3af; margin-top: 3px; word-break: break-all;">
                    Backend Unreachable
                </div>
            </div>
            """

        st.markdown(status_html, unsafe_allow_html=True)

        # Navigation Options
        st.markdown(
            """
            <div style="font-size: 0.72rem; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px;">
                Navigation
            </div>
            """,
            unsafe_allow_html=True,
        )

        selected_page = st.radio(
            label="Navigation Sections",
            options=NAVIGATION_PAGES,
            index=0,
            label_visibility="collapsed",
        )

        # Sidebar Footer Details
        st.markdown("<div style='height: 40px;'></div>", unsafe_allow_html=True)
        st.markdown(
            f"""
            <div style="border-top: 1px solid #2d3139; padding-top: 16px; font-size: 0.72rem; color: #64748b;">
                <div>Platform: TechPulse v1.0.0</div>
                <div style="margin-top: 3px;">Architecture: FastAPI / Postgres</div>
                <div style="margin-top: 3px; word-break: break-all;">Host: {api_url}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        return selected_page
