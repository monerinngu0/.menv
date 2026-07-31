## 1. Windowsのportproxyを追加する

管理者権限のPowerShellで実行する。

```powershell
netsh interface portproxy add v4tov4 listenaddress=192.168.10.6 listenport=8000 connectaddress=127.0.0.1 connectport=8000
```

この設定は次の転送を行う。

```text
192.168.10.6:8000
  ↓
127.0.0.1:8000
```

### portproxyを確認

```powershell
netsh interface portproxy show all
```

正常例：

```text
Listen on ipv4:             Connect to ipv4:

Address         Port        Address         Port
--------------- ----------  --------------- ----------
192.168.10.6    8000        127.0.0.1       8000
```

### portproxyを削除

```powershell
netsh interface portproxy delete v4tov4 listenaddress=192.168.10.6 listenport=8000
```

## 2. WindowsファイアウォールでTCP 8000番を許可する

管理者権限のPowerShellで実行する。

### ルールを追加

LAN内の `192.168.10.0/24` からのみ許可する設定：

```powershell
netsh advfirewall firewall add rule name="menv8000" dir=in action=allow protocol=TCP localport=8000 profile=private remoteip=192.168.10.0/24
```

切り分けのため、接続元を一時的に制限しない場合：

```powershell
netsh advfirewall firewall add rule name="menv8000" dir=in action=allow protocol=TCP localport=8000 profile=any remoteip=any
```

### ルールを確認

```powershell
netsh advfirewall firewall show rule name="menv8000"
```

正常例：

```text
Enabled:        Yes
Direction:      In
Protocol:       TCP
LocalPort:      8000
Action:         Allow
```

### 接続元を変更

すべての接続元を許可：

```powershell
netsh advfirewall firewall set rule name="menv8000" new remoteip=any
```

家庭内LANのみに制限：

```powershell
netsh advfirewall firewall set rule name="menv8000" new remoteip=192.168.10.0/24 profile=private
```

### ルールを削除

```powershell
netsh advfirewall firewall delete rule name="menv8000"
```
