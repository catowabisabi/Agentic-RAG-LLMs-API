@echo off
echo ======================================
echo LangGraph RAG Demo Setup
echo ======================================

echo.
echo 1. Installing dependencies...
pip install -r requirements.txt

echo.
echo 2. Creating sample documents...
python load_documents.py --create-samples

echo.
echo 3. Loading documents into vector database...
python load_documents.py --directory ./documents

echo.
echo ======================================
echo Setup complete!
echo ======================================
echo.
echo Next steps:
echo 1. Copy .env.example to .env
echo 2. Add your OpenAI API key to .env
echo 3. Run: python main.py
echo.
echo For help: python main.py --help
pause