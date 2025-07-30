import requests
import json
from bs4 import BeautifulSoup
from flask import Flask, request, render_template_string

app = Flask(__name__)

# --- Step 0: Function for automatic login ---
def perform_login():
    """Logs into the ERP system and returns a session object."""
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
            return None, "Login failed. Please check if the username or password is correct."
        return session, "Login successful."
    except requests.exceptions.RequestException as e:
        return None, f"Error during login: {e}"

# --- Core logic that now accepts parameters ---
def fetch_report_data(ref_number, line_number, selected_color_id):
    """Generates the final report based on the provided inputs."""
    session, login_message = perform_login()
    if not session:
        return f"<p>{login_message}</p>"

    # Step 1: First API
    api1_url = "https://logic-job-no.onrender.com/get_info"
    params1 = {'ref': ref_number}
    response1 = session.get(api1_url, params=params1, timeout=30)
    data1 = response1.json()
    job_no = data1.get("job_no")
    company_id = data1.get("company_id")
    if not all([job_no, company_id]):
        return "<p>Error: 'job_no' or 'company_id' not found from the first API.</p>"
    last_five_digits = job_no[-5:]

    # Step 2: Second API
    api2_base_url = "http://180.92.235.190:8022/erp/production/reports/requires/bundle_wise_sewing_tracking_report_controller.php"
    params2 = {'data': f"{company_id}**0**1**{last_five_digits}**0", 'action': 'search_list_view'}
    response2 = session.get(api2_base_url, params=params2, timeout=120)
    soup = BeautifulSoup(response2.text, 'html.parser')
    first_row = soup.find('table', id='tbl_list_search').find('tbody').find('tr')
    txt_job_id = first_row.get('onclick').split("'")[1].split('_')[1]

    # Step 4: Generate final report
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
        return "<p>No data found in the report.</p>"

    # NEW: Vertical card layout for results
    results_html = '<div class="report-grid">'
    overall_results_found = False
    for row in report_rows:
        cells = row.find_all('td')
        if len(cells) >= 24:
            status_col_18 = cells[18].get_text(strip=True)
            line_no_col_22 = cells[21].get_text(strip=True)
            
            if status_col_18 == 'No' and line_no_col_22 == line_number:
                overall_results_found = True
                sl_no = cells[0].get_text(strip=True)
                barcode_value = cells[1].get_text(strip=True)
                size_value = cells[3].get_text(strip=True)
                bundle_qty = cells[22].get_text(strip=True)
                input_date = cells[16].get_text(strip=True)

                results_html += '<div class="report-card-group">'
                results_html += f'<div class="report-item-card"><div class="report-label">SL No</div><div class="report-value">{sl_no}</div></div>'
                results_html += f'<div class="report-item-card"><div class="report-label">Barcode No</div><div class="report-value" style="font-size: 1.1em; font-weight: bold;">{barcode_value}</div></div>'
                results_html += f'<div class="report-item-card"><div class="report-label">Size</div><div class="report-value">{size_value}</div></div>'
                results_html += f'<div class="report-item-card"><div class="report-label">Bundle Qty</div><div class="report-value">{bundle_qty}</div></div>'
                results_html += f'<div class="report-item-card"><div class="report-label">Input Date</div><div class="report-value">{input_date}</div></div>'
                results_html += '</div>'


    results_html += '</div>'

    if not overall_results_found:
        return f"<p>No 'No' status found for this color on line '{line_number}'.</p>"
    
    return results_html

# --- HTML Templates for web pages ---

# First page: For getting ref number input
INPUT_PAGE_TEMPLATE = """
<!doctype html>
<html>
<head>
<title>Report Generator</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #ffffff; margin: 0; padding: 15px; }
    .form-container { max-width: 400px; margin: 0 auto; }
    .form-container h1 { font-size: 24px; color: #2c3e50; text-align: center; margin-bottom: 20px; }
    label { display: block; font-weight: 600; color: #34495e; margin-bottom: 8px; }
    input[type="text"] { width: 100%; padding: 12px 15px; font-size: 16px; border: 1px solid #bdc3c7; border-radius: 8px; box-sizing: border-box; margin-bottom: 20px; transition: border-color 0.3s, box-shadow 0.3s; }
    input[type="text"]:focus { outline: none; border-color: #3498db; box-shadow: 0 0 8px rgba(52, 152, 219, 0.25); }
    input[type="submit"] { width: 100%; padding: 12px 15px; font-size: 16px; font-weight: 700; color: #ffffff; background: linear-gradient(to right, #3498db, #2980b9); border: none; border-radius: 8px; cursor: pointer; transition: transform 0.2s, box-shadow 0.2s; box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1); }
    input[type="submit"]:hover { transform: translateY(-2px); box-shadow: 0 6px 15px rgba(0, 0, 0, 0.15); }
    /* NEW: Loader Styles */
    #loader-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background-color: rgba(255, 255, 255, 0.8); z-index: 9999; display: none; justify-content: center; align-items: center; }
    .loader { border: 8px solid #f3f3f3; border-top: 8px solid #3498db; border-radius: 50%; width: 60px; height: 60px; animation: spin 1s linear infinite; }
    @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
</style>
</head>
<body>
    <div id="loader-overlay"><div class="loader"></div></div>

    <div class="form-container">
        <h1>Final Report Generator</h1>
        <form action="/get-colors" method="post">
            <label for="ref_number">Please provide the ref number for API 1:</label>
            <input type="text" id="ref_number" name="ref_number" required>
            
            <label for="line_number">Please provide the line number:</label>
            <input type="text" id="line_number" name="line_number" required>
            
            <input type="submit" value="Get Color List">
        </form>
    </div>
    <script>
        document.querySelector('form').addEventListener('submit', function() {
            document.getElementById('loader-overlay').style.display = 'flex';
        });
    </script>
</body>
</html>
"""

