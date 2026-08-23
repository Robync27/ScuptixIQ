param([string]$Root = "C:\3dmodel_app\MeshForge3D\dist\MeshForge3D\_internal")
Get-ChildItem $Root -Directory | ForEach-Object {
    $s = (Get-ChildItem $_.FullName -Recurse -File | Measure-Object Length -Sum).Sum / 1MB
    [PSCustomObject]@{ MB = [math]::Round($s, 0); Name = $_.Name }
} | Sort-Object MB -Descending | Format-Table -AutoSize | Out-String -Width 200