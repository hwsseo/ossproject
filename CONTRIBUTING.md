# 🌱 마으미 기여 가이드 (CONTRIBUTING)

마으미에 관심 가져 주셔서 고마워요! 이 문서는 **어떻게 작업하고, 어떻게 PR을 올리고, 어떻게 리뷰하는지**를 정리합니다.
처음이라면 Wiki의 [Getting Started](https://github.com/hwsseo/ossproject/wiki/Getting-Started)부터 읽어 주세요.

## 1. 작업 흐름 — GitHub Flow

```
main ──●─────────────●──────────●──▶  (항상 배포 가능한 상태)
        \           /          /
         ●──●──●──●  (feat/…)  /
                 \           /
                  ●──●──●──●  (docs/…)
```

1. **Issue 확인/생성** — 할 일을 이슈로 먼저 남깁니다.
2. **브랜치 생성** — `main`에서 기능 단위로 브랜치를 만듭니다.
3. **커밋** — Conventional Commits 규칙으로 작게 자주 커밋합니다.
4. **PR 생성** — PR 템플릿을 채우고 관련 이슈를 연결합니다 (`Closes #번호`).
5. **코드 리뷰** — `[MUST]` 항목이 모두 해결되어야 머지할 수 있습니다.
6. **Squash & Merge** 후 브랜치 삭제.

## 2. 브랜치 이름 규칙

| 접두어 | 용도 | 예시 |
|---|---|---|
| `feat/` | 새 기능 | `feat/crisis-keyword-detector` |
| `fix/` | 버그 수정 | `fix/chat-fallback-timeout` |
| `docs/` | 문서 | `docs/oss-license-coc` |
| `refactor/` | 동작 변화 없는 구조 개선 | `refactor/report-service` |
| `test/` | 테스트 추가 | `test/emotion-classifier` |
| `chore/` | 빌드·설정·잡무 | `chore/update-workflows` |

## 3. 커밋 메시지 — Conventional Commits

```
<type>(<scope>): <요약 (50자 이내, 명령형)>

<본문: 무엇을, 왜 바꿨는지>

<꼬리말: Closes #12>
```

- **type**: `feat` `fix` `docs` `style` `refactor` `test` `chore` `ci`
- **예시**: `feat(safety): 위기 표현 키워드 감지 함수 추가`
- 호환성을 깨는 변경은 `feat!:` 또는 꼬리말에 `BREAKING CHANGE:`를 적습니다.

## 4. 코드 리뷰 가이드

리뷰 코멘트는 **태그로 중요도**를 표시합니다.

| 태그 | 의미 | 머지 전 처리 |
|---|---|---|
| `[MUST]` | 버그·보안·요구사항 위반. 반드시 수정 | ✅ 필수 |
| `[SHOULD]` | 가독성·구조·테스트 보완 권장 | 가능하면 반영, 아니면 이유 답글 |
| `[NIT]` | 사소한 취향 (오타, 공백 등) | 선택 |
| `[QUESTION]` | 의도 확인 질문 | 답글 필수 |

**리뷰어 체크리스트**
- [ ] PR 설명과 실제 변경 내용이 일치하는가?
- [ ] 위기 감지·개인정보 관련 변경이면 테스트가 있는가?
- [ ] API 키 등 비밀값이 코드에 들어가지 않았는가?
- [ ] 이름이 의도를 잘 드러내는가?

**리뷰 매너**: 사람이 아닌 코드에 대해 말하고, "왜"와 "대안"을 함께 적습니다. → [행동 강령](CODE_OF_CONDUCT.md)

## 5. 로컬 개발 & 테스트

```bash
git clone https://github.com/hwsseo/ossproject.git
cd ossproject
python -m pip install pytest
python -m pytest -q
```

자세한 구조는 Wiki [Development Guide](https://github.com/hwsseo/ossproject/wiki/Development-Guide), 막히면 [Troubleshooting](https://github.com/hwsseo/ossproject/wiki/Troubleshooting)을 참고하세요.

## 6. 라이선스
기여한 코드는 이 저장소의 [MIT License](LICENSE)로 배포되는 것에 동의한 것으로 봅니다.
