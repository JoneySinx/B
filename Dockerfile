# 🐍 Base Image: Python 3.11 Slim (Latest Stable & Lightweight)
FROM python:3.11-slim-bookworm

# 🚀 System Environment Variables (Optimization)
# PYTHONDONTWRITEBYTECODE: .pyc फाइल्स बनने से रोकता है (Disk Space बचाता है)
# PYTHONUNBUFFERED: लॉग्स तुरंत दिखेंगे (Real-time logs)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# 📂 Working Directory
WORKDIR /app

# 🛠️ Install System Dependencies (The God Mode Tools)
# ffmpeg: वीडियो थंबनेल और स्क्रीनशॉट के लिए जरूरी
# mediainfo: वीडियो की डिटेल (Resolution, Duration) निकालने के लिए
# git: अगर requirements.txt में कोई GitHub लिंक है
# gcc: uvloop जैसे फास्ट मॉड्यूल्स को कंपाइल करने के लिए
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    libffi-dev \
    musl-dev \
    ffmpeg \
    mediainfo \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 📦 Install Python Dependencies (Cached Layer)
# इसे पहले कॉपी करते हैं ताकि कोड बदलने पर बार-बार requirements डाउनलोड न हों
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 📂 Copy Project Code
COPY . .

# 🛡️ Permissions (Optional but Good Practice)
# डेटा सेव करने वाले फोल्डर्स को परमिशन दें
RUN chmod 777 /app

# 🌐 Expose Port (Documentation purpose)
EXPOSE 8080

# 🤖 Start Command
# python3 का उपयोग करना ज्यादा सुरक्षित है
CMD ["python3", "bot.py"]
