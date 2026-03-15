# Attributes Index Reference

Complete index mapping for player positions and attributes used in this project.

Two attribute groups are defined:
- **`properties_main`** — visible in-game attributes (index 0–68)
- **`properties_hidden`** — hidden personality attributes (index 0–7)

---

## Positions (Index 0–14)

| Index | 中文 | English |
|-------|------|---------|
| 0 | 门将 | Goalkeeper |
| 1 | 未知 | Unknown |
| 2 | 左后卫 | Left Back |
| 3 | 中后卫 | Center Back |
| 4 | 右后卫 | Right Back |
| 5 | 防守型中场 | Defensive Midfielder |
| 6 | 左翼卫 | Left Wing Back |
| 7 | 右翼卫 | Right Wing Back |
| 8 | 左前卫 | Left Midfielder |
| 9 | 中前卫 | Central Midfielder |
| 10 | 右前卫 | Right Midfielder |
| 11 | 左路攻击前卫 | Left Attacking Midfielder |
| 12 | 中路攻击前卫 | Central Attacking Midfielder |
| 13 | 右路攻击前卫 | Right Attacking Midfielder |
| 14 | 前锋 | Forward |

---

## Technical Attributes — Field Players (Index 15–25)

| Index | 中文 | English |
|-------|------|---------|
| 15 | 传中 | Crossing |
| 16 | 盘带 | Dribbling |
| 17 | 射门 | Finishing |
| 18 | 头球 | Heading |
| 19 | 远射 | Long Shots |
| 20 | 盯人 | Marking |
| 21 | 无球跑动 | Off the Ball |
| 22 | 传球 | Passing |
| 23 | 点球 | Penalties |
| 24 | 抢断 | Tackling |
| 25 | 视野 | Vision |

---

## Technical Attributes — Goalkeepers (Index 26–36)

| Index | 中文 | English |
|-------|------|---------|
| 26 | 手控球 | Handling |
| 27 | 制空范围 | Aerial Reach |
| 28 | 拦截传中 | Command of Area |
| 29 | 指挥防守 | Communication |
| 30 | 大脚开球 | Kicking |
| 31 | 手抛球 | Throwing |
| 32 | 预判 | Anticipation |
| 33 | 决断 | Decisions |
| 34 | 一对一 | One on Ones |
| 35 | 防守站位 | Positioning |
| 36 | 反应 | Reflexes |

---

## Additional Technical Attributes (Index 37–50)

| Index | 中文 | English |
|-------|------|---------|
| 37 | 停球 | First Touch |
| 38 | 技术 | Technique |
| 39 | 左脚 | Left Foot |
| 40 | 右脚 | Right Foot |
| 41 | 才华 | Flair |
| 42 | 角球 | Corners |
| 43 | 团队合作 | Teamwork |
| 44 | 工作投入 | Work Rate |
| 45 | 界外球 | Long Throws |
| 46 | 意外性 | Creativity |
| 47 | 出击(倾向) | Rushing Out (Tendency) |
| 48 | 击球(倾向) | Punching (Tendency) |
| 49 | 爆发力 | Acceleration |
| 50 | 任意球 | Free Kick Taking |

---

## Physical Attributes (Index 51–57)

| Index | 中文 | English |
|-------|------|---------|
| 51 | 强壮 | Strength |
| 52 | 耐力 | Stamina |
| 53 | 速度 | Pace |
| 54 | 弹跳 | Jumping Reach |
| 55 | 领导力 | Leadership |
| 56 | 灵活 | Agility |
| 57 | 平衡 | Balance |

---

## Mental Attributes (Index 58–68)

| Index | 中文 | English |
|-------|------|---------|
| 58 | 勇敢 | Bravery |
| 59 | 稳定 | Composure |
| 60 | 侵略性 | Aggression |
| 61 | 灵活 | Agility |
| 62 | 大赛发挥 | Important Matches |
| 63 | 受伤倾向 | Injury Proneness |
| 64 | 多面性 | Versatility |
| 65 | 体质 | Natural Fitness |
| 66 | 意志力 | Determination |
| 67 | 镇定 | Composure |
| 68 | 专注 | Concentration |

---

## Summary: `properties_main` Index Ranges

| Category | Index Range | Count |
|----------|-------------|-------|
| Positions | 0–14 | 15 |
| Field Player Technical | 15–25 | 11 |
| Goalkeeper Technical | 26–36 | 11 |
| Additional Technical | 37–50 | 14 |
| Physical | 51–57 | 7 |
| Mental | 58–68 | 11 |
| **Total** | **0–68** | **69** |

---

# `properties_hidden` — Hidden Attributes (Index 0–7)

Personality attributes not visible in-game, used for scouting and player development assessment.

| Index | 中文 | English |
|-------|------|---------|
| 0 | 适应性 | Adaptability |
| 1 | 雄心 | Ambition |
| 2 | 争论 | Controversy |
| 3 | 忠诚 | Loyalty |
| 4 | 抗压能力 | Pressure |
| 5 | 职业 | Professionalism |
| 6 | 体育道德 | Sportsmanship |
| 7 | 情绪控制 | Temperament |