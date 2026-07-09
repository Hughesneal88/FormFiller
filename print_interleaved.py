import docx

doc = docx.Document(r"C:\Users\Hughe\Downloads\survey_auto_filler\Data Analysis.docx")

table_counter = 0
for idx, element in enumerate(doc.element.body):
    if element.tag.endswith('p'):
        p = docx.text.paragraph.Paragraph(element, doc)
        if p.text.strip():
            print(f"[P {idx}]: {p.text}")
    elif element.tag.endswith('tbl'):
        print(f"\n--- [TBL {table_counter}] ---")
        t = doc.tables[table_counter]
        for r_idx, row in enumerate(t.rows):
            row_text = [cell.text.strip().replace('\n', ' ') for cell in row.cells]
            # De-duplicate adjacent identical cells
            row_display = []
            for cell_val in row_text:
                if not row_display or row_display[-1] != cell_val:
                    row_display.append(cell_val)
            print(f"  Row {r_idx}: {row_display}")
        table_counter += 1
        print("------------------\n")
