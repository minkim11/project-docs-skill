# Project Docs

기획 대화를 전체 제품 PRD와 현재 MVP 구현 명세로 정리하는 개인용 Agent Skill 원본. 버전 0.1.0의 초기 개발 상태이며, 실제 프로젝트 적용 검증 전이다. 스킬 폴더 하나이며 플러그인이나 실행 서비스는 아니다.

## 사용

스킬을 설치한 환경에서 다음처럼 요청한다.

```text
$project-docs 지금까지 합의한 기획으로 새 프로젝트의 전체 PRD와 MVP 0.1 문서를 만들어줘. 대상 폴더는 ...
$project-docs 전체 PRD를 참고해서 다음 MVP 0.2 범위를 정리해줘.
$project-docs 현재 MVP 범위 안에서 OpenAPI 명세를 수정하고 관련 문서의 모순을 확인해줘.
$project-docs 현재 구현 문서가 전체 PRD 없이 구현 가능한지 검토해줘.
```

코드 구현은 생성된 프로젝트의 AGENTS와 현재 구현 문서로 진행한다. 이 스킬은 문서 작업에만 선택되도록 설명되어 있다. 이름을 직접 지정하지 않아도 문서 작업 요청에 선택될 수 있다. 읽기 제한은 지침이며 파일 접근 제어가 아니다. 기획에서 구현으로 넘어갈 때 새 대화로 현재 문서만 전달하면 이미 읽은 전체 PRD의 문맥도 분리할 수 있다.

## 원본과 설치

현재 폴더는 편집·GitHub 버전 관리용 원본이다. 이 위치에 두는 것만으로 모든 프로젝트에서 자동 발견되지는 않는다. 설치가 요청되면 대상 환경에서 지원하는 개인 스킬 위치 또는 프로젝트의 `.agents/skills/project-docs/`에 이 폴더를 설치한다. 문서화 대상 프로젝트의 AGENTS 템플릿을 이 스킬 원본의 루트로 복사하지 않는다.

스킬 설치/업데이트와 기존 프로젝트 문서 갱신은 별개다. 업데이트 시 프로젝트별 결정을 덮어쓰지 않는다. 원격 저장소 게시·설치·자동 업데이트는 이 원본 제작에 포함되지 않는다.

## 구성과 기본값

- `SKILL.md`: 호출 범위와 문서 작성 흐름.
- `references/`: 문서 소유·읽기·버전 규칙, 패키지 구조 기본값, 검토 목록.
- `assets/templates/`: 필요한 출력에만 사용하는 Markdown/OpenAPI 양식.
- `agents/openai.yaml`: 표시 이름과 기본 요청.

현재 문서는 `docs/product/PRD.md`와 `docs/implementation/`에 고정한다. MVP 버전은 헤더와 Git 이력으로 관리하고, 보관본은 요청할 때만 만든다. 요구사항은 REQ/AC ID로 연결한다. API는 OpenAPI 계약을 먼저 확정하고 구현한다. 실제 API 검증기나 테스트 도구를 번들로 설치하지 않는다.

## 참고한 설계

다음 프로젝트의 개념을 참고해 이 요구에 맞는 지침을 새로 작성했다. 상위 프로젝트 코드를 복사하거나 실행 의존성을 가져오지 않았다.

- [BMAD bmad-spec](https://github.com/bmad-code-org/bmad-plugins/blob/main/plugins/method/skills/bmad-spec/SKILL.md): 원본과 구현 명세의 분리.
- [Spec-Driven Development Skills and Templates](https://github.com/alabenkhlifa/Specs-Driven-Development-Skills-Templates): 활성 구현 범위와 보류 범위의 구분.
- [Project Architect](https://github.com/ersinkoc/project-architect/blob/main/SKILL.md): 대화에서 기술 문서로 연결하는 작성 흐름.
- [OpenAPI 3.1.0](https://spec.openapis.org/oas/v3.1.0.html): API 계약 형식.

실제 프로젝트 품질과 토큰 절감은 실사용으로 평가해야 한다.
