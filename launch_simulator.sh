#!/bin/bash
# Script de lancement direct de MyNews AI sur le Simulateur iOS

PROJECT_DIR="/Users/issam/Documents/Projets perso/NewsStreamAI/ios/NewsStreamApp"
DEVICE_NAME="iPhone 17 Pro"
ROOT_DIR="$(cd "$PROJECT_DIR/../.." && pwd)"

# Vérifier et démarrer le backend si inactif
if ! curl -s http://localhost:8000/api/health >/dev/null 2>&1; then
    echo "⚡ Démarrage automatique du backend NewsStreamAI..."
    "$ROOT_DIR/start_newsstream.sh"
fi

echo "🔨 Compilation de MyNews AI pour le simulateur..."
xcodebuild -project "$PROJECT_DIR/MyNewsAI.xcodeproj" -scheme MyNewsAI -destination "platform=iOS Simulator,name=$DEVICE_NAME" -derivedDataPath "$PROJECT_DIR/build" build -quiet

echo "📱 Lancement du Simulateur iOS ($DEVICE_NAME)..."
open -a Simulator
xcrun simctl boot "$DEVICE_NAME" 2>/dev/null || true

APP_PATH=$(find "$PROJECT_DIR/build/Build/Products/Debug-iphonesimulator" -name "MyNewsAI.app" | head -n 1)

if [ -n "$APP_PATH" ]; then
    echo "📲 Installation et ouverture de MyNews AI..."
    xcrun simctl install booted "$APP_PATH"
    xcrun simctl launch booted "com.issam.mynewsai.news"
    echo "✨ MyNews AI est en cours d'exécution sur le Simulateur !"
fi
