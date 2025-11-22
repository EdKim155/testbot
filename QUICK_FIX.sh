#!/bin/bash
# Quick fix script to reset bot and clear all caches

echo "🔄 Останавливаем бот..."
# Kill any running bot processes
pkill -f "python.*bot.main" || true
sleep 2

echo "🗑️  Очищаем Python кэш..."
# Remove all .pyc files and __pycache__ directories
find . -type f -name "*.pyc" -delete
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

echo "💾 Удаляем старую базу данных..."
# Remove old database
rm -f bot.db

echo "✅ Всё готово! Теперь запустите бота:"
echo ""
echo "    python -m bot.main"
echo ""
echo "или в Cursor просто нажмите Run"
