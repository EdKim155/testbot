#!/bin/bash

# Start Telegram HeyGen Bot

cd "/Users/edgark/for gen/testbot"

# Check if bot is already running
if pgrep -f "python -m bot.main" > /dev/null; then
    echo "❌ Бот уже запущен! Сначала остановите его командой: ./stop_bot.sh"
    exit 1
fi

# Activate virtual environment and start bot
source venv/bin/activate
echo "🚀 Запускаю бот..."
nohup python -m bot.main > bot.log 2>&1 &

# Get PID
BOT_PID=$!
echo $BOT_PID > bot.pid

sleep 2

# Check if bot started successfully
if pgrep -f "python -m bot.main" > /dev/null; then
    echo "✅ Бот успешно запущен (PID: $BOT_PID)"
    echo "📋 Логи: tail -f bot.log"
else
    echo "❌ Ошибка запуска бота. Проверьте логи: cat bot.log"
    exit 1
fi
