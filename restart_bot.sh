#!/bin/bash

# Restart Telegram HeyGen Bot

cd "/Users/edgark/for gen/testbot"

echo "🔄 Перезапускаю бот..."

# Stop bot
./stop_bot.sh

sleep 2

# Start bot
./start_bot.sh
