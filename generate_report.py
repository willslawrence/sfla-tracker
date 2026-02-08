#!/usr/bin/env python3
"""
SFLA Monthly Report Generator
Generates a PDF report showing:
  - Status summary of all SFLA shapes
  - Change log for the reporting period
"""

import json, sys, os
from datetime import datetime, timedelta
from fpdf import FPDF
import urllib.request, urllib.parse

# Config
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')
config = json.load(open(CONFIG_PATH))
BASE_ID = config['airtable']['baseId']
API_KEY = config['airtable']['apiKey']
SITES_TABLE = 'Sites'
CHANGELOG_TABLE = 'Change Log'

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

    def header(self):
        self.set_font('Helvetica', 'B', 18)
        self.set_text_color(255, 102, 0)  # THC orange
        self.cell(0, 12, 'THC Riyadh UAM SFLA Report', new_x="LMARGIN", new_y="NEXT", align='C')
        self.set_font('Helvetica', '', 12)
        self.set_text_color(100, 100, 100)
        self.cell(0, 8, self.month_str, new_x="LMARGIN", new_y="NEXT", align='C')
        self.ln(4)
        self.set_draw_color(200, 200, 200)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f'Generated {datetime.now().strftime("%Y-%m-%d %H:%M")} | THC SFLA Tracker', align='C')

    def section_title(self, title):
        self.set_font('Helvetica', 'B', 14)
        self.set_text_color(40, 40, 40)
        self.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def status_color(self, status):
        colors = {
            'Suitable': (76, 175, 80),
            'Unsuitable': (244, 67, 54),
            'Pending': (255, 152, 0),
        }
        return colors.get(status, (150, 150, 150))

def generate_report(year=None, month=None, output=None):
    now = datetime.now()
    if year is None:
        # Default to previous month
        first = now.replace(day=1)
        prev = first - timedelta(days=1)
        year, month = prev.year, prev.month
    
    start, end = get_month_range(year, month)
    month_str = start.strftime('%B %Y')
    
    if output is None:
        output = os.path.expanduser(f'~/Desktop/Willy/SFLA_Report_{start.strftime("%Y-%m")}.pdf')

    print(f'Generating SFLA report for {month_str}...')

    # Fetch all sites
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

    # Fetch change log for the month
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

    # Build PDF
    pdf = SFLAReport(month_str)
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # === Summary ===
    pdf.section_title('Summary')
    pdf.set_font('Helvetica', '', 11)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(0, 7, f'Total SFLA shapes: {len(site_data)}', new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, f'Changes this month: {len(change_data)}', new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    for status in ['Suitable', 'Unsuitable', 'Pending']:
        c = counts.get(status, 0)
        pct = round(c / len(site_data) * 100, 1) if site_data else 0
        r, g, b = pdf.status_color(status)
        pdf.set_fill_color(r, g, b)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font('Helvetica', 'B', 11)
        bar_w = max(pct * 1.2, 15)
        pdf.cell(bar_w, 8, f' {status}: {c} ({pct}%)', fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

    pdf.ln(6)

    # === All Shapes Status ===
    pdf.section_title('SFLA Shape Status')
    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_text_color(255, 255, 255)
    pdf.set_fill_color(50, 50, 50)
    col_w = [25, 35, 45, 35]
    headers = ['Shape', 'Status', 'Area', 'Last Checked']
    for i, h in enumerate(headers):
        pdf.cell(col_w[i], 7, h, border=1, fill=True, align='C')
    pdf.ln()

    pdf.set_font('Helvetica', '', 9)
    for i, s in enumerate(site_data):
        r, g, b = pdf.status_color(s['status'])
        if i % 2 == 0:
            pdf.set_fill_color(245, 245, 245)
        else:
            pdf.set_fill_color(255, 255, 255)
        
        pdf.set_text_color(60, 60, 60)
        pdf.cell(col_w[0], 6, s['name'], border=1, fill=True, align='C')
        pdf.set_text_color(r, g, b)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.cell(col_w[1], 6, s['status'], border=1, fill=True, align='C')
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(60, 60, 60)
        pdf.cell(col_w[2], 6, s['area'], border=1, fill=True, align='C')
        pdf.cell(col_w[3], 6, s['last_checked'], border=1, fill=True, align='C')
        pdf.ln()

    # === Change Log ===
    pdf.add_page()
    pdf.section_title(f'Change Log - {month_str}')

    if not change_data:
        pdf.set_font('Helvetica', 'I', 11)
        pdf.set_text_color(150, 150, 150)
        pdf.cell(0, 10, 'No changes recorded this month.', new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.set_font('Helvetica', 'B', 9)
        pdf.set_text_color(255, 255, 255)
        pdf.set_fill_color(50, 50, 50)
        cl_w = [35, 25, 30, 30, 70]
        cl_headers = ['Date', 'Shape', 'From', 'To', 'Notes']
        for i, h in enumerate(cl_headers):
            pdf.cell(cl_w[i], 7, h, border=1, fill=True, align='C')
        pdf.ln()

        pdf.set_font('Helvetica', '', 8)
        for i, c in enumerate(change_data):
            if i % 2 == 0:
                pdf.set_fill_color(245, 245, 245)
            else:
                pdf.set_fill_color(255, 255, 255)

            ts = c['timestamp'][:16].replace('T', ' ') if c['timestamp'] else ''
            pdf.set_text_color(60, 60, 60)
            pdf.cell(cl_w[0], 6, ts, border=1, fill=True)
            pdf.cell(cl_w[1], 6, c['name'], border=1, fill=True, align='C')
            
            # Color the from/to statuses
            for val, wi in [(c['prev'], cl_w[2]), (c['new'], cl_w[3])]:
                r, g, b = pdf.status_color(val)
                pdf.set_text_color(r, g, b)
                pdf.set_font('Helvetica', 'B', 8)
                pdf.cell(wi, 6, val, border=1, fill=True, align='C')
            
            pdf.set_font('Helvetica', '', 8)
            pdf.set_text_color(60, 60, 60)
            notes = c['notes'][:50] + '...' if len(c.get('notes', '')) > 50 else c.get('notes', '')
            pdf.cell(cl_w[4], 6, notes, border=1, fill=True)
            pdf.ln()

    os.makedirs(os.path.dirname(output), exist_ok=True)
    pdf.output(output)
    print(f'✅ Report saved: {output}')
    return output

if __name__ == '__main__':
    # Usage: python3 generate_report.py [YYYY] [MM]
    if len(sys.argv) >= 3:
        generate_report(int(sys.argv[1]), int(sys.argv[2]))
    elif len(sys.argv) == 2 and sys.argv[1] == 'current':
        now = datetime.now()
        generate_report(now.year, now.month)
    else:
        generate_report()
