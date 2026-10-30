# Despliegue en Windows (mini PC)

Destino: `C:\Users\b3-ml\recetas-web\recetas-web-v2`. La web v1 (`C:\Users\b3-ml\recetas-web`) se queda tal cual como respaldo
y su carpeta `videos\` se reutiliza (no se copian vídeos).

Todos los comandos en **PowerShell como administrador** (la tarea programada corre como SYSTEM: hace falta UAC).

## 1. Copia de seguridad y código

```powershell
$Old = "C:\Users\b3-ml\recetas-web"
$New = "$Old\recetas-web-v2"
Compress-Archive -Path "$Old\*" -DestinationPath "C:\Users\b3-ml\recetas-web-backup-$(Get-Date -f yyyyMMdd).zip" `
  -CompressionLevel Fastest   # opcional si la carpeta de vídeos es muy grande
# Copia aquí la carpeta recetas-web-v2 (USB, red o zip). No copies data\recetas.db, media\ ni videos\ desde el box.
```

## 2. Python y dependencias

```powershell
cd $New
py -3.12 -m venv .venv          # Python 3.11+ (probado con 3.13)
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements.txt
```

## 3. Variables y prueba manual

```powershell
New-Item -ItemType Directory -Force C:\ProgramData\recetas-web\secret | Out-Null
$env:RECETAS_VIDEOS_DIR = "$Old\videos"
$env:RECETAS_SECRET_DIR = "C:\ProgramData\recetas-web\secret"
.\run.bat --port 8088
```

Abre `http://localhost:8088` y comprueba que una receta con vídeo lo reproduce. Para la prueba manual para la tarea
antigua primero (paso 4, primera línea) si ocupa el puerto. `Ctrl+C` para salir.

**Por qué `RECETAS_SECRET_DIR` explícito:** por defecto la clave Fernet va a `~\.recetas-web\secret.key`; con SYSTEM
`~` es `C:\Windows\System32\config\systemprofile`, que es incómodo de respaldar y distinto del de tu usuario (las claves
de IA guardadas con una cuenta no se podrían leer con la otra). Restringe la carpeta:

```powershell
icacls C:\ProgramData\recetas-web\secret /inheritance:r /grant "SYSTEM:(OI)(CI)F" "Administrators:(OI)(CI)F"
```

**Haz copia de `secret.key`** (fuera del PC). Sin ella las claves de IA y de APIs guardadas no se pueden descifrar
(se vuelven a introducir; las recetas no se pierden). La sesión de Instagram (`*.session`) también vive ahí.

## 4. Sustituir la tarea programada `RecetasWeb`

```powershell
Stop-ScheduledTask -TaskName RecetasWeb -ErrorAction SilentlyContinue
Export-ScheduledTask -TaskName RecetasWeb | Out-File "$Old\RecetasWeb-v1-task.xml"   # respaldo de la tarea v1
Unregister-ScheduledTask -TaskName RecetasWeb -Confirm:$false

$cmd = "set RECETAS_VIDEOS_DIR=$Old\videos&& set RECETAS_SECRET_DIR=C:\ProgramData\recetas-web\secret&& `"$New\run.bat`" --port 8088"
$action   = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c $cmd" -WorkingDirectory $New
$trigger  = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName RecetasWeb -Action $action -Trigger $trigger -Settings $settings -User SYSTEM -RunLevel Highest
Start-ScheduledTask -TaskName RecetasWeb
Start-Sleep 5; Invoke-RestMethod http://localhost:8088/api/health
```

Firewall (solo red privada/LAN):

```powershell
New-NetFirewallRule -DisplayName "Recetario 8088" -Direction Inbound -Protocol TCP -LocalPort 8088 -Action Allow -Profile Private
```

## Volver a la v1

```powershell
Unregister-ScheduledTask -TaskName RecetasWeb -Confirm:$false
Register-ScheduledTask -TaskName RecetasWeb -Xml (Get-Content "$Old\RecetasWeb-v1-task.xml" -Raw)
Start-ScheduledTask -TaskName RecetasWeb
```

## Notas

- Los datos nuevos viven en `recetas-web-v2\data\recetas.db` (+ `media\`). La primera ejecución siembra la BD con las
  recetas v1 incluidas en `data\seed\`. Respalda `data\`, `media\` y la carpeta secreta.
- La UI (`/api/...`) no pide login: pensada solo para la LAN. Las API externas (`/api/v1`, `/mcp`) exigen token.
