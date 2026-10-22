"""Reusable design system UI components for the CityPulse application.

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
