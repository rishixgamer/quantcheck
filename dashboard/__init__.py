"""The standalone read-only QuantCheck forensic dashboard.

This package lives outside ``src/quantcheck`` on purpose. The core package must
stay usable without Streamlit installed, so nothing importable as
``quantcheck.*`` may import this module, and an ordinary ``import quantcheck``
never reaches it.

Launch it with::

    uv run --group dashboard streamlit run dashboard/app.py -- --artifacts <root>
"""
