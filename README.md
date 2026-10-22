# LINK Server

**Every World. One Link.**

Element·Script·Style로 만든 가상세계를 LINK Browser에 제공하는 독립 실행형 서버입니다. Python 3.10 이상과 표준 라이브러리만 사용합니다.

기본 전송은 **LINK Protocol 0.1 / TCP**입니다. `link://192.168.0.10:8000/hello-world`로 접속하면 브라우저와 서버가 하나의 TCP 연결에서 LINK 메시지로 버전을 확인하고, 월드 문서와 이미지를 교환합니다. HTTP 요청·응답을 거치지 않습니다. 문서 형식은 LINK World Standards v0.1을 사용합니다. [전송 규약](docs/link-protocol-v0.1.md)을 참고하세요.

## Windows에서 시작

1. Python 3.10 이상이 설치된 PC에서 `LINK_SERVER_START.cmd`를 실행합니다. Windows Python Launcher의 `py -3`을 먼저 확인하고 사용할 수 없으면 `python`을 확인합니다.
2. 서버 창의 `LINK/TCP` 표시와 `LAN: link://...:8000/hello-world` 주소를 확인합니다.
3. **직접 LINK/TCP 접속을 지원하는 최신 LINK Browser 빌드**에서 그 주소를 엽니다. 이전 HTTP 전용 브라우저는 기본 서버와 호환되지 않으므로 브라우저와 서버를 함께 업데이트하세요.
4. 서버를 끝내려면 `Ctrl+C`를 누릅니다.

같은 PC에서는 `link://127.0.0.1:8000/hello-world`로 확인할 수 있습니다. 기본 수신 주소는 `0.0.0.0:8000`입니다. `0.0.0.0`은 모든 IPv4 인터페이스에서 수신한다는 설정값이며 접속 주소가 아닙니다.

~~~powershell
.\LINK_SERVER_START.cmd
.\LINK_SERVER_START.cmd --port 8001
python .\link_server.py --host 0.0.0.0 --port 8000
python .\link_server.py --host 127.0.0.1 --port 8000
~~~

`--host`는 숫자로 된 IPv4 주소를 받습니다. `127.0.0.1`은 이 PC 안에서만 접속할 때 사용합니다. 포트가 사용 중이면 다른 `--port`를 지정하고 브라우저 주소에도 같은 포트를 사용하세요. 기본 월드 경로는 실행 위치와 관계없이 스크립트 옆의 `worlds`입니다.

기본 TCP 포트는 일반 웹 브라우저의 HTTP 주소로 열 수 없습니다. 자동으로 HTTP로 전환하는 동작은 없습니다.

## 실제 IP와 네트워크

PowerShell에서 `ipconfig`를 실행하고 실제로 연결된 Ethernet 또는 Wi-Fi 어댑터의 IPv4 주소를 선택하세요. 가상 머신·VPN 주소가 함께 표시될 수 있고, 실제 주소가 반드시 `192.168.*`로 시작하는 것은 아닙니다.

다른 PC에서는 다음 명령으로 TCP 포트 접근 여부를 확인할 수 있습니다. 이 명령의 성공은 포트가 열려 있다는 뜻이며 LINK 메시지 교환까지 확인하는 검사는 아닙니다.

~~~powershell
Test-NetConnection 서버IPv4 -Port 8000
~~~

접속이 안 되면 서버 실행 여부, 주소·포트, 네트워크 경로와 Windows 방화벽의 Python/TCP 허용 여부를 확인하세요. 서버는 방화벽이나 공유기 설정을 자동 변경하지 않습니다.

현재 구현은 **암호화·서버 인증·로그인·권한 검사가 없는 평문 TCP**입니다. LINK 규격을 사용한다는 이유로 HTTPS보다 안전해지는 것은 아닙니다. 신뢰하는 환경에서 시험하고, 외부 네트워크에서 사용할 때에는 보호된 네트워크 경로를 별도로 마련해야 합니다. TLS와 인증은 후속 작업입니다.

## 예제 월드

| 주소 끝부분 | 공간 |
| --- | --- |
| `/hello-world` | 회전하고 클릭하면 색이 바뀌는 큐브, UTF-8 경로 이미지, 두 번째 월드로 가는 포탈 |
| `/second-world` | 같은 서버의 두 번째 공간과 돌아오는 포탈 |
| `/afterlight` | 원목 가구, 오후빛, 책과 스탠드가 있는 작은 3D 방 |

`/second-world` 같은 상대 포탈 주소는 접속한 서버의 IP와 포트를 유지합니다. `link://local/...`은 방문 중인 브라우저 PC의 로컬 월드를 뜻합니다. 포탈 이동과 새로고침은 새로운 연결에서 월드를 다시 가져옵니다.

