import requests
import openpyxl
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter
from bs4 import BeautifulSoup
from datetime import datetime
from io import BytesIO
from openpyxl.drawing.image import Image
from PIL import Image as PILImage

# --- Flask লাইব্রেরি ইম্পোর্ট ---
from flask import Flask, request, render_template_string, send_file, flash

app = Flask(__name__)
app.secret_key = 'a-secret-key-for-flash-messages' # যেকোনো কী দিতে পারেন

# ==============================================================================
# ফাংশন ১: ERP সিস্টেমে লগইন করার ফাংশন
# ==============================================================================
def get_authenticated_session(username, password):
    login_url = 'http://103.231.177.24:8022/erp/login.php'
    login_payload = {'txt_userid': username, 'txt_password': password, 'submit': 'Login'}
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    })
    try:
        print("লগইন করার চেষ্টা করা হচ্ছে...")
        response = session.post(login_url, data=login_payload, timeout=20)
        if "dashboard.php" in response.url or "Invalid" not in response.text:
            print("✅ লগইন সফল হয়েছে!")
            return session
        else:
            print("❌ লগইন ব্যর্থ হয়েছে।")
            return None
    except requests.exceptions.RequestException as e:
        print(f"লগইন করার সময় একটি ত্রুটি ঘটেছে: {e}")
        return None

# ==============================================================================
# ফাংশন ২: HTML থেকে ডেটা পার্স করার ফাংশন
# ==============================================================================
def parse_report_data(html_content):
    all_report_data = []
    try:
        soup = BeautifulSoup(html_content, 'lxml')
        header_row = soup.select_one('thead tr:nth-of-type(2)')
        if not header_row:
            print("ত্রুটি: রিপোর্টের টেবিল হেডার খুঁজে পাওয়া যায়নি।")
            return None
        all_th = header_row.find_all('th')
        headers = [th.get_text(strip=True) for th in all_th if 'total' not in th.get_text(strip=True).lower()]
        data_rows = soup.select('div#scroll_body table tbody tr')
        item_blocks = []
        current_block = []
        for row in data_rows:
            if row.get('bgcolor') == '#cddcdc':
                if current_block: item_blocks.append(current_block)
                current_block = []
            else:
                current_block.append(row)
        if current_block: item_blocks.append(current_block)
        for block in item_blocks:
            style, color, buyer_name, gmts_qty_data, sewing_input_data, cutting_qc_data = "N/A", "N/A", "N/A", None, None, None
            for row in block:
                cells = row.find_all('td')
                if len(cells) > 2:
                    criteria_main = cells[0].get_text(strip=True)
                    criteria_sub = cells[2].get_text(strip=True)
                    main_lower, sub_lower = criteria_main.lower(), criteria_sub.lower()
                    if main_lower == "style": style = cells[1].get_text(strip=True)
                    elif main_lower == "color & gmts. item": color = cells[1].get_text(strip=True)
                    elif "buyer" in main_lower: buyer_name = cells[1].get_text(strip=True)
                    if sub_lower == "gmts. color /country qty": gmts_qty_data = [cell.get_text(strip=True) for cell in cells[3:len(headers)+3]]
                    if "sewing input" in main_lower: sewing_input_data = [cell.get_text(strip=True) for cell in cells[1:len(headers)+1]]
                    elif "sewing input" in sub_lower: sewing_input_data = [cell.get_text(strip=True) for cell in cells[3:len(headers)+3]]
                    if "cutting qc" in main_lower and "balance" not in main_lower:
                        cutting_qc_data = [cell.get_text(strip=True) for cell in cells[1:len(headers)+1]]
                    elif "cutting qc" in sub_lower and "balance" not in sub_lower:
                        cutting_qc_data = [cell.get_text(strip=True) for cell in cells[3:len(headers)+3]]
            if gmts_qty_data:
                plus_3_percent_data = []
                for value in gmts_qty_data:
                    try:
                        new_qty = round(int(value.replace(',', '')) * 1.03)
                        plus_3_percent_data.append(str(new_qty))
                    except (ValueError, TypeError):
                        plus_3_percent_data.append(value)
                all_report_data.append({'style': style, 'buyer': buyer_name, 'color': color, 'headers': headers, 'gmts_qty': gmts_qty_data, 'plus_3_percent': plus_3_percent_data, 'sewing_input': sewing_input_data if sewing_input_data else [], 'cutting_qc': cutting_qc_data if cutting_qc_data else []})
        return all_report_data
    except Exception as e:
        print(f"ডেটা পার্স করার সময় ত্রুটি হয়েছে: {e}")
        return None

