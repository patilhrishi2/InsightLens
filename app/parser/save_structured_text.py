import os

def save_structured_sections(sections, filename):
    """
    Saves the segmented resume sections into a readable structured text file
    for manual inspection and comparison.
    """
    os.makedirs("app/structured_text_output", exist_ok=True)
    output_path = os.path.join("app/structured_text_output", f"{filename}_structured.txt")

    with open(output_path, "w", encoding="utf-8") as f:
        for section, content in sections.items():
            f.write(f"===== {section.upper()} =====\n")
            f.write(content.strip() + "\n\n")

    return output_path
