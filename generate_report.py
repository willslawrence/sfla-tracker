#!/usr/bin/env python3
"""
SFLA Monthly Report Generator
Generates a PDF report matching THC document style (Aptos Narrow, THC logo header).
Shows: Summary, Change Log, then SFLA Shape Status (compact 2-page target).
"""

import json, sys, os
from datetime import datetime, timedelta
from fpdf import FPDF
import urllib.request, urllib.parse

# Config
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')
LOGO_PATH = os.path.join(os.path.dirname(__file__), 'thc_logo.png')
config = json.load(open(CONFIG_PATH))
BASE_ID = config['airtable']['baseId']
API_KEY = config['airtable']['apiKey']
SITES_TABLE = 'Sites'
CHANGELOG_TABLE = 'Change Log'

# THC brand colors
THC_ORANGE = (237, 125, 49)  # #ED7D31
BLACK = (0, 0, 0)
DARK_GREY = (50, 50, 50)
MID_GREY = (100, 100, 100)
LIGHT_GREY = (220, 220, 220)
WHITE = (255, 255, 255)

# Status colors
STATUS_COLORS = {
    'Suitable': (76, 175, 80),       # Green
    'Unsuitable': (107, 114, 128),   # Grey
    'Pending': (244, 67, 54),        # Red
    'New SFLA': (244, 67, 54),       # Red
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
    if month == 12:
        end = datetime(year + 1, 1, 1)
    else:
        end = datetime(year, month + 1, 1)
    return start, end


class SFLAReport(FPDF):
    def __init__(self, month_str):
        super().__init__()
        self.month_str = month_str
        # Use built-in Helvetica as closest match to Aptos Narrow
        self.set_auto_page_break(auto=True, margin=15)

    def header(self):
        # THC logo top-right
        if os.path.exists(LOGO_PATH):
            self.image(LOGO_PATH, x=160, y=6, w=35)
        
        # Orange accent line
        self.set_draw_color(*THC_ORANGE)
        self.set_line_width(1.5)
        self.line(10, 22, 155, 22)
        
        # Title
        self.set_xy(10, 8)
        self.set_font('Helvetica', 'B', 16)
        self.set_text_color(*DARK_GREY)
        self.cell(0, 7, 'Riyadh UAM SFLA Report', new_x="LMARGIN", new_y="NEXT")
        self.set_font('Helvetica', '', 10)
        self.set_text_color(*MID_GREY)
        self.cell(0, 5, self.month_str, new_x="LMARGIN", new_y="NEXT")
        self.ln(6)

    def footer(self):
        self.set_y(-12)
        self.set_font('Helvetica', 'I', 7)
        self.set_text_color(*MID_GREY)
        self.cell(95, 8, f'Generated {datetime.now().strftime("%Y-%m-%d %H:%M")} | THC SFLA Tracker')
        self.cell(95, 8, f'Page {self.page_no()}', align='R')

    def section_title(self, title):
        self.set_font('Helvetica', 'B', 12)
        self.set_text_color(*DARK_GREY)
        self.cell(0, 7, title, new_x="LMARGIN", new_y="NEXT")
        # Orange underline
        self.set_draw_color(*THC_ORANGE)
        self.set_line_width(0.5)
        self.line(10, self.get_y(), 80, self.get_y())
        self.ln(3)

    def status_dot(self, status, x=None, y=None):
        r, g, b = STATUS_COLORS.get(status, MID_GREY)
        cx = x or self.get_x()
        cy = y or (self.get_y() + 2.5)
        self.set_fill_color(r, g, b)
        self.ellipse(cx, cy, 3, 3, style='F')


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

    # Fetch data
    sites = api_get(SITES_TABLE)
    site_data = []
    for r in sites:
        f = r.get('fields', {})
        site_data.append({
            'name': f.get('Name', ''),
            'status': f.get('Status', 'Unknown'),
            'area': f.get('Area', ''),
            'last_checked': f.get('LastChecked', ''),
        })
    site_data.sort(key=lambda x: x['name'])

    # Fetch change log
    formula = f"AND(IS_AFTER(Timestamp, '{start.strftime('%Y-%m-%dT00:00:00')}'), IS_BEFORE(Timestamp, '{end.strftime('%Y-%m-%dT00:00:00')}'))"
    changes = api_get(CHANGELOG_TABLE, f'&filterByFormula={urllib.parse.quote(formula)}&sort%5B0%5D%5Bfield%5D=Timestamp&sort%5B0%5D%5Bdirection%5D=desc')
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

    # Count statuses
    counts = {}
    for s in site_data:
        st = s['status']
        counts[st] = counts.get(st, 0) + 1
    
    # Count checks done this month (changes where NewStatus is Suitable or Unsuitable)
    checks_done = sum(1 for c in change_data if c['new'] in ('Suitable', 'Unsuitable'))

    # Build PDF
    pdf = SFLAReport(month_str)
    pdf.add_page()

    # === SUMMARY ===
    pdf.section_title('Summary')
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(*DARK_GREY)
    
    total = len(site_data)
    pdf.cell(0, 6, f'Total SFLA Shapes: {total}', new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f'Total Changes This Month: {len(change_data)}', new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f'Total Checks Completed: {checks_done}', new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # Status breakdown with colored dots
    status_order = ['Suitable', 'Unsuitable', 'Pending', 'New SFLA']
    for status in status_order:
        c = counts.get(status, 0)
        if c == 0:
            continue
        pct = round(c / total * 100, 1) if total else 0
        x_start = pdf.get_x()
        pdf.status_dot(status, x_start + 2)
        pdf.set_x(x_start + 7)
        pdf.set_font('Helvetica', '', 10)
        pdf.set_text_color(*DARK_GREY)
        pdf.cell(0, 6, f'{status}: {c} ({pct}%)', new_x="LMARGIN", new_y="NEXT")

    pdf.ln(4)

    # === CHANGE LOG ===
    pdf.section_title(f'Change Log - {month_str}')

    if not change_data:
        pdf.set_font('Helvetica', 'I', 9)
        pdf.set_text_color(*MID_GREY)
        pdf.cell(0, 6, 'No changes recorded this month.', new_x="LMARGIN", new_y="NEXT")
    else:
        # Table header
        pdf.set_font('Helvetica', 'B', 8)
        pdf.set_text_color(*WHITE)
        pdf.set_fill_color(*DARK_GREY)
        cl_w = [30, 20, 28, 28, 84]
        cl_headers = ['Date', 'Shape', 'From', 'To', 'Notes']
        for i, h in enumerate(cl_headers):
            pdf.cell(cl_w[i], 6, h, border=1, fill=True, align='C')
        pdf.ln()

        pdf.set_font('Helvetica', '', 7)
        for i, c in enumerate(change_data):
            if pdf.get_y() > 270:
                pdf.add_page()
                # Re-draw header
                pdf.set_font('Helvetica', 'B', 8)
                pdf.set_text_color(*WHITE)
                pdf.set_fill_color(*DARK_GREY)
                for j, h in enumerate(cl_headers):
                    pdf.cell(cl_w[j], 6, h, border=1, fill=True, align='C')
                pdf.ln()
                pdf.set_font('Helvetica', '', 7)

            bg = (245, 245, 245) if i % 2 == 0 else WHITE
            pdf.set_fill_color(*bg)

            ts = c['timestamp'][:16].replace('T', ' ') if c['timestamp'] else ''
            pdf.set_text_color(*DARK_GREY)
            pdf.cell(cl_w[0], 5, ts, border=1, fill=True)
            pdf.cell(cl_w[1], 5, c['name'], border=1, fill=True, align='C')

            # Colored status cells
            for val, wi in [(c['prev'], cl_w[2]), (c['new'], cl_w[3])]:
                r, g, b = STATUS_COLORS.get(val, MID_GREY)
                pdf.set_text_color(r, g, b)
                pdf.set_font('Helvetica', 'B', 7)
                pdf.cell(wi, 5, val, border=1, fill=True, align='C')

            pdf.set_font('Helvetica', '', 7)
            pdf.set_text_color(*DARK_GREY)
            notes = c.get('notes', '') or ''
            if len(notes) > 60:
                notes = notes[:57] + '...'
            pdf.cell(cl_w[4], 5, notes, border=1, fill=True)
            pdf.ln()

    pdf.ln(4)

    # === SFLA STATUS TABLE ===
    # Compact: fit all shapes in multi-column layout
    if pdf.get_y() > 200:
        pdf.add_page()
    
    pdf.section_title('Current SFLA Status')

    # Use 4-column layout: Name | Status | Name | Status (x2)
    col_sets = 4  # 4 pairs across
    pair_w = 190 / col_sets  # ~47.5 each
    name_w = pair_w * 0.55
    stat_w = pair_w * 0.45

    # Header row
    pdf.set_font('Helvetica', 'B', 7)
    pdf.set_text_color(*WHITE)
    pdf.set_fill_color(*DARK_GREY)
    for _ in range(col_sets):
        pdf.cell(name_w, 5, 'Shape', border=1, fill=True, align='C')
        pdf.cell(stat_w, 5, 'Status', border=1, fill=True, align='C')
    pdf.ln()

    # Fill rows across columns
    rows_per_col = -(-len(site_data) // col_sets)  # ceiling division
    pdf.set_font('Helvetica', '', 7)
    
    for row in range(rows_per_col):
        if pdf.get_y() > 275:
            pdf.add_page()
            # Re-draw header
            pdf.set_font('Helvetica', 'B', 7)
            pdf.set_text_color(*WHITE)
            pdf.set_fill_color(*DARK_GREY)
            for _ in range(col_sets):
                pdf.cell(name_w, 5, 'Shape', border=1, fill=True, align='C')
                pdf.cell(stat_w, 5, 'Status', border=1, fill=True, align='C')
            pdf.ln()
            pdf.set_font('Helvetica', '', 7)

        bg = (248, 248, 248) if row % 2 == 0 else WHITE
        pdf.set_fill_color(*bg)

        for col in range(col_sets):
            idx = col * rows_per_col + row
            if idx < len(site_data):
                s = site_data[idx]
                pdf.set_text_color(*DARK_GREY)
                pdf.cell(name_w, 4.5, s['name'], border=1, fill=True, align='C')
                r, g, b = STATUS_COLORS.get(s['status'], MID_GREY)
                pdf.set_text_color(r, g, b)
                pdf.set_font('Helvetica', 'B', 7)
                pdf.cell(stat_w, 4.5, s['status'], border=1, fill=True, align='C')
                pdf.set_font('Helvetica', '', 7)
            else:
                pdf.cell(name_w + stat_w, 4.5, '', border=0)
        pdf.ln()

    os.makedirs(os.path.dirname(output), exist_ok=True)
    pdf.output(output)
    print(f'Report saved: {output}')
    return output


if __name__ == '__main__':
    # Usage: python3 generate_report.py [YYYY] [MM]  |  python3 generate_report.py current
    if len(sys.argv) >= 3:
        generate_report(int(sys.argv[1]), int(sys.argv[2]))
    elif len(sys.argv) == 2 and sys.argv[1] == 'current':
        now = datetime.now()
        generate_report(now.year, now.month)
    else:
        generate_report()
