$env:HEALTH_TOKEN="secret"
$proc = Start-Process -FilePath "python" -ArgumentList "run_system.py --source 0 --source-type webcam --target-fps 10 --width 640 --height 480 --bus zmq" -PassThru -NoNewWindow

Write-Host "Waiting 20s for system startup..."
Start-Sleep -Seconds 20

Write-Host "`n--- Health Check (No Token) ---"
try { Invoke-RestMethod -Uri "http://127.0.0.1:9001/health" -Method Get } catch { Write-Host "Error: $_" }

Write-Host "`n--- Ready Check (Ingestion) ---"
try { Invoke-RestMethod -Uri "http://127.0.0.1:9001/ready" -Method Get } catch { Write-Host "Error: $_" }

Write-Host "`n--- Ready Check (Detection) ---"
try { Invoke-RestMethod -Uri "http://127.0.0.1:9002/ready" -Method Get } catch { Write-Host "Error: $_" }

Write-Host "`n--- Token Auth Check (Expected 401) ---"
try { 
    Invoke-RestMethod -Uri "http://127.0.0.1:9001/health" -Method Get 
    Write-Host "WARN: Should have failed with 401!" 
} catch { 
    Write-Host "Success: Got expected error: $_" 
}

Write-Host "`n--- Token Auth Check (Valid Token) ---"
try { 
    $headers = @{ "X-IVIS-Health-Token" = "secret" }
    $res = Invoke-RestMethod -Uri "http://127.0.0.1:9001/health" -Method Get -Headers $headers
    Write-Host "Success: Auth worked."
} catch { 
    Write-Host "Error: $_" 
}

Write-Host "`nStopping system..."
Stop-Process -Id $proc.Id -Force
Stop-Process -Name "python" -Force -ErrorAction SilentlyContinue 
Write-Host "Done."
