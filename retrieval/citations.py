"""Human-readable source labels for retrieved chunks, used in search output and answers."""


def page_label(metadata: dict) -> str | None:
    start, end = metadata.get("page_number"), metadata.get("page_end")
    if start is None:
        return None
    if end is None or end == start:
        return f"page {start}"
    return f"pages {start}-{end}"


def source_label(metadata: dict) -> str:
    """e.g. 'handbook.pdf, pages 4-6 (Leave Policy > Sick Leave)'"""
    parts = [metadata.get("file_name", "unknown file")]
    pages = page_label(metadata)
    if pages:
        parts.append(pages)
    label = ", ".join(parts)
    if metadata.get("section"):
        label += f" ({metadata['section']})"
    return label
