"""Reusable design system UI components for the AERA application.

Provides accessible, contrast-compliant visual elements:
- risk_pill(label): Good, Unhealthy, Severe pill with contrast >= 4.5:1.
- quality_badge(label): Good, Fair, Low telemetry quality indicator.
- card(title, body): Flat surface card with subtle border and elevation.
- big_number(value, caption): Key metric highlight callout.
"""

from __future__ import annotations

import html
from typing import Union


def risk_pill(label: str) -> str:
    """Render an accessible risk tier pill.

    Parameters
    ----------
    label : str
        Risk tier ('Good', 'Unhealthy', or 'Severe').

    Returns
    -------
    str
        HTML string of the rendered pill.
    """
    clean_label = html.escape(str(label).strip())
    cls_key = clean_label.lower()
    if cls_key not in ["good", "unhealthy", "severe"]:
        cls_key = "good"

    return f'<span class="cp-pill cp-pill-{cls_key}">{clean_label}</span>'


def quality_badge(label: str) -> str:
    """Render a data quality badge.

    Parameters
    ----------
    label : str
        Data quality label ('Good', 'Fair', or 'Low').

    Returns
    -------
    str
        HTML string of the rendered badge.
    """
    clean_label = html.escape(str(label).strip())
    cls_key = clean_label.lower()
    if cls_key not in ["good", "fair", "low"]:
        cls_key = "fair"

    return f'<span class="cp-badge cp-badge-{cls_key}">{clean_label} Data Quality</span>'


def card(title: str, body: str) -> str:
    """Render a standard flat surface card.

    Parameters
    ----------
    title : str
        Card headline.
    body : str
        Card body content.

    Returns
    -------
    str
        HTML string of the rendered card.
    """
    clean_title = html.escape(str(title))
    return (
        f'<div class="cp-card">'
        f'<div class="cp-card-title">{clean_title}</div>'
        f'<div class="cp-card-body">{body}</div>'
        f'</div>'
    )


def big_number(value: Union[str, int, float], caption: str) -> str:
    """Render a big number callout card.

    Parameters
    ----------
    value : str | int | float
        Numeric or highlight value.
    caption : str
        Explanatory label below the value.

    Returns
    -------
    str
        HTML string of the callout card.
    """
    clean_val = html.escape(str(value))
    clean_caption = html.escape(str(caption))
    return (
        f'<div class="cp-bignum-card">'
        f'<div class="cp-bignum-val">{clean_val}</div>'
        f'<div class="cp-bignum-caption">{clean_caption}</div>'
        f'</div>'
    )


def demographic_card(ward_info: dict, surge_info: dict) -> str:
    """Render the official Demographic Vulnerability Card for a station's ward.

    Parameters
    ----------
    ward_info : dict
        Ward metadata containing school children, senior citizens, ward code/name.
    surge_info : dict
        Surge alert containing level, badge_color, badge_bg, and catchment.

    Returns
    -------
    str
        HTML string representing the demographic vulnerability card.
    """
    ward_code = html.escape(str(ward_info.get("ward_code", "K/East")))
    ward_name = html.escape(str(ward_info.get("ward_name", "Mumbai Ward")))
    school_children = int(ward_info.get("school_children_at_risk", 42000))
    senior_citizens = int(ward_info.get("senior_citizens", 28500))
    surge_level = html.escape(str(surge_info.get("level", "ELEVATED")))
    badge_bg = surge_info.get("badge_bg", "#FFF4E5")
    badge_color = surge_info.get("badge_color", "#8A4B00")
    catchment = html.escape(str(surge_info.get("catchment", "Municipal General Hospital Catchment")))

    return f"""
    <div class="cp-vuln-card">
      <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #E5E5EA; padding-bottom: 8px;">
        <div>
          <span style="font-size: 13px; font-weight: 700; color: #1D1D1F;">🏥 Ward Health & Vulnerability Exposure</span>
          <span style="font-size: 12px; color: #6E6E73; margin-left: 6px;">(BMC Ward {ward_code} • {ward_name})</span>
        </div>
        <span style="background: {badge_bg}; color: {badge_color}; border: 1px solid {badge_color}40; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 999px;">
          SURGE: {surge_level}
        </span>
      </div>
      <div class="cp-vuln-grid">
        <div class="cp-vuln-item">
          <div style="font-size: 11px; text-transform: uppercase; color: #6E6E73; font-weight: 600;">🏫 School Children at Risk</div>
          <div style="font-size: 19px; font-weight: 700; color: #1D1D1F; margin-top: 2px;">{school_children:,}</div>
          <div style="font-size: 11px; color: #86868B; margin-top: 2px;">Ages &le;14 in active school zones</div>
        </div>
        <div class="cp-vuln-item">
          <div style="font-size: 11px; text-transform: uppercase; color: #6E6E73; font-weight: 600;">🧓 Senior Citizen Population</div>
          <div style="font-size: 19px; font-weight: 700; color: #1D1D1F; margin-top: 2px;">{senior_citizens:,}</div>
          <div style="font-size: 11px; color: #86868B; margin-top: 2px;">Ages &ge;65 vulnerable cohort</div>
        </div>
        <div class="cp-vuln-item">
          <div style="font-size: 11px; text-transform: uppercase; color: #6E6E73; font-weight: 600;">🏥 Respiratory Bed Surge Alert</div>
          <div style="font-size: 14px; font-weight: 700; color: {badge_color}; margin-top: 2px;">{surge_level}</div>
          <div style="font-size: 11px; color: #6E6E73; margin-top: 2px;">{catchment}</div>
        </div>
      </div>
    </div>
    """
