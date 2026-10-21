# LINK LAN Server

LINK Browser에서 이 컴퓨터의 실제 IPv4 주소로 접속할 수 있는 독립 실행형 LINK 서버입니다. Python 3.10 이상과 표준 라이브러리만 사용하며 패키지 설치가 필요하지 않습니다.

`link://192.168.0.10:8000/hello-world`를 입력하면 브라우저가 `http://192.168.0.10:8000/hello-world/world.link`와 그 월드의 Element·Style·Script·이미지를 가져옵니다. LINK Protocol의 실험적 LAN HTTP 프로파일이며, 문서 형식은 LINK World Standards v0.1입니다. [전송 규약](docs/lan-protocol.md)을 참고하세요.

## Windows에서 시작

1. Python 3.10 이상이 설치된 PC에서 `LINK_SERVER_START.cmd`를 실행합니다. Windows Python Launcher의 `py -3`을 먼저 확인하고, 사용할 수 없으면 `python`을 확인합니다.
2. 서버 창에 출력된 `LAN: link://...:8000/hello-world` 주소를 확인합니다. `0.0.0.0`은 모든 IPv4 인터페이스에서 수신하겠다는 설정값이고 접속 주소가 아닙니다.
3. 같은 네트워크의 다른 PC에서 **LAN HTTP를 지원하는 새 LINK Browser 빌드**를 실행하고 그 주소를 LINK 주소창에 입력합니다. 이전 로컬 전용 브라우저는 원격 주소를 열 수 없습니다.
4. 서버를 끝내려면 서버 창에서 `Ctrl+C`를 누릅니다.

서버와 같은 PC에서는 `link://127.0.0.1:8000/hello-world`로 확인할 수 있습니다. 기본 설정은 `0.0.0.0:8000`이며 실행 위치에 관계없이 이 스크립트 옆의 `worlds` 폴더만 공개합니다.

명령줄에서도 실행할 수 있습니다.

```powershell
.\LINK_SERVER_START.cmd
.\LINK_SERVER_START.cmd --port 8001
python .\link_server.py --host 0.0.0.0 --port 8000
python .\link_server.py --host 127.0.0.1 --port 8000
```

`--host 127.0.0.1`은 이 PC 안에서 테스트할 때 사용합니다. `--host`는 IPv4 리터럴만 받습니다. 포트가 이미 사용 중이면 기존 프로그램을 종료하거나 다른 `--port` 값을 지정하세요. 포트를 바꾸면 LINK 주소와 방화벽 규칙의 포트도 맞춰야 합니다.

## 실제 IP 확인과 방화벽

PowerShell 또는 명령 프롬프트에서 `ipconfig`를 실행하고 **실제로 연결된 Ethernet 또는 Wi-Fi 어댑터의 IPv4 주소**를 확인하세요. 가상 머신·VPN의 가상 어댑터 주소가 함께 있을 수 있습니다. 서버는 발견한 주소를 각각 출력하므로, 다른 PC가 연결된 실제 인터페이스 주소를 선택하세요. 실제 네트워크 주소가 반드시 `192.168.*`로 시작하는 것은 아닙니다.

다른 PC에서 연결이 안 되면 같은 네트워크인지, Wi-Fi 클라이언트 격리 정책이 있는지, Windows 방화벽이 Python/TCP 포트를 허용하는지 확인하세요. 서버는 방화벽을 자동 변경하지 않습니다.

필요한 경우 관리자가 아래 명령을 **관리자 PowerShell**에서 직접 실행하면 TCP 8000 접속을 `LocalSubnet`에만 허용할 수 있습니다. 현재 네트워크 프로필이 Public일 수도 있으므로 규칙은 `Any` 프로필에 적용하되, 접속 가능한 원격 주소 범위를 로컬 서브넷으로 제한합니다. 조직에서 관리하는 PC라면 해당 조직의 네트워크 정책을 따르세요.

```powershell
New-NetFirewallRule -Name "LINK-LAN-TCP-8000" -DisplayName "LINK LAN TCP 8000 (LocalSubnet)" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8000 -RemoteAddress LocalSubnet -Profile Any
```

사용을 마친 뒤 해당 규칙을 제거하려면 관리자가 다음 명령을 실행합니다.

```powershell
Remove-NetFirewallRule -Name "LINK-LAN-TCP-8000"
```

외부 인터넷으로 라우터 포트를 전달하지 마세요. 이 프로파일은 신뢰하는 LAN에서 문서를 읽는 평문 HTTP용이며 HTTPS·로그인·인증·권한 관리 기능을 제공하지 않습니다.

