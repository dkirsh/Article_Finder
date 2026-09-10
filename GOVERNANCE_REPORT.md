# Governance Report — Article_Finder_v3_2_3
*tier: full · findings: 7*

| sev | check | path | detail |
|---|---|---|---|
| RED | G4 | /Users/davidusa/REPOS/Article_Finder_v3_2_3/install.sh | destructive op in tracked script: `rm -rf` (RULE 0 — quarantine, don't delete; allowlist in governance.json g4_allow if legitimate) |
| AMBER | G1 | /Users/davidusa/REPOS/Article_Finder_v3_2_3/CLAUDE.md | no CLAUDE.md (autofixable: govern fix scaffolds one with the root pointer) |
| AMBER | G2 | /Users/davidusa/REPOS/Article_Finder_v3_2_3/TASKS.md | no TASKS.md (autofixable: govern fix scaffolds template) |
| AMBER | G6 | /Users/davidusa/REPOS/Article_Finder_v3_2_3/docs/CLAUDE_CODE_HANDOFF_v2.7.0.md | 1 bare repo-relative path line(s) in a handoff/prompt doc (Complete Verified File Paths rule) |
| AMBER | G11 | /Users/davidusa/REPOS/Article_Finder_v3_2_3/governance.json | no canonical: true/false declared (near-duplicate-clone hazard) |
| INFO | G8 | /Users/davidusa/REPOS/Article_Finder_v3_2_3 | no quarantine/ or _to_delete/ — RULE 0 has nowhere to put things here |
| INFO | G10 | /Users/davidusa/REPOS/Article_Finder_v3_2_3 | >=5 decision entries in docs but no DECISIONS_LOG file |

*govern v1.1 — no violations detected means NOT-DETECTED-BY-V1-CHECKS, never compliance. Reports are detectors, not attestations (design §9; llm_cheating_corpus drivers 1-6).*