AFTERLIGHT에서는 WASD와 마우스 드래그로 이동하고, 탁자의 책 표지를 클릭해 펼치거나 스탠드 받침을 클릭해 작은 빛무리를 켤 수 있습니다. [제작 방식과 조작 안내](https://github.com/songyoungwoon/link/blob/main/docs/afterlight.md)는 LINK Browser 저장소에 있습니다. 빛과 그림자는 정적 베이크입니다.

Script는 각 브라우저에서 실행됩니다. 다른 사용자의 클릭이나 플레이어 위치를 공유하는 멀티플레이어 동기화는 아직 제공하지 않습니다.

## 내 월드 공개

~~~text
worlds/
  my-world/
    world.link
    scene.element
    appearance.style
    scripts/example.script
    assets/example.png
~~~

폴더 이름은 ASCII 영문·숫자·하이픈으로 작성하고 `world.link`의 `id`와 맞추세요. 참조하는 모든 문서와 이미지는 해당 월드 안에 두세요. [Element·Script·Style 가이드](https://github.com/songyoungwoon/link/tree/main/docs/guides)를 참고하세요.

별도 월드 루트를 지정할 수도 있습니다. 해당 폴더만 공개되며 상위 저장소를 공개하지 않습니다.

~~~powershell
python .\link_server.py --worlds "C:\LINK\my-worlds" --port 8000
python .\link_server.py --worlds "..\link\native\worlds" --port 8000
~~~

`--worlds`의 상대 경로는 실행한 폴더 기준입니다. 공개 폴더는 신뢰하는 작성자가 관리하고 실행 중에는 정션·심볼릭 링크나 디렉터리 구조를 바꾸지 마세요.

같은 연결의 요청도 매번 현재 파일을 읽습니다. 연결 중 파일을 수정하면 서로 다른 시점의 문서가 섞일 수 있습니다. 일관된 스냅샷이나 콘텐츠 해시 검증은 아직 제공하지 않으므로 월드 편집을 끝낸 뒤 서버에 반영하는 방식으로 사용하세요.

## 전송 범위와 제한

LINK Protocol 0.1은 `HELLO → WELCOME → GET / RESOURCE → GOODBYE` 순서의 읽기 전용 세션입니다. 요청 ID와 메시지 길이를 검사하고 잘못된 요청에는 가능한 경우 `ERROR`를 보낸 뒤 연결을 종료합니다. 하나의 세션은 하나의 월드만 읽을 수 있습니다.

| 제한 | 값 |
| --- | --- |
| 동시 TCP 세션 | 32 |
| 세션당 GET | 최대 256회 |
| 세션당 리소스 합계 | 64 MiB |
| `world.link` | 64 KiB |
| `.element`, `.style` | 각각 1 MiB |
| `.script` | 128 KiB |
| 이미지 | 16 MiB |
| 리소스 상대 경로 | UTF-8 기준 2,048바이트 |
| 수신 메시지 | 헤더와 본문을 합쳐 10초 |
| 쓰기 | socket sendall에 10초 제한 |

GET에서 클라이언트가 지정한 최대 바이트 수도 적용합니다. 경로는 URL 인코딩 없이 UTF-8로 전송하며 상위 경로·Windows 별칭·대체 데이터 스트림·월드 밖 정션과 심볼릭 링크 등을 거부합니다. 허용된 문서와 이미지 확장자만 제공하며 저장소 소스, 임의 JSON·HTML, 디렉터리 목록, 업로드·삭제는 공개하지 않습니다.

재접속·실시간 상태 동기화·압축·스트리밍 우선순위·캐시 협상은 이번 규격에 포함하지 않습니다.

## 기존 HTTP 브라우저와 시험

이전 HTTP 전용 LINK Browser가 필요한 경우 별도 옵션으로 기존 서버를 실행할 수 있습니다.

~~~powershell
.\LINK_SERVER_START.cmd --transport http --port 8001
~~~

이 모드는 기존 HTTP GET·HEAD, 안내 페이지 `http://서버IP:8001/`와 선택적 `/.well-known/link` 메타데이터를 제공합니다. 새 LINK/TCP 브라우저는 이 서버로 자동 전환하지 않습니다. 두 방식을 함께 시험하려면 각기 다른 포트에서 서버를 실행하세요. [기존 LAN HTTP 문서](docs/lan-protocol.md)를 참고하세요.

## 테스트

~~~powershell
python -m unittest discover -s tests -v
~~~

테스트는 임시 폴더와 운영체제가 고른 loopback 포트에서 실행하며 방화벽을 변경하지 않습니다. 실제 소켓에서 분할·연속 프레임, 버전·순서·길이 검증, 오류, Unicode, 경로 우회, 리소스·세션 제한, 느린 메시지·유휴 시간 제한, 동시 접속, 서버 종료와 기존 HTTP 동작을 확인합니다. 파일 심볼릭 링크 권한이 없는 Windows에서는 해당 검사만 건너뜁니다.

## 라이선스

Copyright 2026 Song Youngwoon. 코드·문서·예제 월드·생성 이미지는 [Apache License 2.0](LICENSE)을 따릅니다. [NOTICE](NOTICE)를 함께 배포하세요. 개인 사진은 포함하지 않습니다.