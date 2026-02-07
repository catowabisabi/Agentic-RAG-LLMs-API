# ====================================
# 停止所有 Agentic RAG 相關服務 (PowerShell)
# ====================================

Write-Host "====================================" -ForegroundColor Cyan
Write-Host "停止所有 Agentic RAG 相關服務" -ForegroundColor Cyan  
Write-Host "====================================" -ForegroundColor Cyan
Write-Host

# 1. 停止所有 Python 程序
Write-Host "[1] 停止所有 Python 程序..." -ForegroundColor Yellow
$pythonProcesses = Get-Process python -ErrorAction SilentlyContinue
if ($pythonProcesses) {
    $pythonProcesses | Stop-Process -Force
    Write-Host "✓ 已停止 $($pythonProcesses.Count) 個 Python 程序" -ForegroundColor Green
} else {
    Write-Host "- 沒有 Python 程序在執行" -ForegroundColor Gray
}

# 2. 停止所有 Node.js 程序  
Write-Host "`n[2] 停止所有 Node.js 程序..." -ForegroundColor Yellow
$nodeProcesses = Get-Process node -ErrorAction SilentlyContinue
if ($nodeProcesses) {
    $nodeProcesses | Stop-Process -Force
    Write-Host "✓ 已停止 $($nodeProcesses.Count) 個 Node.js 程序" -ForegroundColor Green
} else {
    Write-Host "- 沒有 Node.js 程序在執行" -ForegroundColor Gray
}

# 3. 停止所有 uvicorn 程序
Write-Host "`n[3] 停止所有 uvicorn 程序..." -ForegroundColor Yellow
$uvicornProcesses = Get-Process uvicorn -ErrorAction SilentlyContinue  
if ($uvicornProcesses) {
    $uvicornProcesses | Stop-Process -Force
    Write-Host "✓ 已停止 $($uvicornProcesses.Count) 個 uvicorn 程序" -ForegroundColor Green
} else {
    Write-Host "- 沒有 uvicorn 程序在執行" -ForegroundColor Gray
}

# 4. 檢查並清理特定端口
Write-Host "`n[4] 檢查 port 1130 (API) 和 1131 (UI)..." -ForegroundColor Yellow

$port1130 = netstat -ano | findstr ":1130" | Select-String "LISTENING"
$port1131 = netstat -ano | findstr ":1131" | Select-String "LISTENING"

if ($port1130) {
    $pid1130 = ($port1130 -split '\s+')[-1]
    Write-Host "- 強制停止 port 1130 程序 (PID: $pid1130)" -ForegroundColor Yellow
    Stop-Process -Id $pid1130 -Force -ErrorAction SilentlyContinue
} else {
    Write-Host "✓ Port 1130 已清空" -ForegroundColor Green
}

if ($port1131) {
    $pid1131 = ($port1131 -split '\s+')[-1] 
    Write-Host "- 強制停止 port 1131 程序 (PID: $pid1131)" -ForegroundColor Yellow
    Stop-Process -Id $pid1131 -Force -ErrorAction SilentlyContinue
} else {
    Write-Host "✓ Port 1131 已清空" -ForegroundColor Green
}

# 5. 最終檢查
Write-Host "`n[5] 最終檢查..." -ForegroundColor Yellow
$remainingProcesses = Get-Process | Where-Object {$_.ProcessName -like "*python*" -or $_.ProcessName -like "*node*" -or $_.ProcessName -like "*uvicorn*"}

if ($remainingProcesses) {
    Write-Host "⚠️  仍有程序在執行:" -ForegroundColor Red
    $remainingProcesses | Select-Object ProcessName, Id, CPU | Format-Table
} else {
    Write-Host "✓ 所有相關程序已清理完成" -ForegroundColor Green
}

Write-Host "`n====================================" -ForegroundColor Cyan
Write-Host "✅ 清理完成！所有服務已停止" -ForegroundColor Green
Write-Host "====================================" -ForegroundColor Cyan
Write-Host "`n💡 如需重新啟動:" -ForegroundColor Cyan
Write-Host "   - API 後端: .\start_api.bat" -ForegroundColor White  
Write-Host "   - UI 前端: cd ui; npm run dev" -ForegroundColor White
Write-Host

Read-Host "按 Enter 鍵結束"