
# 🤖 FB Auto Post & Media Tool

Một công cụ tự động hóa mạnh mẽ được viết bằng Python, giúp bạn dễ dàng quản lý, xử lý video/âm thanh và tự động đăng bài lên Facebook, YouTube.

## ✨ Tính năng chính

- **Tự động đăng bài Facebook:**
  - Hỗ trợ đăng bài lên Trang cá nhân (Profile).
  - Đính kèm ảnh, video.
  - Hẹn giờ (lên lịch) tự động đăng bài.
  - Sử dụng Cookie để duy trì đăng nhập an toàn, giảm rủi ro checkpoint.
- **Xử lý Media (Tích hợp FFmpeg):**
  - Cắt, ghép video và âm thanh.
  - Tải video/âm thanh từ các nền tảng (thông qua yt-dlp).
  - Xử lý hàng loạt file với tốc độ cao.
- **Tự động hóa YouTube:**
  - Tự động upload video lên YouTube.
  - Hỗ trợ đặt lịch đăng (Schedule) và cài đặt chế độ hiển thị (Public/Private/Unlisted).

## 🛠️ Yêu cầu hệ thống

- **Python:** Phiên bản 3.10 trở lên (Khuyến nghị 3.11+).
- **Trình duyệt:** Google Chrome (phiên bản mới nhất).
- **FFmpeg:** Bắt buộc phải cài đặt (dùng để xử lý video/âm thanh).

## 🚀 Hướng dẫn cài đặt

### 1. Cài đặt FFmpeg (Bắt buộc)
- **Windows:** Mở PowerShell (quyền Admin) và chạy lệnh:
  ```bash
  winget install Gyan.FFmpeg
  ```
  *(Khởi động lại máy hoặc mở lại Terminal sau khi cài xong).*
- **MacOS:** `brew install ffmpeg`
- **Ubuntu:** `sudo apt install ffmpeg`

### 2. Clone dự án và cài đặt thư viện
```bash
# 1. Clone dự án
git clone https://github.com/Doha1610/fb-auto-post.git
cd fb-auto-post

# 2. Tạo môi trường ảo (venv)
python -m venv venv

# 3. Kích hoạt môi trường ảo
# Windows:
.\venv\Scripts\Activate.ps1
# Mac/Linux:
source venv/bin/activate

# 4. Cài đặt các thư viện phụ thuộc
pip install -r requirements.txt
```

### 3. Cấu hình biến môi trường (Tùy chọn)
Nếu bạn có sử dụng Proxy/VPN để đăng bài YouTube, hãy thêm cấu hình vào file `.env` hoặc trực tiếp trong code:
```env
HTTP_PROXY=http://127.0.0.1:7890
HTTPS_PROXY=http://127.0.0.1:7890
```

## 💻 Cách sử dụng

### Bước 1: Lấy Cookie Facebook (Chỉ làm 1 lần)
Để tool có thể đăng bài thay bạn mà không cần nhập mật khẩu mỗi lần, bạn cần lấy Cookie:
```bash
python get_cookie.py
```
*Một cửa sổ Chrome sẽ hiện lên. Bạn đăng nhập Facebook thủ công, sau đó quay lại Terminal nhấn `Enter`. File cookie sẽ được lưu vào thư mục `cookies/`.*

### Bước 2: Khởi chạy Server
```bash
python run.py
```

### Bước 3: Sử dụng giao diện Web
Mở trình duyệt và truy cập: **`http://127.0.0.1:5000`**

- **Tab Đăng bài:** Nhập nội dung, chọn ảnh và chọn giờ để đặt lịch đăng.
- **Tab Media:** Tải lên video/âm thanh để cắt ghép.
- **Tab YouTube:** Chọn video đã xử lý, nhập tiêu đề và bấm Upload.

## ⚠️ Lưu ý quan trọng
1. **Rủi ro tài khoản:** Việc sử dụng công cụ tự động hóa (Selenium) để đăng bài lên Facebook cá nhân có thể vi phạm điều khoản dịch vụ của Meta. Hãy sử dụng với tần suất vừa phải (1-2 bài/ngày) để tránh bị khóa tài khoản.
2. **Dung lượng file:** Không nên upload các file media quá lớn (trên 500MB) qua giao diện web để tránh lỗi `Timeout`. Hãy xử lý video nhỏ trước khi tải lên.

## 📝 Giấy phép
Dự án này được phát triển cho mục đích cá nhân. Vui lòng không sử dụng cho các mục đích vi phạm pháp luật hoặc spam.

