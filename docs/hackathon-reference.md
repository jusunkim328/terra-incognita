# Hackathon Reference — Elasticsearch Agent Builder Hackathon

> **공식 페이지**: [elasticsearch.devpost.com](https://elasticsearch.devpost.com/)

---

## 일정

| 항목 | 날짜/시간 (EST) | 날짜/시간 (KST) |
|------|-----------------|-----------------|
| 등록/제출 시작 | 2026-01-22 2:00 PM EST | 2026-01-23 (금) 04:00 AM KST |
| **제출 마감** | **2026-02-27 1:00 PM EST** | **2026-02-28 (토) 03:00 AM KST** |
| 심사 기간 | 2026-02-27 ~ 2026-03-14 | 2026-02-28 ~ 2026-03-15 |
| 수상자 발표 | 2026-03-16 2:00 PM EST | 2026-03-17 (화) 04:00 AM KST |

> **주의**: 마감은 한국 시간 기준 **2월 28일 새벽 3시**. 여유를 두고 2월 27일 자정(KST) 이전 제출 권장.

---

## 심사 기준

| 기준 | 비중 | 상세 |
|------|------|------|
| **Technical Execution** (기술 실행력) | 30% | 코드 품질, 기능 구현 완성도, Agent Builder/Elasticsearch 활용 깊이 |
| **Potential Impact & Wow Factor** (임팩트/혁신성) | 30% | 문제의 중요성, 솔루션의 효율성, 참신함 |
| **Demo Quality** (데모 품질) | 30% | 문제 정의 명확성, 프레젠테이션 효과, 아키텍처 문서화 |
| **Social Media Presence** (소셜 공유) | 10% | @elastic_devs / @elastic 태그된 소셜 미디어 포스트 확인 |

### 심사 프로세스

1. **Stage 1 (Pass/Fail)**: 테마 적합성 + 필수 API/SDK 사용 여부 확인
2. **Stage 2 (점수 평가)**: 위 4개 기준으로 가중 평가
3. **타이브레이커**: 동점 시 첫 번째 해당 기준에서 높은 점수 순; 그래도 동점이면 심사위원 투표

---

## 제출 요건

### 필수 항목

| 항목 | 요건 | 상세 |
|------|------|------|
| **설명문** | ~300단어 (Devpost 기준 ~400단어) | 해결하는 문제, 사용한 기능, 좋았던 점/도전 2~3가지 |
| **데모 영상** | 3분 이내 | 작동하는 프로젝트 시연, YouTube/Vimeo/Facebook Video/Youku 업로드 |
| **코드 저장소** | 공개 (Public) | OSI 승인 오픈소스 라이선스, 저장소 About 섹션에서 라이선스 감지 가능해야 함 |
| **Agent Builder 사용** | 필수 | Elastic Agent Builder 커스텀 에이전트 + 도구 |
| **ES 데이터** | 필수 | Elasticsearch에 데이터 저장 |
| **작동 데모/크레덴셜** | 필수 | 심사위원이 테스트 가능한 환경 (단, 심사위원이 반드시 테스트하지는 않음) |

### 선택 항목

| 항목 | 혜택 |
|------|------|
| **소셜 미디어 포스트** | 10% 가산점, @elastic_devs 또는 @elastic 태그 필수 |

---

## 기술 요건

### 필수 기술

- **Elasticsearch**: 데이터 저장 및 검색
- **Agent Builder**: 멀티스텝 AI 에이전트 구축 프레임워크
- **Elastic Workflows / Search / ES|QL 중 하나 이상**: Agent Builder의 도구로 활용

### 선택 기술 (활용 시 가산)

- ELSER / semantic_text (시맨틱 검색)
- RRF 하이브리드 검색
- Index Alias
- Cloud Scheduler (Workflows)
- MCP 커넥터
- Kibana 대시보드

---

## 데이터 규칙

- **허용**: 오픈소스 데이터, 합성(synthetic) 데이터
- **금지**: 기밀 데이터, 개인정보(PII), 저작권 침해 콘텐츠
- **AI 사용 시**: 제3자 AI 도구가 개인정보/데이터 보호법을 준수해야 함

---

## 라이선스 요건

- **OSI 승인 오픈소스 라이선스** 필수 (예: MIT, Apache 2.0, GPL 등)
- 저장소 최상위에 LICENSE 파일이 있어야 함
- 저장소 About 섹션에서 라이선스가 **감지 가능**(detectable)해야 함
- 제3자 오픈소스 사용 시 해당 라이선스 조건 준수

---

## 상금

| 순위 | 상금 | 부가 혜택 |
|------|------|-----------|
| 1위 | $10,000 | 블로그 피처 + 소셜 인정 |
| 2위 | $5,000 | 블로그 피처 + 소셜 인정 |
| 3위 | $3,000 | 블로그 피처 + 소셜 인정 |
| Creative (Wow Factor) x4 | 각 $500 | 블로그 피처 + 소셜 인정 |

- 프로젝트당 하나의 상금만 수상 가능
- 세금/수수료는 수상자 부담
- 수상 후 60일 이내 지급

---

## Terra Incognita 기술 충족 현황

| 요건 | 상태 | 구현 내용 |
|------|------|-----------|
| **Elasticsearch 데이터 저장** | 충족 | 5개 인덱스 (ti-papers, ti-gaps, ti-bridges, ti-exploration-log, ti-discovery-cards) |
| **Agent Builder 에이전트** | 충족 | `terra-incognita` 에이전트 (8 Rules, 5단계 워크플로우) |
| **Agent Builder 커스텀 도구** | 충족 | ES\|QL 도구 4개 + MCP 도구 1개 |
| **Elastic Workflows / Search / ES\|QL** | 충족 | ES\|QL 4개 도구 (ti-survey, ti-detect, ti-bridge, ti-validate) |
| **OSI 라이선스** | 충족 | MIT License (LICENSE 파일 존재) |
| **오픈소스/합성 데이터** | 충족 | arXiv 오픈 API + 합성 시드 데이터 |
| **공개 저장소** | 미완 | 제출 전 GitHub public 전환 필요 |
| **~300단어 설명** | 미완 | Devpost 제출 시 작성 |
| **3분 데모 영상** | 미완 | 제작 필요 |
| **소셜 미디어 포스트** | 미완 | 게시 필요 |
| **작동 데모** | 충족 | Elastic Cloud Hosted + Kibana Agent Builder UI |

### 추가 활용 ES 기능 (가산 기대)

| ES 기능 | 활용처 |
|---------|--------|
| `semantic_text` + ELSER v2 | SURVEY, BRIDGE — 제로 설정 시맨틱 임베딩 |
| RRF 하이브리드 검색 | SURVEY, BRIDGE — BM25 + 벡터 융합으로 예상치 못한 연결 발견 |
| ES\|QL 파라미터 쿼리 | DETECT, VALIDATE — 교차 도메인 밀도 분석, 참신성 검증 |
| Index Alias | Time-Travel Discovery — 백테스트 분리 (before_2020 vs all) |
| Cloud Scheduler (Workflows) | Gap Watch + Daily Discovery — 자동 모니터링 |
| MCP 커넥터 | ti-save-results — Agent Builder에서 외부 쓰기 |
| Kibana 대시보드 | 6개 패널 시각화 (Research Landscape, IVI Top 10, Heatmap 등) |

---

## 제출 전 최종 체크리스트

- [ ] GitHub repo **public** 전환
- [x] LICENSE 파일 (MIT) — 저장소 최상위에 존재
- [x] `.env`는 `.env.example`만 커밋 (실제 크레덴셜 제외)
- [x] 시드 데이터가 합성(synthetic)임을 README에 명시
- [ ] ~300단어 Devpost 설명
- [ ] 3분 데모 영상 제작 및 업로드 (YouTube/Vimeo)
- [ ] 소셜 미디어 포스트
- [ ] 소셜 미디어 실제 게시 + URL 확보
- [ ] 심사위원용 작동 데모 환경 확인
- [ ] Devpost 제출 폼 작성 및 제출
