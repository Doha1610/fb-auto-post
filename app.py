import logging
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, render_template, request
from werkzeug.utils import secure_filename

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    WebDriverException,
    ElementClickInterceptedException,
)

# ============================================================
# 1. CẤU HÌNH
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
LOG_DIR = BASE_DIR / "logs"
PROFILE_DIR = BASE_DIR / "chrome_profile"
DB_PATH = BASE_DIR / "facebook_jobs.sqlite3"

for folder in (UPLOAD_DIR, LOG_DIR, PROFILE_DIR):
    folder.mkdir(parents=True, exist_ok=True)

TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_IMAGE_SIZE = 15 * 1024 * 1024
POLL_INTERVAL_SECONDS = 2
BROWSER_LOCK = threading.Lock()

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "facebook.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("facebook_auto_post")

stop_event = threading.Event()
scheduler_thread = None


# ============================================================
# 2. SQLITE - LƯU LỊCH KHÔNG BỊ MẤT KHI KHỞI ĐỘNG LẠI
# ============================================================

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                image_path TEXT,
                run_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                message TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_posts_status_run_at
            ON posts(status, run_at)
        """)
        conn.commit()


def update_post(post_id, status, message=None):
    now = datetime.now(TIMEZONE).isoformat()
    with get_db() as conn:
        conn.execute(
            """
            UPDATE posts
            SET status = ?, message = ?, finished_at = ?
            WHERE id = ?
            """,
            (status, message, now, post_id),
        )
        conn.commit()


def get_post(post_id):
    with get_db() as conn:
        return conn.execute(
            "SELECT * FROM posts WHERE id = ?", (post_id,)
        ).fetchone()


def get_public_post(row):
    return {
        "id": row["id"],
        "content": row["content"],
        "image": Path(row["image_path"]).name if row["image_path"] else None,
        "run_at": row["run_at"],
        "status": row["status"],
        "message": row["message"],
        "created_at": row["created_at"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
    }


# ============================================================
# 3. KHỞI TẠO CHROME
# ============================================================

def create_driver():
    """
    Dùng đúng Chrome profile đã được đăng nhập bằng get_cookie.py.
    Hãy đóng mọi cửa sổ Chrome đang dùng profile này trước khi chạy tool.
    """
    options = webdriver.ChromeOptions()
    options.add_argument(f"--user-data-dir={PROFILE_DIR}")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-notifications")
    options.add_experimental_option(
        "prefs",
        {"profile.default_content_setting_values.notifications": 2},
    )

    # Không dùng chế độ ẩn danh hoặc kỹ thuật né phát hiện tự động.
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(60)
    return driver


def check_facebook_login(driver):
    driver.get("https://www.facebook.com/")
    wait = WebDriverWait(driver, 35)

    try:
        wait.until(
            lambda d: "facebook.com" in d.current_url.lower()
            and d.execute_script("return document.readyState") == "complete"
        )
    except TimeoutException:
        raise RuntimeError("Facebook tải quá lâu hoặc không truy cập được.")

    time.sleep(3)

    login_inputs = driver.find_elements(
        By.CSS_SELECTOR,
        "input[name='email'], input[name='pass']",
    )
    if login_inputs or "login" in driver.current_url.lower():
        driver.save_screenshot(str(LOG_DIR / "login_required.png"))
        raise RuntimeError(
            "Chrome profile chưa đăng nhập. Hãy chạy get_cookie.py, "
            "đăng nhập thủ công, rồi chạy lại app.py."
        )


# ============================================================
# 4. TÌM NÚT TẠO BÀI VIẾT
# ============================================================

def find_composer(driver):
    wait = WebDriverWait(driver, 25)

    # Facebook có thể đổi câu chữ/DOM theo tài khoản và ngôn ngữ.
    xpaths = [
        "//*[self::div or self::span]"
        "[contains(normalize-space(.), 'đang nghĩ gì thế')]",
        "//*[self::div or self::span]"
        "[contains(normalize-space(.), 'Bạn đang nghĩ gì')]",
        "//*[self::div or self::span]"
        "[contains(normalize-space(.), \"What's on your mind\")]",
        "//*[@aria-label and contains(@aria-label, 'nghĩ gì')]",
        "//*[@aria-label and contains(@aria-label, 'mind')]",
    ]

    end_time = time.time() + 25
    while time.time() < end_time:
        for xpath in xpaths:
            for found in driver.find_elements(By.XPATH, xpath):
                try:
                    if not found.is_displayed():
                        continue

                    # Đi lên phần tử có thể click gần nhất.
                    candidates = driver.execute_script(
                        """
                        let e = arguments[0];
                        let out = [];
                        for (let i = 0; e && i < 5; i++, e = e.parentElement) {
                            out.push(e);
                            if (e.getAttribute('role') === 'button') break;
                        }
                        return out;
                        """,
                        found,
                    )

                    for candidate in candidates:
                        try:
                            if (
                                candidate.is_displayed()
                                and candidate.is_enabled()
                                and (
                                    candidate.get_attribute("role") == "button"
                                    or candidate.tag_name.lower() == "button"
                                )
                            ):
                                driver.execute_script(
                                    "arguments[0].scrollIntoView({block:'center'});",
                                    candidate,
                                )
                                logger.info(
                                    "Tìm thấy nút soạn bài: %s",
                                    candidate.text[:120],
                                )
                                return candidate
                        except WebDriverException:
                            continue
                except WebDriverException:
                    continue

        time.sleep(0.5)

    driver.save_screenshot(str(LOG_DIR / "composer_not_found.png"))
    raise RuntimeError(
        "Không tìm thấy nút tạo bài viết. "
        "Facebook có thể đã thay đổi giao diện. "
        "Ảnh lỗi: logs/composer_not_found.png"
    )


# ============================================================
# 5. MỞ HỘP THOẠI VÀ TÌM Ô NHẬP
# ============================================================

def open_composer(driver):
    composer = find_composer(driver)
    try:
        composer.click()
    except ElementClickInterceptedException:
        # Chỉ thử click chuẩn qua Selenium; không can thiệp lớp bảo vệ Facebook.
        driver.execute_script(
            "arguments[0].scrollIntoView({block:'center'});", composer
        )
        time.sleep(0.5)
        composer.click()

    wait = WebDriverWait(driver, 20)
    return wait.until(
        EC.visibility_of_element_located(
            (By.XPATH, "//div[@role='dialog']")
        )
    )


def find_editor(dialog, driver=None):
    """
    Tìm ô nhập nội dung. Sửa lại để tìm trên toàn bộ trang (driver)
    thay vì chỉ tìm trong dialog.
    """
    # Danh sách các XPath tìm ô nhập liệu
    xpaths = [
        "//div[@contenteditable='true' and @role='textbox']",
        "//div[@contenteditable='true']",
        "//div[@role='dialog']//div[@contenteditable='true']",
        "//textarea"
    ]

    end_time = time.time() + 20
    target = driver if driver else dialog

    while time.time() < end_time:
        for xpath in xpaths:
            try:
                elements = target.find_elements(By.XPATH, xpath)
                for element in elements:
                    try:
                        if element.is_displayed() and element.is_enabled():
                            return element
                    except WebDriverException:
                        continue
            except WebDriverException:
                continue
        time.sleep(0.5)

    if driver is not None:
        try:
            driver.save_screenshot(str(LOG_DIR / "editor_not_found.png"))
        except WebDriverException:
            pass

    raise RuntimeError(
        "Đã mở hộp thoại nhưng không tìm thấy ô nhập nội dung. "
        "Đã lưu ảnh lỗi trong thư mục logs."
    )


# ============================================================
# 6. ĐÍNH KÈM ẢNH
# ============================================================

def attach_image(dialog, image_path):
    image_file = Path(image_path)
    if not image_file.is_file():
        raise RuntimeError(f"Không tìm thấy ảnh: {image_file}")

    inputs = dialog.find_elements(By.CSS_SELECTOR, "input[type='file']")
    if not inputs:
        # Một số phiên bản Facebook đặt input file ngoài phần tử dialog.
        inputs = dialog.parent.find_elements(By.CSS_SELECTOR, "input[type='file']")

    if not inputs:
        raise RuntimeError(
            "Không tìm thấy ô tải ảnh. Hãy kiểm tra giao diện Facebook."
        )

    # Không tìm cách vượt giới hạn loại file hoặc cơ chế bảo vệ của Facebook.
    inputs[0].send_keys(str(image_file.resolve()))
    time.sleep(4)


# ============================================================
# 7. TÌM NÚT ĐĂNG VÀ THỰC HIỆN
# ============================================================

def find_post_button(dialog):
    xpaths = [
        ".//*[@role='button' and @aria-label='Đăng']",
        ".//*[@role='button' and @aria-label='Post']",
        ".//*[@role='button' and normalize-space(.)='Đăng']",
        ".//*[@role='button' and normalize-space(.)='Post']",
        ".//button[normalize-space(.)='Đăng']",
        ".//button[normalize-space(.)='Post']",
    ]

    wait = WebDriverWait(dialog, 20)
    for xpath in xpaths:
        try:
            button = wait.until(
                lambda d: next(
                    (
                        e for e in d.find_elements(By.XPATH, xpath)
                        if e.is_displayed() and e.is_enabled()
                    ),
                    False,
                )
            )
            if button:
                return button
        except TimeoutException:
            continue

    raise RuntimeError(
        "Không tìm thấy nút Đăng. Bài viết vẫn có thể đang nằm trong hộp thoại."
    )


def post_to_facebook(content, image_path=None):
    """
    Đăng một bài lên trang cá nhân đã đăng nhập trong chrome_profile.
    Không retry tự động sau khi đã bấm Đăng để tránh đăng trùng.
    """
    with BROWSER_LOCK:
        driver = None
        clicked_post = False

        try:
            logger.info("Bắt đầu mở Facebook")
            driver = create_driver()
            check_facebook_login(driver)

            logger.info("Đang mở hộp thoại soạn bài")
            dialog = open_composer(driver)
            logger.info("Đã mở hộp thoại soạn bài")

            editor = find_editor(dialog, driver)
            editor.click()
            editor.send_keys(content)
            logger.info("Đã nhập nội dung")

            if image_path:
                attach_image(dialog, image_path)
                logger.info("Đã gửi ảnh vào hộp thoại")

            # Kiểm tra nút trước khi bấm.
            post_button = find_post_button(dialog)
            logger.info("Đã tìm thấy nút Đăng")

            # Chỉ bấm một lần; không tự động thử lại nếu kết quả không rõ.
            post_button.click()
            clicked_post = True
            logger.info("Đã bấm Đăng; đang chờ Facebook xử lý")

            WebDriverWait(driver, 45).until(
                EC.invisibility_of_element_located(
                    (By.XPATH, "//div[@role='dialog']")
                )
            )

            time.sleep(3)
            logger.info("Hộp thoại đã đóng sau thao tác đăng")
            return True, (
                "Đã bấm Đăng và hộp thoại đã đóng. "
                "Hãy kiểm tra bài viết trên trang cá nhân để xác nhận."
            )

        except Exception as error:
            logger.exception("Lỗi đăng bài: %s", error)

            if driver:
                try:
                    driver.save_screenshot(str(LOG_DIR / "post_error.png"))
                except WebDriverException:
                    pass

            if clicked_post:
                return False, (
                    "Đã bấm Đăng nhưng không xác minh được kết quả. "
                    "Hãy kiểm tra trang cá nhân trước khi tạo lịch đăng lại "
                    "để tránh bài bị trùng."
                )

            return False, str(error)

        finally:
            if driver:
                try:
                    driver.quit()
                except WebDriverException:
                    pass


# ============================================================
# 8. WORKER - TỰ ĐỘNG LẤY LỊCH ĐẾN HẠN
# ============================================================

def claim_due_post():
    """
    Chọn và đánh dấu một lịch đến hạn trong cùng transaction,
    tránh hai worker cùng lấy một bài.
    """
    now = datetime.now(TIMEZONE).isoformat()

    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """
            SELECT * FROM posts
            WHERE status = 'pending' AND run_at <= ?
            ORDER BY run_at ASC
            LIMIT 1
            """,
            (now,),
        ).fetchone()

        if not row:
            conn.commit()
            return None

        started = datetime.now(TIMEZONE).isoformat()
        conn.execute(
            """
            UPDATE posts
            SET status = 'running', started_at = ?, message = ?
            WHERE id = ? AND status = 'pending'
            """,
            (started, "Đang khởi chạy trình duyệt", row["id"]),
        )
        conn.commit()
        return dict(row)


def scheduler_loop():
    logger.info("Scheduler worker đã khởi động")
    while not stop_event.is_set():
        try:
            post = claim_due_post()
            if post:
                post_id = post["id"]
                logger.info("Bắt đầu tác vụ %s", post_id)

                ok, message = post_to_facebook(
                    post["content"],
                    post["image_path"],
                )

                final_status = "success" if ok else "failed"
                update_post(post_id, final_status, message)
                logger.info("%s: %s - %s", post_id, final_status, message)
            else:
                stop_event.wait(POLL_INTERVAL_SECONDS)

        except Exception:
            logger.exception("Lỗi trong scheduler worker")
            stop_event.wait(POLL_INTERVAL_SECONDS)


def start_scheduler_worker():
    global scheduler_thread

    if scheduler_thread and scheduler_thread.is_alive():
        return

    stop_event.clear()
    scheduler_thread = threading.Thread(
        target=scheduler_loop,
        name="facebook-scheduler",
        daemon=True,
    )
    scheduler_thread.start()


# ============================================================
# 9. ROUTES - GIAO DIỆN VÀ TẠO LỊCH
# ============================================================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/schedule", methods=["POST"])
def schedule_post():
    content = request.form.get("content", "").strip()
    schedule_time = request.form.get("schedule_time", "").strip()
    image = request.files.get("image")

    if not content:
        return jsonify({"ok": False, "msg": "Nội dung bài viết đang trống."}), 400

    if not schedule_time:
        return jsonify({"ok": False, "msg": "Bạn chưa chọn thời gian đăng."}), 400

    try:
        run_at = datetime.fromisoformat(schedule_time)
        if run_at.tzinfo is None:
            run_at = run_at.replace(tzinfo=TIMEZONE)
        run_at = run_at.astimezone(TIMEZONE)
    except ValueError:
        return jsonify({"ok": False, "msg": "Thời gian không hợp lệ."}), 400

    if run_at <= datetime.now(TIMEZONE):
        return jsonify({"ok": False, "msg": "Thời gian phải ở tương lai."}), 400

    image_path = None

    if image and image.filename:
        safe_name = secure_filename(image.filename)
        extension = Path(safe_name).suffix.lower()

        if extension not in ALLOWED_EXTENSIONS:
            return jsonify({
                "ok": False,
                "msg": "Chỉ hỗ trợ JPG, JPEG, PNG hoặc WEBP.",
            }), 400

        if image.content_length and image.content_length > MAX_IMAGE_SIZE:
            return jsonify({"ok": False, "msg": "Ảnh vượt quá 15 MB."}), 400

        unique_name = f"{uuid4().hex}{extension}"
        saved_path = UPLOAD_DIR / unique_name
        image.save(saved_path)
        image_path = str(saved_path)

    post_id = f"post_{uuid4().hex}"
    created_at = datetime.now(TIMEZONE).isoformat()

    try:
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO posts
                (id, content, image_path, run_at, status, message, created_at)
                VALUES (?, ?, ?, ?, 'pending', 'Đang chờ đến giờ đăng', ?)
                """,
                (
                    post_id,
                    content,
                    image_path,
                    run_at.isoformat(),
                    created_at,
                ),
            )
            conn.commit()
    except Exception:
        logger.exception("Không lưu được lịch đăng")
        if image_path:
            try:
                Path(image_path).unlink(missing_ok=True)
            except OSError:
                pass
        return jsonify({"ok": False, "msg": "Không thể lưu lịch đăng."}), 500

    return jsonify({
        "ok": True,
        "msg": f"Đã lên lịch lúc {run_at.strftime('%H:%M %d/%m/%Y')}",
        "job_id": post_id,
    })


