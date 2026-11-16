const contentEl = document.getElementById('content');
const imageEl = document.getElementById('image');
const scheduleEl = document.getElementById('schedule_time');
const submitBtn = document.getElementById('submitBtn');
const statusEl = document.getElementById('status');
const previewEl = document.getElementById('preview');

// Xem trước ảnh
imageEl.addEventListener('change', () => {
  previewEl.innerHTML = '';
  const file = imageEl.files[0];
  if (file) {
    const img = document.createElement('img');
    img.src = URL.createObjectURL(file);
    previewEl.appendChild(img);
  }
});

// Gợi ý thời gian mặc định: 5 phút sau
(function setDefaultTime() {
  const now = new Date(Date.now() + 5 * 60 * 1000);
  now.setSeconds(0, 0);
  const pad = (n) => String(n).padStart(2, '0');
  scheduleEl.value =
    `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}` +
    `T${pad(now.getHours())}:${pad(now.getMinutes())}`;
})();

submitBtn.addEventListener('click', async () => {
  const content = contentEl.value.trim();
  const image = imageEl.files[0];
  const scheduleTime = scheduleEl.value;

  if (!content || !scheduleTime) {
    statusEl.textContent = '⚠️ Vui lòng nhập nội dung và thời gian';
    statusEl.style.color = '#d97706';
    return;
  }

  const formData = new FormData();
  formData.append('content', content);
  formData.append('schedule_time', scheduleTime);
  if (image) formData.append('image', image);

  submitBtn.disabled = true;
  statusEl.textContent = '⏳ Đang gửi...';
  statusEl.style.color = '#555';

  try {
    const res = await fetch('/schedule', { method: 'POST', body: formData });
    const data = await res.json();
    statusEl.textContent = data.ok ? '✅ ' + data.msg : '❌ ' + data.msg;
    statusEl.style.color = data.ok ? '#16a34a' : '#dc2626';
  } catch (e) {
    statusEl.textContent = '❌ Không kết nối được backend';
    statusEl.style.color = '#dc2626';
  } finally {
    submitBtn.disabled = false;
  }
});