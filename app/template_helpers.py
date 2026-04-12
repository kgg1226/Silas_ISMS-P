"""
app/template_helpers.py — Jinja2 global helpers for ISMS-P templates.

Call `setup_i18n(app, templates)` once after creating the Jinja2Templates
instance to inject a `t()` translation function into every template.

Template usage:
    {{ t("nav.dashboard") }}          {# uses the request's locale #}
    {{ t("btn.search", locale="en") }} {# explicit override #}
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates

from app.i18n import get_text, DEFAULT_LOCALE


def setup_i18n(app: FastAPI, templates: Jinja2Templates) -> None:  # noqa: ARG001
    """Register a ``t()`` global in the Jinja2 environment.

    The function signature exposed to templates is::

        t(key: str, locale: str = DEFAULT_LOCALE) -> str

    *locale* defaults to ``DEFAULT_LOCALE`` ("ko").  Templates can pass an
    explicit locale, or the route handler can inject ``locale`` into the
    template context so that ``t`` picks it up automatically via a closure.

    Because Jinja2 globals are set on the *Environment* (not per-request),
    the locale is resolved in this order:

    1. The ``locale`` keyword argument passed directly to ``t()`` in the
       template — highest priority.
    2. The ``DEFAULT_LOCALE`` constant — safe fallback.

    For per-request locale support (future), routes should pass ``locale``
    in the template context and templates should call ``t(key, locale)``.
    """

    def t(key: str, locale: str = DEFAULT_LOCALE) -> str:
        """Translate *key* into *locale*.  Falls back to Korean then to *key*."""
        return get_text(key, locale=locale)

    # Expose as a Jinja2 global so every template can call it without
    # explicit context injection.
    templates.env.globals["t"] = t
