#!/bin/bash
# WSL 環境完整安裝腳本
# 在 WSL Ubuntu 中執行

echo "🚀 開始安裝 Agentic RAG WSL 環境..."

# ====== 1. 更新系統套件 ======
echo "📦 更新系統套件..."
sudo apt update && sudo apt upgrade -y

# ====== 2. 安裝基本開發工具 ======
echo "🔨 安裝開發工具..."
sudo apt install -y curl wget git build-essential tmux tree htop

# ====== 3. 安裝 Miniconda ======
echo "🐍 安裝 Miniconda..."
cd /tmp
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh -b -p $HOME/miniconda3
echo 'export PATH="$HOME/miniconda3/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
conda init bash
echo "source ~/.bashrc" >> ~/.bash_profile

# ====== 4. 重新載入 shell 配置 ======
source ~/.bashrc

# ====== 5. 建立 Python 3.12 環境 ======
echo "🏗️ 建立 Python 3.12 環境..."
conda create -n agentic python=3.12 -y
conda activate agentic

# ====== 6. 安裝 Node.js 18+ ======
echo "🟢 安裝 Node.js..."
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# ====== 7. 驗證安裝 ======
echo "✅ 驗證安裝版本..."
python --version
node --version
npm --version
tmux -V

# ====== 8. 建立工作目錄並安裝 Python 依賴 ======
echo "📚 安裝 Python 套件..."
cd /mnt/d/codebase/Agentic-RAG-LLMs-API
pip install -r app_docs/requirements2.txt

# ====== 9. 安裝 UI 依賴 ======
echo "🌐 安裝 UI 套件..."
cd ui && npm install && cd ..

# ====== 10. 建立 tmux session ======
echo "🪟 設定 tmux session..."
tmux new-session -d -s agentic_rag -c '/mnt/d/codebase/Agentic-RAG-LLMs-API'
tmux new-window -t agentic_rag -n 'testing_terminal' -c '/mnt/d/codebase/Agentic-RAG-LLMs-API'
tmux new-window -t agentic_rag -n 'api_terminal' -c '/mnt/d/codebase/Agentic-RAG-LLMs-API'
tmux new-window -t agentic_rag -n 'ui_terminal' -c '/mnt/d/codebase/Agentic-RAG-LLMs-API'

echo "🎉 安裝完成！"
echo "下次使用指令:"
echo "wsl -d Ubuntu"
echo "conda activate agentic"
echo "cd /mnt/d/codebase/Agentic-RAG-LLMs-API"
echo "tmux attach-session -t agentic_rag"