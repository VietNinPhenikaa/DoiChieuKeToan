import os
import uuid
from flask import Flask, render_template, request, send_file, flash, redirect, url_for
from services.excel_reader import read_and_normalize
from services.matcher import match_transactions
from services.excel_exporter import export_results

app = Flask(__name__)
app.secret_key = 'super_secret_key_for_flash'
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process():
    if 'bank_file' not in request.files or 'acc_file' not in request.files:
        flash('Vui lòng tải lên đầy đủ 2 file.', 'danger')
        return redirect(url_for('index'))
        
    bank_file = request.files['bank_file']
    acc_file = request.files['acc_file']
    
    if bank_file.filename == '' or acc_file.filename == '':
        flash('Chưa chọn file.', 'danger')
        return redirect(url_for('index'))

    # Lưu tạm
    bank_path = os.path.join(UPLOAD_FOLDER, f"bank_{uuid.uuid4().hex}.xlsx")
    acc_path = os.path.join(UPLOAD_FOLDER, f"acc_{uuid.uuid4().hex}.xlsx")
    out_filename = f"KetQuaDoiChieu_{uuid.uuid4().hex}.xlsx"
    out_path = os.path.join(OUTPUT_FOLDER, out_filename)
    
    try:
        bank_file.save(bank_path)
        acc_file.save(acc_path)
        
        # Đọc và đối chiếu
        bank_data = read_and_normalize(bank_path, is_bank=True)
        acc_data = read_and_normalize(acc_path, is_bank=False)
        
        results = match_transactions(bank_data, acc_data)
        
        # Xuất Excel & Thống kê
        summary = export_results(results, len(bank_data), len(acc_data), out_path)
        
        # Dọn file gốc
        os.remove(bank_path)
        os.remove(acc_path)
        
        return render_template('result.html', summary=summary, download_file=out_filename)
        
    except Exception as e:
        flash(f'Lỗi xử lý dữ liệu: {str(e)}', 'danger')
        return redirect(url_for('index'))

@app.route('/download/<filename>')
def download(filename):
    file_path = os.path.join(OUTPUT_FOLDER, filename)
    return send_file(file_path, as_attachment=True, download_name="KetQua_DoiChieu.xlsx")

if __name__ == '__main__':
    app.run(debug=True, port=5000)