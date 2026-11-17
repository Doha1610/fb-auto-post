
from pathlib import Path
from selenium import webdriver

# Lấy thư mục dự án
BASE_DIR = Path(__file__).resolve().parent

# Sử dụng chung Chrome Profile với app.py
PROFILE_DIR = BASE_DIR / "chrome_profile"

PROFILE_DIR.mkdir(exist_ok=True)

options = webdriver.ChromeOptions()

# Lưu phiên đăng nhập Facebook
options.add_argument(
    f"--user-data-dir={PROFILE_DIR}"
)

options.add_argument("--start-maximized")

# Chặn thông báo
prefs = {
    "profile.default_content_setting_values.notifications": 2
}

options.add_experimental_option("prefs", prefs)

driver = webdriver.Chrome(options=options)

try:
    driver.get("https://www.facebook.com/")

    print("=" * 50)
    print("ĐĂNG NHẬP FACEBOOK")
    print("=" * 50)
    print("Hãy đăng nhập Facebook trên Chrome vừa mở.")
    print("Sau khi đăng nhập, quay lại Terminal.")

    input("Nhấn Enter khi đã đăng nhập thành công: ")

    print("Đã lưu phiên đăng nhập trong chrome_profile.")

finally:
    driver.quit()
