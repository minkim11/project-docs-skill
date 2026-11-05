# Project Docs

**기획 대화를 제품 PRD와 MVP·기술 명세로 정리하는 Codex 스킬입니다.**

기획을 이야기하는 동안에는 제품의 장기 방향, 이번 버전의 기능, 기술 선택지, 아직 결정하지 않은 내용이 한 대화에 함께 쌓입니다. 이 중 무엇이 확정됐고 이번 범위가 어디까지인지를 문서로 옮겨야 합니다.

Project Docs는 그 내용을 전체 제품 PRD와 현재 MVP·기술 명세로 작성하고, 기획 변경에 따라 문서를 갱신·검토합니다. 문서의 경로·역할·작성 기준은 스킬에 두고, 프로젝트마다 다른 동작과 기술 결정은 해당 프로젝트 문서에 기록합니다.

## 다루는 문제

| 기획 내용을 문서로 정리할 때 다루는 항목 | 스킬의 작성 기준 |
|---|---|
| 장기 계획과 현재 버전의 범위 | 전체 PRD에 제품 맥락을, MVP에 현재 동작·제외 범위·완료 기준을 기록 |
| 확정된 결정과 아직 검토 중인 생각 | 확정·제안·미정을 구분하고, 미정이 막는 요구사항과 단계를 표시 |
| 여러 문서에 등장하는 같은 정보 | 동작은 MVP, 저장 구조는 데이터 모델, HTTP 계약은 OpenAPI가 담당하고 ID·링크로 연결 |
| 구체적이지 않은 기술 선택과 프로젝트 구조 | 전체 구성·기술스택, 패키지 구조·의존 방향, 통신·실행·배포 설계를 아키텍처에 기록 |
| 문서별 읽기 범위와 참고 순서 | AGENTS에 읽기 경계와 작업별 참고 문서·검증 지침을 지정 |

## 동작 방식

Codex가 `SKILL.md`의 절차를 따르면서 요청에 해당하는 참고 지침과 템플릿을 선택해 사용합니다. 요청한 문서와 그 변경에 직접 영향을 받는 문서를 작성 대상으로 삼습니다.

1. **요청과 입력 확인** — 대상 프로젝트와 작성·수정·검토 범위를 확인합니다. 기획·MVP 작업은 대화와 전체 PRD를, 기술 명세 작업은 현재 MVP와 관련 계약을 참고합니다.
2. **범위와 결정 정리** — 사용자 흐름, 업무 규칙, 제외 범위, 완료 기준을 명시합니다. 동작·권한·데이터 처리를 바꾸는 미정은 임의로 채우지 않고 질문하거나 차단 범위를 기록합니다.
3. **담당 문서에 명세 작성** — 요청에 맞춰 PRD·MVP와 기술 문서를 작성합니다. 기술 문서에는 경로와 계약을 기록하고, 아키텍처 선택의 이유는 프로젝트 요구와 연결합니다. HTTP API가 있다면 `openapi.yaml`에 계약을 작성합니다.
4. **참조와 상태 검토** — REQ·AC ID, 링크, 문서 간 계약을 대조합니다. 사용 가능한 비수정 문서 검사만 실행하고, 변경 문서·현재 상태·남은 미정·검증 범위를 보고합니다.

## 설치

### 직접 설치: 모든 프로젝트에서 사용

Windows PowerShell에서 실행합니다. Git이 설치되어 있어야 하며, 비공개 저장소에 접근할 수 있는 GitHub 계정으로 Git 인증이 되어 있어야 합니다.

```powershell
$skillInstallRoot = Join-Path $env:USERPROFILE '.agents\skills'
New-Item -ItemType Directory -Path $skillInstallRoot -Force | Out-Null
git clone https://github.com/minkim11/project-docs-skill.git (Join-Path $skillInstallRoot 'project-docs')
```

설치 위치는 `%USERPROFILE%\.agents\skills\project-docs`입니다. 이미 해당 위치에 Git으로 설치했다면 다시 복제하는 대신 아래 명령으로 업데이트합니다.

```powershell
git -C "$env:USERPROFILE\.agents\skills\project-docs" pull --ff-only
```

### Git 없이 수동 설치

1. GitHub 저장소의 **Code → Download ZIP**으로 파일을 받거나, 이미 받은 스킬 폴더를 준비합니다.
2. `%USERPROFILE%\.agents\skills\project-docs` 폴더를 만듭니다.
3. 스킬의 `SKILL.md`와 `agents/`, `references/`, `assets/`, `scripts/`를 그 폴더 바로 아래에 복사합니다. ZIP에서 풀린 상위 폴더가 한 겹 더 들어가지 않도록 합니다.

```text
%USERPROFILE%\.agents\skills\project-docs\
├─ SKILL.md
├─ agents\
├─ references\
├─ assets\
└─ scripts\
```

특정 프로젝트에서만 사용하려면 같은 파일과 폴더를 **해당 프로젝트 루트의 `.agents/skills/project-docs/`**에 복사합니다.

### Codex에게 설치 요청

직접 설치하는 대신 Skill Installer에 요청할 수도 있습니다.

```text
$skill-installer minkim11/project-docs-skill 저장소 루트의 스킬을 개인 스킬 폴더 ~/.agents/skills 아래에 project-docs라는 이름으로 설치해줘.
```

