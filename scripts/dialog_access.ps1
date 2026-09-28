# Semantic Windows control access. Requests arrive as data on stdin.
$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

try {
    $request = [Console]::In.ReadToEnd() | ConvertFrom-Json
    $element = [System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]$request.handle)
    if ($element.Current.ProcessId -ne $request.process_id) {
        throw 'The dialog control no longer belongs to the target FL process'
    }
    switch ($request.action) {
        'read' {
            $children = $element.FindAll([System.Windows.Automation.TreeScope]::Subtree,
                                        [System.Windows.Automation.Condition]::TrueCondition)
            $result = @($children | ForEach-Object {
                @{ name = $_.Current.Name; id = $_.Current.AutomationId
                   handle = $_.Current.NativeWindowHandle; enabled = $_.Current.IsEnabled }
            })
            ConvertTo-Json -InputObject $result -Compress
        }
        default { throw 'Unsupported dialog control action' }
    }
} catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}
