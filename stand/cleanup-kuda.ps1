$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$failed = $false

try {
    $stand = (Resolve-Path -LiteralPath 'C:\Users\mset6\kuda-nt').Path
    if ($stand -ne 'C:\Users\mset6\kuda-nt') {
        throw 'Неверный каталог стенда.'
    }
    foreach ($file in @('compose.yaml', 'seed.sql')) {
        if (!(Test-Path -LiteralPath (Join-Path $stand $file) -PathType Leaf)) {
            throw "Не найден $file. Очистка остановлена."
        }
    }
    docker info --format '{{.ServerVersion}}'
    if ($LASTEXITCODE) {
        throw 'Docker недоступен. Запустите Docker Desktop и повторите.'
    }

    Write-Host 'Остановка тестового стенда Kuda...'
    Get-ScheduledTask -ErrorAction SilentlyContinue |
        Where-Object TaskName -Like 'Kuda-PG-Diagnostics*' |
        Stop-ScheduledTask
    docker compose --project-name kuda-nt --file (Join-Path $stand 'compose.yaml') down
    if ($LASTEXITCODE) { throw 'Не удалось остановить контейнеры стенда.' }

    Write-Host 'Удаление тестовой базы данных...'
    $volume = 'kuda-nt_postgres-data'
    $volumes = @(docker volume ls --format '{{.Name}}')
    if ($LASTEXITCODE) { throw 'Не удалось получить список томов Docker.' }
    if ($volumes -contains $volume) {
        docker volume rm $volume
        if ($LASTEXITCODE) { throw 'Не удалось удалить том тестовой базы.' }
    }

    Write-Host 'Удаление старых артефактов...'
    $artifacts = Join-Path $stand 'artifacts'
    if (Test-Path -LiteralPath $artifacts) {
        $resolved = (Resolve-Path -LiteralPath $artifacts).Path
        if ($resolved -ne 'C:\Users\mset6\kuda-nt\artifacts') {
            throw 'Неверный путь к артефактам.'
        }
        if ((Get-Item -LiteralPath $resolved).Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw 'Папка артефактов является ссылкой. Очистка остановлена.'
        }
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
    foreach ($name in @('backend.tar', 'backend-updated.tar')) {
        $file = Join-Path $stand $name
        if (Test-Path -LiteralPath $file -PathType Leaf) {
            Remove-Item -LiteralPath $file
        }
    }

    Write-Host 'Удаление старых образов бэкенда...'
    $images = @(docker image ls --quiet --no-trunc)
    if ($LASTEXITCODE) { throw 'Не удалось получить список образов Docker.' }
    $current = docker image inspect venue-backend:nt-metrics --format '{{.Id}}'
    if ($LASTEXITCODE) { throw 'Не найден текущий образ бэкенда.' }
    foreach ($prefix in @('b6d14ffe853e', '7546643be108')) {
        foreach ($image in $images) {
            if ($image.StartsWith('sha256:' + $prefix) -and $image -ne $current) {
                docker image rm $image
                if ($LASTEXITCODE) {
                    Write-Warning "Образ $prefix используется и оставлен на диске."
                }
            }
        }
    }
    Write-Host ''
    Write-Host 'Очистка завершена. База удалена, контейнеры остановлены.' -ForegroundColor Green
    Write-Host 'Настройки, seed.sql и текущий образ сохранены.'
} catch {
    $failed = $true
    Write-Host ''
    Write-Host ('Ошибка: ' + $_.Exception.Message) -ForegroundColor Red
}

[void](Read-Host 'Нажмите Enter, чтобы закрыть окно')
if ($failed) { exit 1 }

