#!/bin/bash

# Check Telegram HeyGen Bot status

cd "/Users/edgark/for gen/testbot"

echo "📊 Статус бота:"
echo "─────────────────────────────────────"

if pgrep -f "python -m bot.main" > /dev/null; then
    echo "✅ Бот ЗАПУЩЕН"
    echo ""
    echo "Процессы:"
    ps aux | grep "[p]ython -m bot.main" | awk '{print "  PID: "$2"  CPU: "$3"%  MEM: "$4"%"}'
    echo ""
    echo "📋 Последние 10 строк логов:"
    echo "─────────────────────────────────────"
    tail -10 bot.log
else
    echo "❌ Бот ОСТАНОВЛЕН"
fi

echo "─────────────────────────────────────"