# ==============================================================================
# ফাংশন ৩: ফরম্যাটেড এক্সেল রিপোর্ট তৈরির ফাংশন
# ==============================================================================
def create_formatted_excel_report(report_data, internal_ref_no=""):
    if not report_data: return None
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Closing Report"
   
    # --- স্টাইলসমূহ ---
    bold_font = Font(bold=True)
    center_align = Alignment(horizontal='center', vertical='center')
    left_align = Alignment(horizontal='left', vertical='center')
    color_align = Alignment(horizontal='center', vertical='center', wrap_text=True)
    thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
    medium_border = Border(left=Side(style='medium'), right=Side(style='medium'), top=Side(style='medium'), bottom=Side(style='medium'))
    light_brown_fill = PatternFill(start_color="FFF5E8D1", end_color="FFF5E8D1", fill_type="solid")
    light_red_fill = PatternFill(start_color="FFFFCDD2", end_color="FFFFCDD2", fill_type="solid")
    light_blue_fill = PatternFill(start_color="FFDDEBF7", end_color="FFDDEBF7", fill_type="solid")
    light_green_fill = PatternFill(start_color="FFE2F0D9", end_color="FFE2F0D9", fill_type="solid")

    NUM_COLUMNS, TABLE_START_ROW = 9, 8
   
    # --- প্রধান দুটি হেডার ---
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=NUM_COLUMNS); ws['A1'].value = "COTTON CLOTHING BD LTD"; ws['A1'].font = Font(size=32, bold=True); ws['A1'].alignment = center_align
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=NUM_COLUMNS); ws['A2'].value = "CLOSING REPORT [ INPUT SECTION ]"; ws['A2'].font = Font(size=24, bold=False); ws['A2'].alignment = center_align
    ws.row_dimensions[3].height = 6

    # --- সাব-হেডারসমূহ ---
    formatted_ref_no = internal_ref_no.upper(); current_date = datetime.now().strftime("%d/%m/%Y")
    left_sub_headers = {'A4': 'BUYER', 'B4': report_data[0].get('buyer', ''), 'A5': 'IR/IB NO', 'B5': formatted_ref_no, 'A6': 'STYLE NO', 'B6': report_data[0].get('style', '')}
    for cell_ref, value in left_sub_headers.items():
        cell = ws[cell_ref]; cell.value = value; cell.font = bold_font; cell.alignment = left_align; cell.border = thin_border
    ws.merge_cells('B4:G4'); ws.merge_cells('B5:G5'); ws.merge_cells('B6:G6')
    right_sub_headers = {'H4': 'CLOSING DATE', 'I4': current_date, 'H5': 'SHIPMENT', 'I5': 'ALL', 'H6': 'PO NO', 'I6': 'ALL'}
    for cell_ref, value in right_sub_headers.items():
        cell = ws[cell_ref]; cell.value = value; cell.font = bold_font; cell.alignment = left_align; cell.border = thin_border
    for row in range(4, 7):
        for col in range(3, 8): ws.cell(row=row, column=col).border = thin_border
       
    current_row = TABLE_START_ROW
   
    # --- ডেটা টেবিল তৈরি ---
    for block in report_data:
        table_headers = ["COLOUR NAME", "SIZE", "ORDER QTY 3%", "ACTUAL QTY", "CUTTING QC", "INPUT QTY", "BALANCE", "SHORT/PLUS QTY", "Percentage %"]
        for col_idx, header in enumerate(table_headers, 1):
            cell = ws.cell(row=current_row, column=col_idx, value=header); cell.font = bold_font; cell.alignment = center_align; cell.border = medium_border
        current_row += 1
        start_merge_row = current_row
        full_color_name = block.get('color', 'N/A')
        total_input_qty, total_order_qty_3_percent, total_actual_qty, total_short_plus_qty, total_cutting_qc, total_balance = 0, 0, 0, 0, 0, 0
        for i, size in enumerate(block['headers']):
            color_to_write = full_color_name if i == 0 else ""
            actual_qty = int(block['gmts_qty'][i].replace(',', '') or 0)
            three_percent_qty = int(block['plus_3_percent'][i].replace(',', '') or 0)
            input_qty = int(block['sewing_input'][i].replace(',', '') or 0) if i < len(block['sewing_input']) else 0
            cutting_qc_val = int(block.get('cutting_qc', [])[i].replace(',', '') or 0) if i < len(block.get('cutting_qc', [])) else 0
            balance_val, short_plus_qty = cutting_qc_val - input_qty, input_qty - three_percent_qty
            percentage_val = (short_plus_qty / three_percent_qty) * 100 if three_percent_qty != 0 else 0.0
            percentage_str = f"{percentage_val:.2f}%"
            total_input_qty += input_qty; total_order_qty_3_percent += three_percent_qty; total_actual_qty += actual_qty; total_short_plus_qty += short_plus_qty; total_cutting_qc += cutting_qc_val; total_balance += balance_val
            row_data = [color_to_write, size, three_percent_qty, actual_qty, cutting_qc_val, input_qty, balance_val, short_plus_qty, percentage_str]
            for col_idx, value in enumerate(row_data, 1):
                cell = ws.cell(row=current_row, column=col_idx, value=value)
                cell.border = medium_border if col_idx == 2 else thin_border
                cell.alignment = center_align
                if col_idx in [1, 2, 3, 6, 9]: cell.font = bold_font
                if col_idx == 3: cell.fill = light_blue_fill
                elif col_idx == 6: cell.fill = light_green_fill
                if col_idx == 9 and percentage_val <= -3: cell.fill = light_red_fill
            current_row += 1
        end_merge_row = current_row - 1
        if start_merge_row <= end_merge_row:
            ws.merge_cells(start_row=start_merge_row, start_column=1, end_row=end_merge_row, end_column=1)
            merged_cell = ws.cell(row=start_merge_row, column=1)
            merged_cell.alignment = color_align
            if not merged_cell.font.bold: merged_cell.font = bold_font
        total_percentage_str = f"{(total_short_plus_qty / total_order_qty_3_percent) * 100:.2f}%" if total_order_qty_3_percent != 0 else "0.00%"
        ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=2)
        totals = {"A": "TOTAL", "C": total_order_qty_3_percent, "D": total_actual_qty, "E": total_cutting_qc, "F": total_input_qty, "G": total_balance, "H": total_short_plus_qty, "I": total_percentage_str}
        for col_letter, value in totals.items():
            cell = ws[f"{col_letter}{current_row}"]
            cell.value = value; cell.font = bold_font; cell.border = medium_border; cell.alignment = center_align; cell.fill = light_brown_fill
        for col_idx in range(2, NUM_COLUMNS + 1):
            cell = ws.cell(row=current_row, column=col_idx)
            if not cell.value: cell.fill = light_brown_fill; cell.border = medium_border
        current_row += 2
       
    image_row = current_row + 1
   
    # --- ছবি যোগ করার অংশ ---
    try:
        direct_image_url = 'https://i.ibb.co/v6bp0jQW/rockybilly-regular.webp'
        image_response = requests.get(direct_image_url); image_response.raise_for_status()
        original_img = PILImage.open(BytesIO(image_response.content))
        padded_img = PILImage.new('RGBA', (original_img.width + 400, original_img.height), (0, 0, 0, 0))
        padded_img.paste(original_img, (400, 0))
        padded_image_io = BytesIO(); padded_img.save(padded_image_io, format='PNG')
        img = Image(padded_image_io); aspect_ratio = padded_img.height / padded_img.width
        img.width = 95; img.height = int(img.width * aspect_ratio)
        ws.row_dimensions[image_row].height = img.height * 0.90; ws.add_image(img, f'A{image_row}')
    except Exception as e:
        print(f"ছবি যোগ করার সময় ত্রুটি: {e}")

    # --- স্বাক্ষর সেকশন (ফন্ট সাইজ পরিবর্তন করা হয়েছে) ---
    signature_row = image_row + 1
    ws.merge_cells(start_row=signature_row, start_column=1, end_row=signature_row, end_column=NUM_COLUMNS)
    titles = ["Prepared By", "Input Incharge", "Cutting Incharge", "IE & Planning", "Sewing Manager", "Cutting Manager"]
    signature_cell = ws.cell(row=signature_row, column=1)
    signature_cell.value = "                  ".join(titles)
    signature_cell.font = Font(bold=True, size=15)
    signature_cell.alignment = Alignment(horizontal='center', vertical='center')

    # --- ডেটা টেবিলের ফন্ট সাইজ ---
    last_data_row = current_row - 2
    for row in ws.iter_rows(min_row=4, max_row=last_data_row):
        for cell in row:
            if cell.font:
                existing_font = cell.font
                new_font = Font(name=existing_font.name, size=16.5, bold=existing_font.bold, italic=existing_font.italic, vertAlign=existing_font.vertAlign, underline=existing_font.underline, strike=existing_font.strike, color=existing_font.color)
                cell.font = new_font
   
    # --- কলামের প্রস্থ ঠিক করা ---
    ws.column_dimensions['A'].width = 23
    ws.column_dimensions['B'].width = 6.5
    ws.column_dimensions['C'].width = 20
    ws.column_dimensions['D'].width = 17
    ws.column_dimensions['E'].width = 17
    ws.column_dimensions['F'].width = 15
    ws.column_dimensions['G'].width = 13.5
    ws.column_dimensions['H'].width = 23
    ws.column_dimensions['I'].width = 18
   
    # --- পেজ সেটআপ (আপনার ছবির মতো করে পরিবর্তন করা হয়েছে) ---
    ws.page_setup.orientation = ws.ORIENTATION_PORTRAIT
    ws.page_setup.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0 
    
    # Horizontally = True, Vertically = False
    ws.page_setup.horizontalCentered = True
    ws.page_setup.verticalCentered = False 

    # ছবির মতো করে মার্জিন সেট করা হয়েছে (মান ইঞ্চিতে)
    ws.page_setup.left = 0.25
    ws.page_setup.right = 0.25
    ws.page_setup.top = 0.45
    ws.page_setup.bottom = 0.45
    ws.page_setup.header = 0
    ws.page_setup.footer = 0
   
    # --- ফাইল সেভ করার পরিবর্তে মেমোরি থেকে রিটার্ন করা ---
    file_stream = BytesIO()
    wb.save(file_stream)
    file_stream.seek(0)
    print(f"✅ রিপোর্ট সফলভাবে মেমোরিতে তৈরি হয়েছে।")
    return file_stream

