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
        return f"<p>No 'No' status found for this color on line '{line_number}'.</p>"
    
    return results_html

# --- HTML Templates for web pages ---
# First page: For getting ref number input
INPUT_PAGE_TEMPLATE = """
<!doctype html>
<html>
<head><title>Report Generator</title></head>
<body>
    <h1>Final Report Generator</h1>
    <form action="/get-colors" method="post">
        <label for="ref_number">Please provide the ref number for API 1:</label><br>
        <input type="text" id="ref_number" name="ref_number" required><br><br>
        <label for="line_number">Please provide the line number:</label><br>
        <input type="text" id="line_number" name="line_number" required><br><br>
        <input type="submit" value="Get Color List">
    </form>
</body>
</html>
"""

# Second page: For selecting a color
COLOR_SELECTION_TEMPLATE = """
<!doctype html>
<html>
<head><title>Select Color</title></head>
<body>
    <h1>Please select a color</h1>
    <form action="/generate-report" method="post">
        <input type="hidden" name="ref_number" value="{{ ref_number }}">
        <input type="hidden" name="line_number" value="{{ line_number }}">
        
        <label for="color_id">Color:</label>
        <select name="color_id" id="color_id">
            {% for color in colors %}
            <option value="{{ color.id }}">{{ color.name }}</option>
            {% endfor %}
        </select>
        <br><br>
        <input type="submit" value="Generate Report">
    </form>
    <br>
    <a href="/">Go Back</a>
</body>
</html>
"""

# Page for displaying results
RESULT_TEMPLATE = """
<!doctype html>
<html>
<head><title>Report Result</title></head>
<body>
    <h1>Report (Filtered)</h1>
    <div>{{ content | safe }}</div>
    <br>
    <a href="/">Try Again</a>
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
    app.run(debug=True)
