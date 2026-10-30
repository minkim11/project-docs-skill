---
name: project-docs
description: "대화와 기획 내용을 전체 PRD, 버전별 MVP, 아키텍처, 데이터 모델, OpenAPI 계약으로 작성·수정·검토한다. 새 프로젝트의 문서 체계를 만들거나 다음 MVP의 범위를 정할 때 사용한다. 일반 코드 구현·테스트·버그 수정·리팩터링·코드 리뷰에는 사용하지 않는다."
metadata:
  version: "0.1.0"
---

# Project Docs

채팅의 합의를 사람이 참고할 제품 문서와 에이전트가 구현할 현재 명세로 옮긴다. 프로젝트별 내용은 생성된 문서에 저장하고 이 스킬에는 저장하지 않는다. 작성 언어는 사용자 언어, 경로와 식별자는 아래 규칙을 따른다.

## 작업 경계

- 문서 생성·수정·검토만 수행한다. 애플리케이션 코드, DB 마이그레이션, 의존성 설치, 배포는 이 스킬의 작업에 포함하지 않는다.
- 전체 PRD는 제품 기획·PRD 갱신·MVP 작성 및 범위 수정 때만 읽는다. 기술 명세만 수정할 때는 현재 MVP와 관련 계약으로 작업한다. 구현 요청은 프로젝트 `AGENTS.md`와 구현 명세로 넘기며 이 스킬의 문서 작성 절차를 실행하지 않는다.
- 필요한 출력의 템플릿만 읽는다. 전체 PRD, 모든 기술 문서, 모든 ADR을 일괄 로딩하지 않는다.
- 기존 프로젝트에서는 현행 경로·스키마·규칙을 먼저 확인한다. 새 표준으로 이동하거나 기존 `AGENTS.md`를 통째로 덮어쓰지 말고 필요한 변경을 병합한다.

## 작성 흐름

1. 대상 프로젝트와 작업을 식별한다: 초기 기획, 다음 MVP, 문서 수정, 문서 검토. 프로젝트가 불명확할 때만 위치를 확인한다. 대화에서 확정사항·제안·미정을 구분하고, 이미 답한 질문을 반복하지 않는다.
2. [문서 계약](references/document-contract.md)에서 작업에 관련된 경로·정보 소유·버전 절만 읽는다. 초기 구조 선정 때만 [패키지 구조 기본값](references/project-layouts.md)을 추가로 읽는다.
3. 기획 작업이면 전체 PRD의 사용자·문제·제품 방향을 정리한 뒤 이번 MVP에 들어갈 동작을 선별한다. 전체 PRD를 단순 축약하거나 장기 기능을 전부 구현 명세에 옮기지 않는다. 다음 버전에서는 기존 동작과 관련 계약을 기준선으로 보존하고 새로 구현할 변경과 구분한다. 전체 이력을 재복사하지 않고 이번 변경에 필요한 기존 조건은 현재 명세에서 완결되게 유지한다.
4. MVP에 범위, 업무 규칙, 제외 범위, 완료 기준을 작성한다. 중요한 제품 결정이 빠졌으면 관련 질문을 묶어 묻는다. 형식·경로 같은 일상적 선택은 기본값으로 처리한다. 동작·권한·데이터 처리·외부 계약을 바꾸는 미정을 사실로 채우지 않는다.
5. 확정된 MVP로 아키텍처와 코드 규칙을 정하고 필요한 경우 데이터 모델·OpenAPI·ADR을 작성한다. 기존 코드가 있으면 연결 지점과 실제 제약을 확인하되 코드를 수정하지 않는다.
6. HTTP API는 `openapi.yaml`에 먼저 정의하고 검토한 뒤 구현에 전달한다. 생성 코드나 런타임 출력이 계약을 덮어쓰게 하지 않는다. 데이터·API 작업의 상세 규칙은 [문서 계약](references/document-contract.md)의 해당 절만 따른다.
7. 프로젝트용 `AGENTS.md`에 읽기 경계·작업별 진입점·검증 명령을 생성 또는 병합한다. 선택 문서 중 실제 존재하는 것만 연결한다. 스킬의 작성 절차를 프로젝트 작업 지침에 복제하지 않는다.
8. [검토 목록](references/review-checklist.md)으로 변경 문서와 영향을 받는 참조를 점검한다. 실행 가능한 명세 검증기가 이미 있으면 사용하고, 실행하지 못한 검증과 의미상 미정을 구분해 보고한다.

## 출력 템플릿

| 출력 경로 | 템플릿 | 생성 조건 |
|---|---|---|
| `AGENTS.md` | [AGENTS](assets/templates/AGENTS.md) | 새 체계 또는 읽기 규칙 갱신 |
| `docs/product/PRD.md` | [PRD](assets/templates/PRD.md) | 제품 기획 |
| `docs/implementation/MVP.md` | [MVP](assets/templates/MVP.md) | 현재 버전 명세 |
| `docs/implementation/ARCHITECTURE.md` | [ARCHITECTURE](assets/templates/ARCHITECTURE.md) | 기본 |
| `docs/implementation/CONVENTIONS.md` | [CONVENTIONS](assets/templates/CONVENTIONS.md) | 기본 |
| `docs/implementation/DATA_MODEL.md` | [DATA_MODEL](assets/templates/DATA_MODEL.md) | 영속 데이터 저장이 필요할 때 |
| `docs/implementation/openapi.yaml` | [OpenAPI](assets/templates/openapi.yaml) | HTTP API가 있을 때 |
| `docs/decisions/INDEX.md` | [ADR index](assets/templates/ADR_INDEX.md) | 첫 ADR이 생길 때 |
| `docs/decisions/NNNN-title.md` | [ADR](assets/templates/ADR.md) | 중요한 결정이 있을 때 |

템플릿의 중괄호 안내문은 실제 내용으로 바꾸고 작성자 주석은 제거한다. 선택 항목과 무관한 표·섹션은 삭제한다. 기본 문서라도 기록할 내용이 없으면 짧게 적용 대상 없음을 적고 일반 지식으로 채우지 않는다. 빈 디렉터리·빈 선택 문서를 만들지 않는다.

## 전달

작성·변경한 문서, 현재 MVP 버전·상태, 미정과 해당 작업에 미치는 영향, 확인한 검증 결과를 간단히 보고한다. 명세의 `Ready`는 구현 시작 가능 상태이며 구현 완료를 뜻하지 않는다. 토큰 절감이나 구현 정확도를 측정 없이 보장하지 않는다. 기획 대화에서 구현으로 넘어갈 때는 현재 명세만 전달하는 새 대화를 권장한다. 같은 대화에서 이미 읽은 전체 PRD의 내용은 읽기 지침만으로 제거할 수 없다.