# ==============================================================================
# Flask ওয়েব অ্যাপ্লিকেশনের অংশ
# ==============================================================================

# --- ওয়েবপেজের জন্য HTML টেমপ্লেট ---
HTML_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Closing Report Generator</title>
    <style>
        body { font-family: sans-serif; background: #f4f4f9; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .container { background: white; padding: 2rem; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); text-align: center; }
        h1 { color: #333; }
        input[type="text"] { width: 100%; padding: 10px; margin-top: 1rem; border: 1px solid #ccc; border-radius: 4px; }
        button { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 4px; margin-top: 1.5rem; cursor: pointer; font-size: 1rem; }
        button:hover { background: #0056b3; }
        .flash { padding: 1rem; margin-top: 1rem; border-radius: 4px; background-color: #f8d7da; color: #721c24; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Closing Report Generator</h1>
        <form action="/generate-report" method="post">
            <label for="ref_no">Enter Internal Ref No:</label>
            <input type="text" id="ref_no" name="ref_no" required>
            <button type="submit">Generate Report</button>
        </form>
        {% with messages = get_flashed_messages() %}
            {% if messages %}
                <div class="flash">{{ messages[0] }}</div>
            {% endif %}
        {% endwith %}
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/generate-report', methods=['POST'])
def generate_report():
    internal_ref_no = request.form['ref_no']
    if not internal_ref_no:
        flash("Internal Ref No is required!")
        return render_template_string(HTML_TEMPLATE)

    # ERP তে লগইন করা
    active_session = get_authenticated_session("Clothing-cutting", "489356")
    if not active_session:
        flash("Login failed! Check credentials.")
        return render_template_string(HTML_TEMPLATE)

    # রিপোর্ট খোঁজা
    report_url = 'http://103.231.177.24:8022/erp/prod_planning/reports/requires/cutting_lay_production_report_controller.php'
    payload_template = {'action': 'report_generate', 'cbo_wo_company_name': '2', 'cbo_location_name': '2', 'cbo_floor_id': '0', 'cbo_buyer_name': '0', 'txt_internal_ref_no': internal_ref_no, 'reportType': '3'}
    found_data = None
   
    # এখানে 2025 সাল ব্যবহার করা হয়েছে
    for year in ['2025', '2024']:
        for company_id in range(1, 6):
            payload = payload_template.copy()
            payload['cbo_year_selection'] = year
            payload['cbo_company_name'] = str(company_id)
            try:
                response = active_session.post(report_url, data=payload, timeout=30)
                if response.status_code == 200 and "Data not Found" not in response.text:
                    found_data = response.text
                    break
            except requests.exceptions.RequestException as e:
                print(f"একটি ত্রুটি ঘটেছে: {e}")
        if found_data:
            break
           
    if not found_data:
        flash(f"No data found for Ref No: {internal_ref_no}")
        return render_template_string(HTML_TEMPLATE)

    report_data = parse_report_data(found_data)
    if not report_data:
        flash(f"Failed to parse data for Ref No: {internal_ref_no}")
        return render_template_string(HTML_TEMPLATE)

    # এক্সেল ফাইল তৈরি ও পাঠানো
    excel_file_stream = create_formatted_excel_report(report_data, internal_ref_no)
    if excel_file_stream:
        return send_file(
            excel_file_stream,
            as_attachment=True,
            download_name=f"Closing_Report_{internal_ref_no.replace('/', '_')}.xlsx",
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    else:
        flash("Could not generate the Excel file.")
        return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(debug=True)
