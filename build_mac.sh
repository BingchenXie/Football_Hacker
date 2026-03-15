#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "=== Football Hacker — Mac 打包 ==="

# 检查必要文件
if [ ! -f "football.db" ]; then
    echo "错误：找不到 football.db，请先运行 build_db.py"
    exit 1
fi

# 清理旧构建
rm -rf build dist

# 运行 PyInstaller
python3 -m PyInstaller football_hacker.spec --noconfirm

echo ""
echo "=== 打包完成 ==="
echo "应用位置：dist/Football Hacker.app"
echo "大小：$(du -sh 'dist/Football Hacker.app' | cut -f1)"

# 用 ditto 打包成 zip（保留 macOS 元数据，避免解压后报损坏）
echo ""
echo "=== 生成发布包 ==="
ditto -c -k --keepParent "dist/Football Hacker.app" "dist/Football_Hacker.zip"
echo "发布包：dist/Football_Hacker.zip"
echo "大小：$(du -sh 'dist/Football_Hacker.zip' | cut -f1)"
echo ""
echo "将 dist/Football_Hacker.zip 发给用户即可。"