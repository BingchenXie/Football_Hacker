# Football Hacker

足球模拟游戏（Football Manager 类）球员数据库的 JSON 快照，用于数据分析与对比。

## 数据文件

| 文件 | 快照时间 | 球员数量 | 文件大小 |
|------|----------|----------|----------|
| `persons_2401.json` | 2024 年 1 月 | 478,948 | ~677 MB |
| `persons_2402.json` | 2024 年 2 月 | 480,911 | ~680 MB |

两个文件结构完全相同，记录同一批球员在不同时间点的状态。

## 数据结构

顶层字段：

```json
{
  "count": 478948,
  "items": [ ... ]
}
```

每条球员记录（`items` 中的一个对象）包含以下字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | 球员唯一 ID |
| `first_name` | string | 名 |
| `last_name` | string | 姓 |
| `full_name` | string | 全名（通常为空，使用 first+last） |
| `birth_date` | string (YYYY-MM-DD) | 出生日期 |
| `height` | int | 身高（cm） |
| `weight` | int | 体重（kg） |
| `nation_id` | int | 国籍 ID |
| `club_id` | int | 所属俱乐部 ID（0 表示无俱乐部） |
| `play_number` | int | 球衣号码（255 为未分配） |
| `ability_now` | int | 当前能力值 |
| `ability_potential` | int | 潜力上限值 |
| `salary` | int | 薪资 |
| `transfer_value` | int | 转会市场估值 |
| `entry_date` | string | 进入数据库日期 |
| `contract_start_date` | string | 合同开始日期 |
| `contract_end_date` | string | 合同结束日期 |
| `properties_main` | int[~50] | 主要属性数组（技术、身体、心理等各项数值） |
| `properties_hidden` | int[8] | 隐藏属性数组（如职业态度、适应能力等） |

## 典型用途

- 比较 2401 与 2402 快照，追踪球员能力值/合同/俱乐部的变化
- 根据 `ability_now`、`ability_potential` 筛选潜力新星
- 统计各俱乐部/国家的球员分布
- 分析身体数据（身高、体重）与能力值的关联