import requests
import json
from bs4 import BeautifulSoup
from flask import Flask, request, render_template_string

app = Flask(__name__)

# --- ধাপ ০: স্বয়ংক্রিয় লগইন করার ফাংশন ---
def perform_login():
    """ERP সিস্টেমে লগইন করে এবং একটি সেশন অবজেক্ট ফেরত দেয়।"""
    LOGIN_URL = 'http://180.92.235.190:8022/erp/login.php'
    USERNAME = 'Clothing-cutting'
    PASSWORD = '489356'
    
    login_payload = {
        'hiddenUserIP': '', 'hiddenUserMAC': '', 'txt_userid': USERNAME,
        'txt_password': PASSWORD, 'submit': 'Login',
    }
    session = requests.Session()
    try:
        login_response = session.post(LOGIN_URL, data=login_payload, timeout=15)
        login_response.raise_for_status()
        if "logout" not in login_response.text.lower():
            return None, "লগইন ব্যর্থ হয়েছে। ইউজারনেম বা পাসওয়ার্ড সঠিক কিনা তা পরীক্ষা করুন।"
        return session, "লগইন সফল হয়েছে।"
    except requests.exceptions.RequestException as e:
        return None, f"লগইন করার সময় ত্রুটি: {e}"

# --- আপনার মূল লজিক যা এখন প্যারামিটার গ্রহণ করে ---
def fetch_report_data(ref_number, line_number, selected_color_id):
    """প্রদত্ত ইনপুটের উপর ভিত্তি করে চূড়ান্ত রিপোর্ট তৈরি করে।"""
    session, login_message = perform_login()
    if not session:
        return f"<p>❌ {login_message}</p>"

    # ধাপ ১: প্রথম API
    api1_url = "https://logic-job-no.onrender.com/get_info"
    params1 = {'ref': ref_number}
    response1 = session.get(api1_url, params=params1, timeout=30)
    data1 = response1.json()
    job_no = data1.get("job_no")
    company_id = data1.get("company_id")
    if not all([job_no, company_id]):
        return "<p>❌ ত্রুটি: প্রথম API থেকে 'job_no' বা 'company_id' পাওয়া যায়নি।</p>"
    last_five_digits = job_no[-5:]

    # ধাপ ২: দ্বিতীয় API
    api2_base_url = "http://180.92.235.190:8022/erp/production/reports/requires/bundle_wise_sewing_tracking_report_controller.php"
    params2 = {'data': f"{company_id}**0**1**{last_five_digits}**0", 'action': 'search_list_view'}
    response2 = session.get(api2_base_url, params=params2, timeout=120)
    soup = BeautifulSoup(response2.text, 'html.parser')
    first_row = soup.find('table', id='tbl_list_search').find('tbody').find('tr')
    txt_job_id = first_row.get('onclick').split("'")[1].split('_')[1]

    # ধাপ ৪: চূড়ান্ত রিপোর্ট জেনারেট
    post_data = {
        'action': 'report_generate', 'cbo_lc_company_id': company_id, 'cbo_working_company_id': '2',
        'cbo_location_id': '2', 'cbo_floor_id': '0', 'cbo_buyer_id': '0', 'txt_job_no': job_no,
        'txt_file_no': '', 'txt_int_ref': '', 'color_id': selected_color_id, 'txt_cutting_no': '',
        'txt_bunle_no': '', 'txt_date_from': '', 'txt_date_to': '', 'txt_job_id': txt_job_id,
        'txt_color_name': selected_color_id, 'type': '2'
    }
    response4 = session.post(api2_base_url, data=post_data, timeout=300)
    soup4 = BeautifulSoup(response4.text, 'html.parser')
    report_rows = soup4.find_all('tr', id=lambda x: x and x.startswith('tr_'))

    if not report_rows:
        return "<p>রিপোর্টে কোনো ডেটা পাওয়া যায়নি।</p>"

    results_html = ""
    overall_results_found = False
    for row in report_rows:
        cells = row.find_all('td')
        if len(cells) >= 24:
            status_col_18 = cells[18].get_text(strip=True)
            line_no_col_22 = cells[21].get_text(strip=True)
            
            if status_col_18 == 'No' and line_no_col_22 == line_number:
                overall_results_found = True
                results_html += "<hr>"
                results_html += f"<p><b>SL No:</b> {cells[0].get_text(strip=True)}</p>"
                results_html += f"<p><b>Barcode No:</b> {cells[1].get_text(strip=True)}</p>"
                results_html += f"<p><b>Size:</b> {cells[3].get_text(strip=True)}</p>"
                results_html += f"<p><b>Bundle Qty:</b> {cells[22].get_text(strip=True)}</p>"
                results_html += f"<p><b>Input Date:</b> {cells[16].get_text(strip=True)}</p>"

    if not overall_results_found:
        return f"<p>এই রঙের জন্য লাইন '{line_number}' এ কোনো 'No' স্ট্যাটাস পাওয়া যায়নি।</p>"
    
    return results_html

