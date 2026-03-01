"""Thin entry-point — delegates to dashboard/app.py."""
from dashboard.app import app  # noqa: F401

if __name__ == "__main__":
    import os
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8050)))
