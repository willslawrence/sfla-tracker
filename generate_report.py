#!/usr/bin/env python3
"""
SFLA Monthly Report Generator
Clean, borderless THC-styled PDF.
"""

import json, sys, os
from datetime import datetime, timedelta
from fpdf import FPDF
import urllib.request, urllib.parse

CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')
LOGO_PATH = os.path.join(os.path.dirname(__file__), 'thc_logo.png')
config = json.load(open(CONFIG_PATH))
BASE_ID = config['airtable']['baseId']
API_KEY = config['airtable']['apiKey']

DARK = (40, 40, 40)
MID = (120, 120, 120)
LIGHT = (200, 200, 200)
WHITE = (255, 255, 255)
ROW_ALT = (248, 248, 248)

STATUS_COLORS = {
    'Suitable': (76, 175, 80),
    'Unsuitable': (107, 114, 128),
    'New SFLA': (244, 67, 54),
}

def api_get(table, params=''):
    url = f'https://api.airtable.com/v0/{BASE_ID}/{urllib.parse.quote(table)}?pageSize=100{params}'
    all_records = []
    while url:
        req = urllib.request.Request(url, headers={'Authorization': f'Bearer {API_KEY}'})
        resp = json.loads(urllib.request.urlopen(req).read())
        all_records.extend(resp.get('records', []))
        offset = resp.get('offset')
        url = f'https://api.airtable.com/v0/{BASE_ID}/{urllib.parse.quote(table)}?pageSize=100&offset={offset}' if offset else None
    return all_records

def get_month_range(year, month):
    start = datetime(year, month, 1)
    end = datetime(year + (1 if month == 12 else 0), (month % 12) + 1, 1)
    return start, end