# --- ওয়েব পেজের জন্য HTML টেমপ্লেট ---
# প্রথম পেজ: ref নম্বর ইনপুট নেওয়ার জন্য
INPUT_PAGE_TEMPLATE = """
<!doctype html>
<html>
<head><title>Report Generator</title></head>
<body>
    <h1>চূড়ান্ত রিপোর্ট জেনারেটর</h1>
    <form action="/get-colors" method="post">
        <label for="ref_number">অনুগ্রহ করে API 1 এর জন্য ref নম্বর দিন:</label><br>
        <input type="text" id="ref_number" name="ref_number" required><br><br>
        <label for="line_number">অনুগ্রহ করে লাইন নম্বর দিন:</label><br>
        <input type="text" id="line_number" name="line_number" required><br><br>
        <input type="submit" value="রঙের তালিকা দেখুন">
    </form>
</body>
</html>
"""

# দ্বিতীয় পেজ: রঙ সিলেক্ট করার জন্য
COLOR_SELECTION_TEMPLATE = """
<!doctype html>
<html>
<head><title>Select Color</title></head>
<body>
    <h1>🎨 অনুগ্রহ করে একটি রঙ সিলেক্ট করুন 🎨</h1>
    <form action="/generate-report" method="post">
        <input type="hidden" name="ref_number" value="{{ ref_number }}">
        <input type="hidden" name="line_number" value="{{ line_number }}">
        
        <label for="color_id">রঙ:</label>
        <select name="color_id" id="color_id">
            {% for color in colors %}
            <option value="{{ color.id }}">{{ color.name }}</option>
            {% endfor %}
        </select>
        <br><br>
        <input type="submit" value="রিপোর্ট জেনারেট করুন">
    </form>
    <br>
    <a href="/">ফিরে যান</a>
</body>
</html>
"""

# ফলাফল দেখানোর পেজ
RESULT_TEMPLATE = """
<!doctype html>
<html>
<head><title>Report Result</title></head>
<body>
    <h1>📊 রিপোর্ট (ফিল্টার করা) 📊</h1>
    <div>{{ content | safe }}</div>
    <br>
    <a href="/">আবার চেষ্টা করুন</a>
</body>
</html>
"""

# --- Flask Routes ---
@app.route('/', methods=['GET'])
def index():
    return render_template_string(INPUT_PAGE_TEMPLATE)

@app.route('/get-colors', methods=['POST'])
def get_colors():
    ref_number = request.form['ref_number']
    line_number = request.form['line_number']
    
    session, login_message = perform_login()
    if not session:
        return render_template_string(RESULT_TEMPLATE, content=f"<p>❌ {login_message}</p>")

    # API 1 এবং 2 থেকে তথ্য সংগ্রহ
    api1_url = "https://logic-job-no.onrender.com/get_info"
    params1 = {'ref': ref_number}
    response1 = session.get(api1_url, params=params1, timeout=30)
    data1 = response1.json()
    job_no = data1.get("job_no")
    company_id = data1.get("company_id")
    last_five_digits = job_no[-5:]

    api2_base_url = "http://180.92.235.190:8022/erp/production/reports/requires/bundle_wise_sewing_tracking_report_controller.php"
    params2 = {'data': f"{company_id}**0**1**{last_five_digits}**0", 'action': 'search_list_view'}
    response2 = session.get(api2_base_url, params=params2, timeout=120)
    soup = BeautifulSoup(response2.text, 'html.parser')
    first_row = soup.find('table', id='tbl_list_search').find('tbody').find('tr')
    txt_job_id = first_row.get('onclick').split("'")[1].split('_')[1]

    # রঙের তালিকা সংগ্রহ
    params3 = {'action': 'color_popup', 'txt_job_no': job_no, 'txt_job_id': txt_job_id}
    response3 = session.get(api2_base_url, params=params3, timeout=120)
    soup3 = BeautifulSoup(response3.text, 'html.parser')
    color_list = []
    color_table = soup3.find('table', id='list_view')
    if color_table:
        for row in color_table.find('tbody').find_all('tr'):
            onclick = row.get('onclick')
            cells = row.find_all('td')
            if onclick and len(cells) > 3:
                color_id = onclick.split("'")[1].split('_')[1]
                color_name = cells[3].get_text(strip=True)
                color_list.append({'id': color_id, 'name': color_name})

    if not color_list:
        return render_template_string(RESULT_TEMPLATE, content="<p>❌ কোনো রঙের তালিকা পাওয়া যায়নি।</p>")

    return render_template_string(COLOR_SELECTION_TEMPLATE, colors=color_list, ref_number=ref_number, line_number=line_number)

@app.route('/generate-report', methods=['POST'])
def generate_report():
    ref_number = request.form['ref_number']
    line_number = request.form['line_number']
    selected_color_id = request.form['color_id']
    
    # মূল ফাংশন কল করে রিপোর্ট তৈরি
    report_html = fetch_report_data(ref_number, line_number, selected_color_id)
    
    return render_template_string(RESULT_TEMPLATE, content=report_html)

if __name__ == '__main__':
    app.run(debug=True)
