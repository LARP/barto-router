'=== Get-Disk ==='
Get-Disk | Select-Object Number, FriendlyName, PartitionStyle, OperationalStatus,
    HealthStatus, @{n='SizeGB';e={[math]::Round($_.Size/1GB,1)}}, IsBoot, IsSystem |
    Format-Table -AutoSize

'=== Get-PhysicalDisk ==='
Get-PhysicalDisk | Select-Object DeviceId, FriendlyName, MediaType, BusType,
    @{n='SizeGB';e={[math]::Round($_.Size/1GB,1)}}, HealthStatus, OperationalStatus |
    Format-Table -AutoSize

'=== Get-Partition ==='
Get-Partition | Select-Object DiskNumber, PartitionNumber, DriveLetter, Type,
    @{n='SizeGB';e={[math]::Round($_.Size/1GB,2)}} |
    Format-Table -AutoSize