# Second page: For selecting a color
COLOR_SELECTION_TEMPLATE = """
<!doctype html>
<html>
<head>
<title>Select Color</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #ffffff; margin: 0; padding: 15px; }
    .form-container { max-width: 400px; margin: 0 auto; }
    .form-container h1 { font-size: 24px; color: #2c3e50; text-align: center; margin-bottom: 20px; }
    label { display: block; font-weight: 600; color: #34495e; margin-bottom: 8px; }
    select { width: 100%; padding: 12px 15px; font-size: 16px; border: 1px solid #bdc3c7; border-radius: 8px; box-sizing: border-box; margin-bottom: 20px; -webkit-appearance: none; -moz-appearance: none; appearance: none; background-image: url('data:image/svg+xml;charset=US-ASCII,%3Csvg%20xmlns%3D%22http%3A//www.w3.org/2000/svg%22%20width%3D%22292.4%22%20height%3D%22292.4%22%3E%3Cpath%20fill%3D%22%2334495e%22%20d%3D%22M287%2069.4a17.6%2017.6%200%200%200-13-5.4H18.4c-5%200-9.3%201.8-12.9%205.4A17.6%2017.6%200%200%200%200%2082.2c0%205%201.8%209.3%205.4%2012.9l128%20127.9c3.6%203.6%207.8%205.4%2012.8%205.4s9.2-1.8%2012.8-5.4L287%2095c3.5-3.5%205.4-7.8%205.4-12.8%200-5-1.9-9.2-5.5-12.8z%22/%3E%3C/svg%3E'); background-repeat: no-repeat; background-position: right 15px top 50%; background-size: .65em auto; }
    select:focus { outline: none; border-color: #3498db; box-shadow: 0 0 8px rgba(52, 152, 219, 0.25); }
    input[type="submit"] { width: 100%; padding: 12px 15px; font-size: 16px; font-weight: 700; color: #ffffff; background: linear-gradient(to right, #27ae60, #229954); border: none; border-radius: 8px; cursor: pointer; transition: transform 0.2s, box-shadow 0.2s; box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1); }
    input[type="submit"]:hover { transform: translateY(-2px); box-shadow: 0 6px 15px rgba(0, 0, 0, 0.15); }
    a { display: block; text-align: center; margin-top: 20px; color: #3498db; text-decoration: none; }
    /* NEW: Loader Styles */
    #loader-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background-color: rgba(255, 255, 255, 0.8); z-index: 9999; display: none; justify-content: center; align-items: center; }
    .loader { border: 8px solid #f3f3f3; border-top: 8px solid #27ae60; border-radius: 50%; width: 60px; height: 60px; animation: spin 1s linear infinite; }
    @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
</style>
</head>
<body>
    <div id="loader-overlay"><div class="loader"></div></div>

    <div class="form-container">
        <h1>Select a Color</h1>
        <form action="/generate-report" method="post">
            <input type="hidden" name="ref_number" value="{{ ref_number }}">
            <input type="hidden" name="line_number" value="{{ line_number }}">
            
            <label for="color_id">Color:</label>
            <select name="color_id" id="color_id">
                {% for color in colors %}
                <option value="{{ color.id }}">{{ color.name }}</option>
                {% endfor %}
            </select>
            
            <input type="submit" value="Generate Report">
        </form>
        <a href="/">Go Back</a>
    </div>
    <script>
        document.querySelector('form').addEventListener('submit', function() {
            document.getElementById('loader-overlay').style.display = 'flex';
        });
    </script>
</body>
</html>
"""