@app.route("/jobs", methods=["GET"])
def get_jobs():
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT * FROM posts
            ORDER BY
                CASE status
                    WHEN 'pending' THEN 0
                    WHEN 'running' THEN 1
                    ELSE 2
                END,
                run_at ASC
            LIMIT 200
            """
        ).fetchall()

    return jsonify({
        "ok": True,
        "jobs": [get_public_post(row) for row in rows],
    })


@app.route("/jobs/<post_id>", methods=["GET"])
def get_job_detail(post_id):
    row = get_post(post_id)
    if not row:
        return jsonify({"ok": False, "msg": "Không tìm thấy lịch đăng."}), 404
    return jsonify({"ok": True, "job": get_public_post(row)})


@app.route("/jobs/<post_id>/cancel", methods=["POST"])
def cancel_job(post_id):
    row = get_post(post_id)
    if not row:
        return jsonify({"ok": False, "msg": "Không tìm thấy lịch đăng."}), 404

    if row["status"] != "pending":
        return jsonify({
            "ok": False,
            "msg": "Chỉ có thể hủy lịch đang chờ.",
        }), 409

    with get_db() as conn:
        conn.execute(
            """
            UPDATE posts
            SET status = 'cancelled', message = ?, finished_at = ?
            WHERE id = ? AND status = 'pending'
            """,
            (
                "Đã hủy lịch đăng",
                datetime.now(TIMEZONE).isoformat(),
                post_id,
            ),
        )
        conn.commit()

    return jsonify({"ok": True, "msg": "Đã hủy lịch đăng."})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "ok": True,
        "scheduler": "running" if scheduler_thread and scheduler_thread.is_alive() else "stopped",
        "timezone": "Asia/Ho_Chi_Minh",
    })


# ============================================================
# 10. KHỞI ĐỘNG ỨNG DỤNG
# ============================================================

init_db()
start_scheduler_worker()

if __name__ == "__main__":
    print("=" * 58)
    print("FACEBOOK AUTO POST")
    print("=" * 58)
    print("Server: http://127.0.0.1:5000")
    print("Scheduler: ĐANG CHẠY")
    print("Timezone: Asia/Ho_Chi_Minh")
    print(f"Database: {DB_PATH}")
    print("Lưu ý: Không tắt máy hoặc đóng Terminal nếu muốn lịch chạy.")
    print("Đóng các cửa sổ Chrome đang dùng chrome_profile trước khi chạy.")
    print("=" * 58)

    try:
        app.run(
            host="127.0.0.1",
            port=5000,
            debug=False,
            use_reloader=False,
            threaded=True,
        )
    finally:
        stop_event.set()
