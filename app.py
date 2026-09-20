import os
import tempfile
import io
from flask import Flask, request, render_template, send_file
from services.excel_reader import read_bank_file, read_accounting_file
from services.matcher import match_transactions
from services.excel_exporter import export_results

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024 # 50MB

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        bank_file = request.files.get('bank_file')
        acc_file = request.files.get('acc_file')

        if not bank_file or not acc_file:
            return "Vui lòng upload đầy đủ file ngân hàng và file kế toán.", 400

        # Khởi tạo bộ nhớ đệm để lưu file
        mem = io.BytesIO()

        with tempfile.TemporaryDirectory() as temp_dir:
            bank_path = os.path.join(temp_dir, bank_file.filename)
            acc_path = os.path.join(temp_dir, acc_file.filename)
            
            bank_file.save(bank_path)
            acc_file.save(acc_path)

            try:
                # 1. Đọc và chuẩn hóa dữ liệu
                df_bank = read_bank_file(bank_path)
                df_acc = read_accounting_file(acc_path)
                
                # 2. Đối chiếu
                matched_groups, unmatched_bank, unmatched_acc = match_transactions(df_bank, df_acc)
                
                # 3. Xuất kết quả ra ổ cứng tạm
                output_path = os.path.join(temp_dir, 'DoiChieuKeToan_KetQua.xlsx')
                export_results(matched_groups, unmatched_bank, unmatched_acc, output_path)

                # 4. Đọc file từ ổ cứng lên RAM trước khi thư mục bị xóa
                with open(output_path, 'rb') as f:
                    mem.write(f.read())
                mem.seek(0) # Đưa con trỏ về đầu file để Flask có thể đọc
                
            except Exception as e:
                return f"Lỗi xử lý: {str(e)}", 400

        # Lúc này vòng lặp with đã kết thúc, thư mục tạm trên ổ cứng đã được xóa an toàn
        # Ta gửi file về trình duyệt từ bộ nhớ RAM
        return send_file(
            mem,
            as_attachment=True,
            download_name='DoiChieuKeToan_KetQua.xlsx',
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000)