class SFLAReport(FPDF):
    def __init__(self, month_str):
        super().__init__()
        self.month_str = month_str
        self.set_auto_page_break(auto=True, margin=15)

    def header(self):
        if os.path.exists(LOGO_PATH):
            self.image(LOGO_PATH, x=165, y=6, w=30)
        self.set_xy(10, 8)
        self.set_font('Helvetica', 'B', 16)
        self.set_text_color(*DARK)
        self.cell(0, 7, 'Riyadh UAM SFLA Report', new_x="LMARGIN", new_y="NEXT")
        self.set_font('Helvetica', '', 10)
        self.set_text_color(*MID)
        self.cell(0, 5, self.month_str, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*LIGHT)
        self.set_line_width(0.3)
        self.line(10, self.get_y() + 2, 195, self.get_y() + 2)
        self.ln(6)

    def footer(self):
        self.set_y(-12)
        self.set_font('Helvetica', 'I', 7)
        self.set_text_color(*MID)
        self.cell(95, 8, f'Generated {datetime.now().strftime("%Y-%m-%d %H:%M")} | THC SFLA Tracker')
        self.cell(95, 8, f'Page {self.page_no()}', align='R')

    def section_title(self, title):
        self.set_font('Helvetica', 'B', 11)
        self.set_text_color(*DARK)
        self.cell(0, 7, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def status_dot(self, status):
        r, g, b = STATUS_COLORS.get(status, MID)
        self.set_fill_color(r, g, b)
        self.ellipse(self.get_x() + 1, self.get_y() + 1.5, 3, 3, style='F')
        self.set_x(self.get_x() + 6)


def generate_report(year=None, month=None, output=None):
    now = datetime.now()
    if year is None:
        first = now.replace(day=1)
        prev = first - timedelta(days=1)
        year, month = prev.year, prev.month

    start, end = get_month_range(year, month)
    month_str = start.strftime('%B %Y')

    if output is None:
        output = os.path.expanduser(f'~/Desktop/Willy/SFLA_Report_{start.strftime("%Y-%m")}.pdf')

    print(f'Generating SFLA report for {month_str}...')

    # Fetch sites
    sites = api_get('Sites')
    site_data = []
    total_checks = 0
    for r in sites:
        f = r.get('fields', {})
        total_checks += f.get('CheckCount', 0)
        site_data.append({
            'name': f.get('SFLA Name', f.get('Name', '')),
            'status': f.get('Status', 'Unknown'),
            'last_checked': f.get('LastChecked', ''),
        })
    site_data.sort(key=lambda x: x['name'])

    # Fetch change log
    formula = f"AND(IS_AFTER(Timestamp, '{start.strftime('%Y-%m-%dT00:00:00')}'), IS_BEFORE(Timestamp, '{end.strftime('%Y-%m-%dT00:00:00')}'))"
    changes = api_get('Change Log', f'&filterByFormula={urllib.parse.quote(formula)}&sort%5B0%5D%5Bfield%5D=Timestamp&sort%5B0%5D%5Bdirection%5D=desc')
    change_data = []
    for r in changes:
        f = r.get('fields', {})
        change_data.append({
            'name': f.get('Name', ''),
            'timestamp': f.get('Timestamp', ''),
            'prev': f.get('PreviousStatus', ''),
            'new': f.get('NewStatus', ''),
            'notes': f.get('Notes', ''),
        })

    counts = {}
    for s in site_data:
        counts[s['status']] = counts.get(s['status'], 0) + 1
    total = len(site_data)

    # Build PDF
    pdf = SFLAReport(month_str)
    pdf.add_page()

    # === SUMMARY ===
    pdf.section_title('Summary')
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(*DARK)
    pdf.cell(0, 6, f'Total SFLA Shapes: {total}', new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f'Total Status Changes: {len(change_data)}', new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f'Total Checks Completed: {total_checks}', new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    for status in ['Suitable', 'Unsuitable', 'New SFLA']:
        c = counts.get(status, 0)
        if c == 0:
            continue
        pct = round(c / total * 100, 1) if total else 0
        pdf.status_dot(status)
        pdf.set_font('Helvetica', '', 10)
        pdf.set_text_color(*DARK)
        pdf.cell(0, 6, f'{status}: {c} ({pct}%)', new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # === CHANGE LOG ===
    pdf.section_title(f'Change Log - {month_str}')

    if not change_data:
        pdf.set_font('Helvetica', 'I', 9)
        pdf.set_text_color(*MID)
        pdf.cell(0, 6, 'No status changes this month.', new_x="LMARGIN", new_y="NEXT")
    else:
        cl_w = [30, 18, 25, 25, 92]
        # Header row — subtle
        pdf.set_font('Helvetica', 'B', 7)
        pdf.set_text_color(*MID)
        for i, h in enumerate(['Date', 'SFLA', 'From', 'To', 'Notes']):
            pdf.cell(cl_w[i], 5, h, align='C' if i < 4 else 'L')
        pdf.ln()
        pdf.set_draw_color(*LIGHT)
        pdf.set_line_width(0.2)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())

        pdf.set_font('Helvetica', '', 7)
        for i, c in enumerate(change_data):
            if i % 2 == 0:
                pdf.set_fill_color(*ROW_ALT)
                fill = True
            else:
                fill = False

            ts = c['timestamp'][:16].replace('T', ' ') if c['timestamp'] else ''
            pdf.set_text_color(*DARK)
            pdf.cell(cl_w[0], 5, ts, fill=fill)
            pdf.cell(cl_w[1], 5, c['name'], fill=fill, align='C')
            for val, w in [(c['prev'], cl_w[2]), (c['new'], cl_w[3])]:
                r, g, b = STATUS_COLORS.get(val, MID)
                pdf.set_text_color(r, g, b)
                pdf.set_font('Helvetica', 'B', 7)
                pdf.cell(w, 5, val, fill=fill, align='C')
            pdf.set_font('Helvetica', '', 7)
            pdf.set_text_color(*DARK)
            notes = (c.get('notes', '') or '')[:65]
            pdf.cell(cl_w[4], 5, notes, fill=fill)
            pdf.ln()
    pdf.ln(4)

    # === SFLA STATUS ===
    if pdf.get_y() > 210:
        pdf.add_page()

    pdf.section_title('Current SFLA Status')

    col_sets = 3
    gap = 5
    usable = 190 - (gap * (col_sets - 1))
    group_w = usable / col_sets
    name_w = group_w * 0.28
    stat_w = group_w * 0.35
    date_w = group_w * 0.37

    def draw_col_headers():
        pdf.set_font('Helvetica', 'B', 6)
        pdf.set_text_color(*MID)
        for c in range(col_sets):
            pdf.cell(name_w, 4, 'SFLA', align='C')
            pdf.cell(stat_w, 4, 'Status', align='C')
            pdf.cell(date_w, 4, 'Last Check', align='C')
            if c < col_sets - 1:
                pdf.cell(gap, 4, '')
        pdf.ln()
        pdf.set_draw_color(*LIGHT)
        pdf.set_line_width(0.2)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(0.5)

    draw_col_headers()

    rows_per_col = -(-len(site_data) // col_sets)
    pdf.set_font('Helvetica', '', 6)

    for row in range(rows_per_col):
        if pdf.get_y() > 275:
            pdf.add_page()
            draw_col_headers()
            pdf.set_font('Helvetica', '', 6)

        if row % 2 == 0:
            pdf.set_fill_color(*ROW_ALT)
            fill = True
        else:
            fill = False

        for col in range(col_sets):
            idx = col * rows_per_col + row
            if idx < len(site_data):
                s = site_data[idx]
                pdf.set_text_color(*DARK)
                pdf.cell(name_w, 4, s['name'], fill=fill, align='C')
                r, g, b = STATUS_COLORS.get(s['status'], MID)
                pdf.set_text_color(r, g, b)
                pdf.set_font('Helvetica', 'B', 6)
                pdf.cell(stat_w, 4, s['status'], fill=fill, align='C')
                pdf.set_font('Helvetica', '', 6)
                pdf.set_text_color(*DARK)
                pdf.cell(date_w, 4, s['last_checked'], fill=fill, align='C')
            else:
                pdf.cell(name_w + stat_w + date_w, 4, '', fill=False)
            if col < col_sets - 1:
                pdf.cell(gap, 4, '', fill=False)
        pdf.ln()

    os.makedirs(os.path.dirname(output), exist_ok=True)
    pdf.output(output)
    print(f'Report saved: {output}')
    return output


if __name__ == '__main__':
    if len(sys.argv) >= 3:
        generate_report(int(sys.argv[1]), int(sys.argv[2]))
    elif len(sys.argv) == 2 and sys.argv[1] == 'current':
        now = datetime.now()
        generate_report(now.year, now.month)
    else:
        generate_report()