## 예제 월드

- `hello-world`: 원격 서버에서 받은 문서임을 표시합니다. 큐브가 회전하고 클릭하면 색이 바뀝니다. `assets/연결.png`는 Unicode 경로의 PNG 전송을 확인하는 생성 이미지입니다. WASD 또는 방향키로 금색 프레임 안에 들어가면 `/second-world`로 이동합니다.
- `second-world`: 같은 서버의 두 번째 월드입니다. 프레임으로 들어가면 `/hello-world`로 돌아갑니다. 상대 포탈 주소는 현재 서버의 IP와 포트를 유지합니다.

Script는 각 브라우저의 월드 인스턴스에서 실행됩니다. 다른 사람이 클릭한 결과나 플레이어 위치를 공유하는 멀티플레이어 상태 동기화는 구현하지 않습니다. 새로고침과 새 탐색은 문서를 다시 가져옵니다.

일반 웹 브라우저에서 `http://서버IP:8000/`를 열면 서버 안내 페이지가 나옵니다. 3D 월드는 LINK Browser에서 열어야 합니다. `http://서버IP:8000/.well-known/link`에서 전송 메타데이터를 확인할 수 있습니다.

## 내 월드 공개

```text
worlds/
  my-world/
    world.link
    scene.element
    appearance.style
    scripts/example.script
    assets/example.png
```

월드 폴더 이름은 ASCII 영문·숫자·하이픈만 사용할 수 있습니다. `world.link`의 `id`도 폴더 이름과 맞추세요. 매니페스트가 참조하는 모든 문서와 이미지는 그 월드 폴더 안에 두세요. 월드 문법과 Script API는 형제 LINK Browser 저장소의 `docs/guides/` 및 `native/docs/language.md`를 참고하세요.

별도 월드 폴더를 공개하려면 절대 경로를 지정합니다. 그 폴더만 서버의 루트가 되고 상위 저장소는 공개되지 않습니다.

```powershell
python .\link_server.py --worlds "C:\LINK\my-worlds" --port 8000
python .\link_server.py --worlds "..\link\native\worlds" --port 8000
```

`--worlds`의 상대 경로는 명령을 실행한 폴더 기준입니다. 기본 경로는 언제나 스크립트 옆의 `worlds`입니다. 공개 폴더는 신뢰하는 작성자가 관리하고, 실행 중에는 링크나 디렉터리 구조를 바꾸지 않는 정적 문서용으로 사용하세요.

## 전송 범위와 제한

서버는 `GET`·`HEAD`만 지원하고 업로드·삭제·디렉터리 목록·리다이렉트를 제공하지 않습니다. 정확한 바이트 길이와 MIME을 응답하며 요청 로그를 서버 창에 표시합니다. 월드 밖으로 벗어나는 경로·심볼릭 링크·정션, `..`, 잘못된 UTF-8, 이중 인코딩, 인코딩된 경로 구분자, query·fragment는 거부합니다. 저장소의 Python 소스나 임의 JSON·HTML 파일은 공개하지 않습니다.

| 리소스 | 파일당 최대 크기 |
| --- | --- |
| `world.link` | 64 KiB |
| `.element`, `.style` | 각각 1 MiB |
| `.script` | 128 KiB |
| 이미지 | 16 MiB |

브라우저는 한 번의 월드 탐색에서 총 64 MiB 제한도 적용합니다. 서버는 서로 독립적인 읽기 요청을 처리하므로 탐색별 합계 상태를 유지하지 않습니다. 예제 이미지는 브라우저에서 지원하는 PNG를 사용합니다.

## 테스트

`link-server` 폴더에서 실행합니다.

```powershell
python -m unittest discover -s tests -v
```

테스트는 임시 폴더와 운영체제가 고른 로컬 포트를 사용합니다. 실제 HTTP의 GET·HEAD·MIME·길이·동시 요청, Unicode 경로, 404, 읽기 외 메서드 거부, 경로 우회, 크기 제한, 실행 위치 독립성, 월드 밖 정션/심볼릭 링크 거부를 확인합니다. 파일 심볼릭 링크를 생성할 권한이 없는 Windows 환경에서는 그 항목만 건너뜁니다. 디렉터리 링크 테스트는 Windows 정션을 대안으로 사용합니다. 방화벽 규칙은 바꾸지 않습니다.

## 라이선스

Copyright 2026 Song Youngwoon. 코드·문서·예제 월드·생성 PNG는 [Apache License 2.0](LICENSE)을 따릅니다. [NOTICE](NOTICE)를 함께 배포하세요. 개인 사진은 포함하지 않습니다.