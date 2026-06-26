"""Utility functions extracted from the Streamlit dashboard for testability."""


def status_badge_html(status: str) -> str:
    """Render a color-coded status badge span.

    Maps status strings to muted-pastel badges matching the minimalist
    colour palette: green (ready), red (error), amber (queued), gray (no-pdf),
    blue (downloading).

    Args:
        status: Filing status string (e.g. 'READY', 'ERROR_DOWNLOAD', 'QUEUED').

    Returns:
        HTML span with appropriate badge CSS class and label.
    """
    if status.startswith("ERROR_"):
        return '<span class="badge badge-error">Error</span>'
    css = status.lower().replace("_", "-")
    labels = {
        "ready": "Ready",
        "queued": "Queued",
        "no-pdf": "No PDF",
        "downloading": "Downloading",
    }
    label = labels.get(css, status)
    known = {"ready", "error", "queued", "no-pdf", "downloading"}
    css_class = css if css in known else "error"
    return f'<span class="badge badge-{css_class}">{label}</span>'
