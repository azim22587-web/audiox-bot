#!/bin/bash
# ==============================================================================
# Audoix Bot - Ubuntu/Debian Server Avtomatik O'rnatish Skripti
# ==============================================================================

set -e

echo "🚀 Server yangilanmoqda va kerakli paketlar o'rnatilmoqda..."
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv ffmpeg git curl

echo "📦 Python virtual muhit (venv) yaratilmoqda..."
python3 -m venv venv
source venv/bin/activate

echo "📥 Bog'liqliklar o'rnatilmoqda..."
pip install --upgrade pip
pip install -r requirements.txt

echo "⚙️ Systemd servisi yaratilmoqda..."
CURRENT_DIR=$(pwd)
CURRENT_USER=$(whoami)

sudo bash -c "cat > /etc/systemd/system/audoix.service" <<EOL
[Unit]
Description=Audoix Telegram Music & Media Bot
After=network.target

[Service]
Type=simple
User=${CURRENT_USER}
WorkingDirectory=${CURRENT_DIR}
ExecStart=${CURRENT_DIR}/venv/bin/python ${CURRENT_DIR}/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOL

echo "🔄 Servis ishga tushirilmoqda..."
sudo systemctl daemon-reload
sudo systemctl enable audoix
sudo systemctl restart audoix

echo "=============================================================================="
echo "✅ Audoix Bot serverda muvaffaqiyatli ishga tushdi va 24/7 avtomatik ishlaydi!"
echo "Holatni tekshirish uchun: sudo systemctl status audoix"
echo "Loglarni jonli ko'rish uchun: sudo journalctl -u audoix -f"
echo "=============================================================================="
