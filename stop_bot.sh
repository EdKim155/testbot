#!/bin/bash

# Stop Telegram HeyGen Bot

cd "/Users/edgark/for gen/testbot"

echo "🛑 Останавливаю бот..."

# Kill all bot processes
pkill -9 -f "python -m bot.main"

# Remove PID file if exists
if [ -f bot.pid ]; then
    rm bot.pid
fi

sleep 1

# Verify all processes are killed
if pgrep -f "python -m bot.main" > /dev/null; then
    echo "⚠️  Некоторые процессы еще работают. Пробую снова..."
    pkill -9 -f "python -m bot.main"
    sleep 1
fi

if ! pgrep -f "python -m bot.main" > /dev/null; then
    echo "✅ Бот остановлен"
else
    echo "❌ Не удалось остановить бот. Попробуйте вручную: pkill -9 -f 'python -m bot.main'"
    exit 1
fi