설치 후 Codex에서 `$project-docs`를 선택해 사용합니다. 목록에 나타나지 않으면 Codex를 재시작하고 다시 확인합니다. 경로 기준은 [Codex 공식 스킬 문서](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills)를 따릅니다.

## 빠른 시작

설치 후, 기획을 이야기한 대화에서 다음처럼 요청하세요.

```text
$project-docs 지금까지 합의한 기획으로 전체 PRD와 MVP 0.1, 관련 기술 명세를 만들어줘.
대상 폴더는 C:\projects\my-app이야.
```

필요한 문서만 요청할 수도 있습니다.

| 하고 싶은 일 | 요청 예시 |
|---|---|
| 제품 기획 정리 | `$project-docs 이 아이디어를 전체 PRD로 정리해줘.` |
| 다음 버전 기획 | `$project-docs 전체 PRD를 참고해서 MVP 0.2의 범위와 완료 기준을 작성해줘.` |
| API 명세 작성·수정 | `$project-docs 현재 MVP를 기준으로 OpenAPI 명세를 작성하고 관련 문서를 맞춰줘.` |
| 문서 완결성 검토 | `$project-docs 현재 MVP와 기술 명세의 누락·모순·미정 사항을 검토해줘.` |

## 만들어지는 문서

| 문서 | 담는 내용 |
|---|---|
| `docs/product/PRD.md` | 제품 목적, 사용자, 전체 경험, 장기 방향 |
| `docs/v<version>/MVP.md` | 해당 버전의 동작, 제외 범위, 검증 가능한 완료 기준 |
| `docs/implementation/ARCHITECTURE.md` | 전체 구성, 기술스택, 패키지 구조·의존 방향, 통신·실행 구조, 필요한 배포 설계와 초기화 선택값 |
| `docs/implementation/CONVENTIONS.md` | 코드 규칙, 포매터·린터 설정 기준, 검사 명령 |
| `docs/implementation/DATA_MODEL.md` | 저장 구조, ERD, 필드·관계·제약조건 |
| `docs/implementation/openapi.yaml` | HTTP API 요청·응답·인증·오류 계약 |
| `docs/decisions/` | 여러 대안 중 선택한 기술 결정의 이유·트레이드오프·재검토 조건과 인덱스. 초기화·빌드 설정도 포함 |
| `AGENTS.md` | 읽기 경계, 작업별 참고 문서와 검증 지침 |

요청한 산출물과 프로젝트에 필요한 문서만 작성합니다. 데이터 모델은 저장 요구가 있을 때, OpenAPI는 HTTP API가 있을 때, ADR은 기록할 결정이 있을 때 추가합니다.

MVP만 `docs/v0.1/MVP.md`, `docs/v0.2/MVP.md`처럼 버전별로 보관합니다. 기술 문서는 공통 `docs/implementation/`에서 현행 기준 한 벌로 관리합니다. AGENTS의 현재 MVP 링크로 대상을 지정하며, 높은 버전 폴더가 생겨도 자동 전환하지 않습니다. 과거 MVP에서 연결한 공통 기술 문서는 최신 내용이므로, 당시 기술 명세가 필요하면 Git 이력을 확인합니다.

## 문서 검증

문서 작성·수정 후 **자동 검사와 내용 리뷰를 함께 수행**합니다.

| 구분 | 역할 |
|---|---|
| `scripts/validate_docs.py` | 링크·REQ/AC ID·MVP 버전, 지원하는 OpenAPI 항목의 형식과 참조 확인 |
| `references/review-checklist.md` | 의미상 중복·모순, 빠진 동작, 문서 완결성과 Ready 조건 검토 |

자동 검사는 생성된 프로젝트 문서를 읽으며 파일을 수정하지 않습니다. 전체 PRD는 기본 검사에서 제외하고, 허용된 기획 작업에서만 명시적으로 포함합니다. 자동 검사 통과가 내용의 타당성 검토를 대신하지는 않습니다.

Python 3.10 이상이 필요합니다. OpenAPI의 YAML·기본 항목 검사는 PyYAML이 이미 있는 환경에서 실행하고, 없으면 해당 검사를 미검증으로 보고합니다. 의존성을 자동 설치하지 않습니다. 실행 명령·검사 범위·한계는 [자동 검증 안내](references/validation.md)에 있습니다.

## 제작 의도

프로젝트마다 기획 대화를 다시 정리하고 문서 구조를 새로 정하는 반복을 줄이기 위해 만들었습니다.

- 제품의 장기 맥락을 보존하면서 현재 구현 범위를 명확히 구분합니다.
- 문서별 정보의 담당 위치를 정해 중복과 불일치를 줄입니다.
- 구현 에이전트가 과거 대화 대신 현재 명세에서 필요한 정보를 찾도록 합니다.

현재 버전은 `0.1.0`이며, 실제 프로젝트 적용 검증 전인 초기 개발 단계입니다.

## 참고 자료

- [BMAD bmad-spec](https://github.com/bmad-code-org/bmad-plugins/blob/main/plugins/method/skills/bmad-spec/SKILL.md)
- [Spec-Driven Development Skills and Templates](https://github.com/alabenkhlifa/Specs-Driven-Development-Skills-Templates)
- [Project Architect](https://github.com/ersinkoc/project-architect/blob/main/SKILL.md)
- [OpenAPI](https://spec.openapis.org/oas/v3.1.0.html)
- [Google Style Guides](https://google.github.io/styleguide/)
