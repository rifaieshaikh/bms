import zipfile, xml.etree.ElementTree as ET, re, json
from pathlib import Path
from collections import Counter, defaultdict

path = Path(r"c:\Users\admin\Downloads\VayBooks_Sales_QA_Test_Execution_Tracker.xlsx")
out = Path(r"c:\Users\admin\Documents\GitHub\zahcci\bms\.tmp_sales_qa_cases.json")
ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

with zipfile.ZipFile(path) as z:
    ss = []
    if "xl/sharedStrings.xml" in z.namelist():
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in root.findall("m:si", ns):
            texts = [t.text or "" for t in si.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")]
            ss.append("".join(texts))
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    sheets = []
    for sh in wb.findall("m:sheets/m:sheet", ns):
        sheets.append((sh.attrib.get("name"), sh.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    rid_to_target = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}

    def col_row(ref):
        m = re.match(r"([A-Z]+)(\d+)", ref)
        col, row = m.group(1), int(m.group(2))
        n = 0
        for ch in col:
            n = n * 26 + ord(ch) - 64
        return n - 1, row

    def sheet_cells(name):
        rid = [r for n, r in sheets if n == name][0]
        target = "xl/" + rid_to_target[rid].lstrip("/")
        if target.startswith("xl/xl/"):
            target = target[3:]
        root = ET.fromstring(z.read(target))
        cells = {}
        max_r = max_c = 0
        for c in root.findall(".//m:c", ns):
            ref = c.attrib.get("r")
            t = c.attrib.get("t")
            v = c.find("m:v", ns)
            if not ref or v is None or v.text is None:
                continue
            ci, ri = col_row(ref)
            val = ss[int(v.text)] if t == "s" else v.text
            cells[(ri, ci)] = val
            max_r = max(max_r, ri)
            max_c = max(max_c, ci)
        return cells, max_r, max_c

    cells, max_r, max_c = sheet_cells("Test Cases")
    headers = [cells.get((3, ci), "") for ci in range(max_c + 1)]
    cases = []
    for ri in range(4, max_r + 1):
        row = {headers[ci] or f"c{ci}": cells.get((ri, ci), "") for ci in range(max_c + 1)}
        if not row.get("Test Case ID"):
            continue
        cases.append(row)

print("TOTAL", len(cases))
print("HEADERS", headers)
print("MODULES", dict(Counter(c.get("Module") for c in cases)))
print("PRIORITY", dict(Counter(c.get("Priority") for c in cases)))
print("AUTO_CANDIDATE", dict(Counter(c.get("Automation Candidate") for c in cases)))
print("AUTO_STATUS", dict(Counter(c.get("Automation Status") for c in cases)))
print("---CASE_LIST---")
for c in cases:
    line = " | ".join([
        c.get("Test Case ID", ""),
        c.get("Module", ""),
        c.get("Area", ""),
        c.get("Priority", ""),
        c.get("Playwright Test ID", ""),
        c.get("Scenario / Test Case", ""),
    ])
    print(line)

# Sales returns detail
print("---SALES_RETURNS_DETAIL---")
for c in cases:
    if c.get("Module") == "Sales Returns":
        print("ID:", c.get("Test Case ID"))
        print("Scenario:", c.get("Scenario / Test Case"))
        print("Steps:", c.get("Manual Steps"))
        print("Expected:", c.get("Expected Result"))
        print("Acct:", c.get("Expected Accounting Impact"))
        print("Inv:", c.get("Expected Inventory Impact"))
        print("PW:", c.get("Playwright Test ID"), "Status:", c.get("Automation Status"), "Spec:", c.get("Spec Path"))
        print("---")

out.write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")
print("WROTE", out)
