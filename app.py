import os, pickle, time
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('cookies', exist_ok=True)

scheduler = BackgroundScheduler()
scheduler.start()

def post_to_facebook(content, image_path=None):
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    # KHÔNG dùng headless

    driver = webdriver.Chrome(options=options)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )

    try:
        driver.get("https://www.facebook.com")
        time.sleep(3)

        cookie_file = "cookies/facebook_cookies.pkl"
        if not os.path.exists(cookie_file):
            raise Exception("Chưa có cookie. Chạy get_cookie.py trước.")

        with open(cookie_file, "rb") as f:
            cookies = pickle.load(f)
        for c in cookies:
            c['domain'] = '.facebook.com'
            try:
                driver.add_cookie(c)
            except Exception:
                pass

        driver.refresh()
        time.sleep(5)

        wait = WebDriverWait(driver, 25)

        # Mở hộp thoại tạo bài viết
        box = wait.until(EC.element_to_be_clickable(
            (By.XPATH,
             "//div[@aria-label='Bạn đang nghĩ gì vậy?'] "
             "| //div[contains(@aria-label,'nghĩ gì')] "
             "| //div[contains(@aria-label,\"What's on your mind\")]")
        ))
        box.click()
        time.sleep(3)

        # Nhập nội dung
        editor = wait.until(EC.presence_of_element_located(
            (By.XPATH, "//div[@role='dialog']//div[@contenteditable='true']")
        ))
        editor.click()
        editor.send_keys(content)
        time.sleep(2)

        # Tải ảnh
        if image_path and os.path.exists(image_path):
            file_input = driver.find_element(By.XPATH, "//input[@type='file']")
            file_input.send_keys(os.path.abspath(image_path))
            time.sleep(6)

        # Bấm Đăng
        post_btn = wait.until(EC.element_to_be_clickable(
            (By.XPATH,
             "//div[@role='dialog']//div[@aria-label='Đăng' or @aria-label='Post']")
        ))
        post_btn.click()
        time.sleep(8)

        return True, "Đăng thành công"
    except Exception as e:
        return False, str(e)
    finally:
        driver.quit()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/schedule', methods=['POST'])
def schedule_post():
    content = request.form.get('content', '').strip()
    schedule_time = request.form.get('schedule_time')
    image = request.files.get('image')

    if not content:
        return jsonify({"ok": False, "msg": "Nội dung trống"}), 400
    if not schedule_time:
        return jsonify({"ok": False, "msg": "Chưa chọn thời gian"}), 400

    image_path = None
    if image and image.filename:
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], image.filename)
        image.save(image_path)

    try:
        run_time = datetime.fromisoformat(schedule_time)
    except ValueError:
        return jsonify({"ok": False, "msg": "Thời gian không hợp lệ"}), 400

    def job():
        ok, msg = post_to_facebook(content, image_path)
        print(f"[{datetime.now()}] {'✅' if ok else '❌'} {msg}")

    scheduler.add_job(job, 'date', run_date=run_time, id=f"post_{time.time()}")
    return jsonify({"ok": True, "msg": f"Đã lên lịch lúc {run_time.strftime('%H:%M %d/%m/%Y')}"})

if __name__ == '__main__':
    app.run(debug=True, port=5000)