# Page for displaying results
RESULT_TEMPLATE = """
<!doctype html>
<html>
<head>
<title>Report Result</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #ffffff; margin: 0; padding: 15px; }
    .result-container { max-width: 800px; margin: 0 auto; padding: 20px; border: 1px solid #eee; border-radius: 8px; }
    .result-container h1 { font-size: 24px; color: #2c3e50; text-align: center; margin-bottom: 20px; }
    /* NEW: Result Card Styles */
    .report-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px; }
    .report-card-group { border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
    .report-item-card { padding: 10px 15px; border-bottom: 1px solid #eee; }
    .report-card-group .report-item-card:last-child { border-bottom: none; }
    .report-label { font-size: 12px; color: #7f8c8d; text-transform: uppercase; margin-bottom: 4px; }
    .report-value { font-size: 18px; color: #2c3e50; font-weight: 500; }

    .action-buttons { margin-top: 25px; display: flex; justify-content: center; gap: 15px; }
    .action-buttons a, .action-buttons button { display: inline-block; text-align: center; color: #ffffff; text-decoration: none; font-weight: 600; padding: 10px 20px; border-radius: 8px; border: none; cursor: pointer; transition: transform 0.2s; }
    .try-again-link { background-color: #3498db; }
    .print-button { background-color: #9b59b6; }
    .action-buttons a:hover, .action-buttons button:hover { transform: translateY(-2px); }
    /* Print Specific Styles */
    @media print {
        body, .result-container { border: none; box-shadow: none; }
        .action-buttons { display: none; }
        .report-grid { grid-template-columns: 1fr; } /* Stack cards vertically for printing */
    }
</style>
</head>
<body>
    <div class="result-container" id="result-page">
        <h1>Report (Filtered)</h1>
        <div id="printable-area">
            {{ content | safe }}
        </div>
        <div class="action-buttons">
            <a href="/" class="try-again-link">Try Again</a>
            <button onclick="window.print()" class="print-button">&#128424;&#65039; Print</button>
        </div>
    </div>
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
        return render_template_string(RESULT_TEMPLATE, content=f"<p>{login_message}</p>")

    # Collect information from API 1 and 2
    try:
        api1_url = "https://logic-job-no.onrender.com/get_info"
        params1 = {'ref': ref_number}
        response1 = session.get(api1_url, params=params1, timeout=30)
        response1.raise_for_status()
        data1 = response1.json()
        job_no = data1.get("job_no")
        company_id = data1.get("company_id")
        last_five_digits = job_no[-5:]

        api2_base_url = "http://180.92.235.190:8022/erp/production/reports/requires/bundle_wise_sewing_tracking_report_controller.php"
        params2 = {'data': f"{company_id}**0**1**{last_five_digits}**0", 'action': 'search_list_view'}
        response2 = session.get(api2_base_url, params=params2, timeout=120)
        response2.raise_for_status()
        soup = BeautifulSoup(response2.text, 'html.parser')
        first_row = soup.find('table', id='tbl_list_search').find('tbody').find('tr')
        txt_job_id = first_row.get('onclick').split("'")[1].split('_')[1]

        # Get color list
        params3 = {'action': 'color_popup', 'txt_job_no': job_no, 'txt_job_id': txt_job_id}
        response3 = session.get(api2_base_url, params=params3, timeout=120)
        response3.raise_for_status()
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
            return render_template_string(RESULT_TEMPLATE, content="<p>No color list found.</p>")

        return render_template_string(COLOR_SELECTION_TEMPLATE, colors=color_list, ref_number=ref_number, line_number=line_number)

    except requests.exceptions.RequestException as e:
        return render_template_string(RESULT_TEMPLATE, content=f"<p>An error occurred while fetching data: {e}</p>")
    except (AttributeError, IndexError) as e:
        return render_template_string(RESULT_TEMPLATE, content=f"<p>Could not parse the required data from the source page. The site's structure may have changed. Error: {e}</p>")


@app.route('/generate-report', methods=['POST'])
def generate_report():
    ref_number = request.form['ref_number']
    line_number = request.form['line_number']
    selected_color_id = request.form['color_id']
    
    # Call the main function to generate the report
    try:
        report_html = fetch_report_data(ref_number, line_number, selected_color_id)
        return render_template_string(RESULT_TEMPLATE, content=report_html)
    except requests.exceptions.RequestException as e:
        return render_template_string(RESULT_TEMPLATE, content=f"<p>An error occurred while generating the report: {e}</p>")
    except (AttributeError, IndexError) as e:
        return render_template_string(RESULT_TEMPLATE, content=f"<p>Could not parse the report data. The report's structure may have changed. Error: {e}</p>")


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=True)
