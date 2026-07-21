# Using UCL Sans in PowerPoint

## Purpose

UCL presentations should use **UCL Sans**, the university's brand font, wherever possible.

The font will display correctly only when:

1. UCL Sans is installed on the computer showing the presentation, or
2. UCL Sans has been embedded inside the PowerPoint file.

> **Important:** Before submitting or sharing a presentation, embed UCL Sans in the `.pptx` file. Otherwise, PowerPoint may substitute another font on the assessor's or presentation-room computer.

---

## Core Requirement

```yaml
ucl_font:
  preferred_font: "UCL Sans"
  use_where_possible: true
  embed_before_sharing: true
  reason: "Prevent font substitution on computers without UCL Sans installed"
```

---

## Recommended Workflow

1. Create the presentation using the official UCL PowerPoint template.
2. Confirm that slide text uses UCL Sans.
3. Finish editing the presentation.
4. Embed the font using the instructions for the relevant operating system.
5. Save the presentation again.
6. Reopen the saved file and check that it displays correctly.
7. Submit or share the final `.pptx`.
8. Optionally export a PDF as a visual backup.

---

# Windows Instructions

## Embed UCL Sans in PowerPoint on Windows

1. Open the presentation in PowerPoint.
2. Select **File** in the top-left corner.
3. Select **Options** at the bottom of the left-hand menu.
4. In the **PowerPoint Options** window, select **Save**.
5. Scroll to:

   **Preserve fidelity when sharing this presentation**

6. Tick:

   **Embed fonts in the file**

7. Choose one of the following options:

   - **Embed all characters**
     - Recommended when another person may edit the file.
     - Preserves the complete font.
     - Produces a larger PowerPoint file.

   - **Embed only the characters used in the presentation**
     - Reduces file size.
     - Suitable when recipients are unlikely to edit the slides.
     - May not support newly typed characters later.

8. For final submission and maximum compatibility, prefer:

   **Embed all characters**

9. Select **OK**.
10. Save the presentation again before sharing or submitting it.

## Windows Menu Path

```text
File
└── Options
    └── Save
        └── Preserve fidelity when sharing this presentation
            ├── Embed fonts in the file
            └── Embed all characters
```

---

# macOS Instructions

## Embed UCL Sans in PowerPoint on a Mac

1. Open the presentation in PowerPoint.
2. In the macOS menu bar, select:

   **PowerPoint → Preferences**

3. In the **Preferences** window, select **Save**.
4. Find the **Font Embedding** section.
5. Tick:

   **Embed fonts in the file**

6. Choose one of the following:

   - **Embed all characters**
     - Recommended when the file may be edited by someone else.
     - Produces a larger file.

   - **Embed only the characters used in the presentation**
     - Reduces file size.
     - Suitable when recipients only need to view the presentation.

7. For final submission and maximum compatibility, prefer:

   **Embed all characters**

8. Select **OK**.
9. Save the presentation again before sharing or submitting it.

## macOS Menu Path

```text
PowerPoint
└── Preferences
    └── Save
        └── Font Embedding
            ├── Embed fonts in the file
            └── Embed all characters
```

---

# Option Selection Guidance

| Option | Advantage | Disadvantage | Recommended use |
|---|---|---|---|
| Embed all characters | Best compatibility and allows later editing | Larger file size | Final editable `.pptx`, assessor copy, collaborative work |
| Embed only used characters | Smaller file size | Editing may cause missing or substituted characters | View-only sharing where file size matters |
| Do not embed fonts | Smallest file | UCL Sans may be replaced on another computer | Not recommended |

---

# Codex Instructions

When creating or modifying the presentation, follow these requirements:

```yaml
powerpoint_font_policy:
  primary_font: "UCL Sans"
  apply_to:
    - slide_titles
    - section_titles
    - body_text
    - labels
    - captions
    - chart_text
    - table_text
  before_delivery:
    - verify_font_usage
    - embed_fonts_in_pptx
    - save_file_after_embedding
    - reopen_and_check_rendering
  embedding_preference:
    option: "embed_all_characters"
    rationale:
      - maximum_compatibility
      - supports_future_editing
      - avoids_font_substitution
  fallback:
    if_embedding_is_not_possible:
      - export_pdf_backup
      - visually_compare_pdf_with_pptx
      - warn_user_that_pptx_may_substitute_fonts
```

---

# Final Presentation Checklist

## Font Use

- [ ] The official UCL PowerPoint template is used.
- [ ] Slide titles use UCL Sans.
- [ ] Body text uses UCL Sans.
- [ ] Figure labels and captions use UCL Sans.
- [ ] Chart titles, axes, legends, and annotations use UCL Sans.
- [ ] Tables use UCL Sans.
- [ ] No accidental fallback fonts are visible.

## Font Embedding

- [ ] **Embed fonts in the file** is enabled.
- [ ] **Embed all characters** is selected.
- [ ] The presentation has been saved after enabling embedding.
- [ ] The saved `.pptx` has been reopened and checked.
- [ ] The file displays correctly on another computer where possible.

## Submission Safety

- [ ] The final `.pptx` opens without warnings.
- [ ] Slide layouts have not changed after reopening.
- [ ] Text has not reflowed or overflowed.
- [ ] Symbols, equations, and special characters display correctly.
- [ ] A PDF backup has been exported where useful.
- [ ] The final file size is acceptable for Moodle upload.

---

# Important Limitation for Automated PowerPoint Generation

A script or Codex workflow may assign the font name `UCL Sans` to text in the PowerPoint file, but this does not guarantee that the actual font data is embedded.

Font embedding may still need to be completed manually in Microsoft PowerPoint using the Windows or macOS instructions above.

Therefore, the final workflow should distinguish between:

```yaml
font_assignment:
  meaning: "Slide text is configured to request UCL Sans"
  can_be_automated: true

font_embedding:
  meaning: "The UCL Sans font data is stored inside the PPTX"
  can_be_automated_reliably: false
  recommended_action: "Complete and verify manually in Microsoft PowerPoint"
```

Do not distribute or package UCL Sans font files separately. Use the institution-approved installation source and PowerPoint's built-in embedding function.
