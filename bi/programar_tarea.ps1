# crea en el Programador de tareas de Windows la tarea que corre bi\cierre_diario.py
# todos los dias a la 1:00 a. m. (la cafeteria ya cerro y el dia anterior queda completo).
#
#   powershell -ExecutionPolicy Bypass -File bi\programar_tarea.ps1          crea o actualiza la tarea
#   powershell -ExecutionPolicy Bypass -File bi\programar_tarea.ps1 -Quitar  la borra
param([switch]$Quitar, [string]$Hora = "01:00")

$nombre = "UBite cierre diario"
if ($Quitar) {
    Unregister-ScheduledTask -TaskName $nombre -Confirm:$false
    Write-Host "Tarea '$nombre' eliminada."
    exit
}

$raiz = Split-Path -Parent $PSScriptRoot
$python = @("$raiz\venv\Scripts\python.exe", "$raiz\.venv\Scripts\python.exe", "$raiz\env\Scripts\python.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $python) {
    Write-Host "No se encontró el entorno virtual de la app (venv). Créalo primero como dice el README."
    exit 1
}

$accion = New-ScheduledTaskAction -Execute $python -Argument "bi\cierre_diario.py" -WorkingDirectory $raiz
$cuando = New-ScheduledTaskTrigger -Daily -At $Hora
# si el computador estaba apagado a esa hora, la tarea corre apenas se prenda
$ajustes = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1)
Register-ScheduledTask -TaskName $nombre -Action $accion -Trigger $cuando -Settings $ajustes `
    -Description "ETL del almacén y predicción de UBite para Power BI" -Force | Out-Null
Write-Host "Tarea '$nombre' programada todos los días a las $Hora con $python"
Write-Host "Para probarla ahora: Start-ScheduledTask -TaskName '$nombre'  (el resultado queda en bi\cierre_diario.log)"
