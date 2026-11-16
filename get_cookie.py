import pickle, os, time
from selenium import webdriver
os.makedirs('cookies', exist_ok=True)
driver = webdriver.Chrome()
driver.get("http://www.facebook.com")
print("👉 Đăng nhập Facebook thủ công trên cửa sổ vừa mở.")
input("Sau khi đăng nhập xong, nhấn Enter tại đây...")
with open("cookies/facebook_cookies.pkl", "wb") as f:
    pickle.dump(driver.get_cookies(), f)
print("✅ Đã lưu cookie vào cookies/facebook_cookies.pkl")
driver.quit()