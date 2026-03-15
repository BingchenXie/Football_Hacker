"""
引援推荐器（推理模块）。

使用方法：
    from recommender import Recommender
    rec = Recommender()
    result = rec.recommend(current_players, all_players, exclude_ids=set())
    # result: dict，包含推荐球员信息和匹配分数
"""

import json
from pathlib import Path
from datetime import date
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

ROOT      = Path(__file__).parent.parent
DATA_DIR  = ROOT / "data"
MODEL_PATH = DATA_DIR / "recommender.pt"

FEATURE_DIM = 82
EMBED_DIM   = 64
LATENT_DIM  = 32

REF_DATE = date(2024, 7, 1)


# ── 特征提取（与训练脚本保持一致）────────────────────────────────

def _calc_age(birth_date_str: str) -> float:
    try:
        bd = date.fromisoformat(str(birth_date_str))
        return (REF_DATE - bd).days / 365.25
    except Exception:
        return 25.0


def player_from_db_row(row: dict) -> dict:
    """将 SQLite 查询行（pm_0..pm_68, ph_0..ph_7）转换为 player_to_vec 期望的格式。"""
    return {
        "id":                row.get("id"),
        "first_name":        row.get("first_name", ""),
        "last_name":         row.get("last_name", ""),
        "birth_date":        row.get("birth_date", ""),
        "height":            row.get("height"),
        "weight":            row.get("weight"),
        "ability_now":       row.get("ability_now"),
        "ability_potential": row.get("ability_potential"),
        "properties_main":   [row.get(f"pm_{i}") or 0 for i in range(69)],
        "properties_hidden": [row.get(f"ph_{i}") or 0 for i in range(8)],
    }


def player_to_vec(p: dict) -> np.ndarray:
    pm = list(p.get("properties_main") or [])
    ph = list(p.get("properties_hidden") or [])
    pm = pm[:69] + [0] * max(0, 69 - len(pm))
    ph = ph[:8]  + [0] * max(0, 8  - len(ph))

    ability_now = float(p.get("ability_now") or 0)
    ability_pot = float(p.get("ability_potential") or 0)
    height      = float(p.get("height") or 175)
    weight      = float(p.get("weight") or 75)
    age         = _calc_age(p.get("birth_date") or "")

    vec = pm + ph + [ability_now, ability_pot, height, weight, age]
    return np.array(vec, dtype=np.float32)


# ── 模型定义（与训练脚本保持一致）────────────────────────────────

class PlayerEncoder(nn.Module):
    def __init__(self, in_dim=FEATURE_DIM, out_dim=EMBED_DIM):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_dim, 128), nn.LayerNorm(128), nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(128, out_dim), nn.LayerNorm(out_dim),
        )

    def forward(self, x):
        return self.net(x)


class SquadVAE(nn.Module):
    def __init__(self):
        super().__init__()
        self.player_enc = PlayerEncoder()
        self.attn      = nn.MultiheadAttention(EMBED_DIM, num_heads=4,
                                               dropout=0.1, batch_first=True)
        self.attn_norm = nn.LayerNorm(EMBED_DIM)
        self.fc_mu     = nn.Linear(EMBED_DIM, LATENT_DIM)
        self.fc_logvar = nn.Linear(EMBED_DIM, LATENT_DIM)
        self.decoder   = nn.Sequential(
            nn.Linear(LATENT_DIM, 64),  nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(64, 128), nn.ReLU(),
            nn.Linear(128, FEATURE_DIM),
        )

    def encode_squad(self, squad_tensor):
        emb = self.player_enc(squad_tensor)
        attn_out, _ = self.attn(emb, emb, emb)
        squad_repr = self.attn_norm(attn_out + emb).mean(dim=1)
        return self.fc_mu(squad_repr), self.fc_logvar(squad_repr)

    def reparameterize(self, mu, logvar, temperature: float = 1.0):
        std = torch.exp(0.5 * logvar) * temperature
        return mu + std * torch.randn_like(std)

    def decode(self, z):
        return self.decoder(z)

    def forward(self, squad_tensor, temperature: float = 1.0):
        mu, logvar = self.encode_squad(squad_tensor)
        z = self.reparameterize(mu, logvar, temperature)
        return self.decode(z), mu, logvar


# ── 属性名称映射（来自 data_loader）─────────────────────────────

POSITIONS = {
    0:"门将", 1:"未知", 2:"左后卫", 3:"中后卫", 4:"右后卫",
    5:"防守中场", 6:"左前卫", 7:"中前卫", 8:"右前卫",
    9:"左路攻前", 10:"中路攻前", 11:"右路攻前", 12:"前锋",
    13:"左翼卫", 14:"右翼卫",
}

TECH_ATTRS = {
    42:"角球", 15:"传中", 16:"盘带", 17:"射门", 37:"停球",
    50:"任意球", 18:"头球", 19:"远射", 20:"盯人", 22:"传球",
    24:"抢断", 38:"技术",
}
MENTAL_ATTRS = {
    60:"侵略性", 32:"预判", 67:"镇定", 33:"决断", 41:"才华",
    21:"无球跑动", 35:"防守站位", 43:"团队合作", 25:"视野",
}
PHYSICAL_ATTRS = {
    49:"爆发力", 56:"灵活", 57:"平衡", 54:"弹跳",
    53:"速度", 52:"耐力", 51:"强壮",
}


def _describe_profile(vec_norm: np.ndarray, mean: np.ndarray, std: np.ndarray) -> dict:
    """
    将归一化的生成向量反归一化，提取人类可读的属性画像。
    """
    raw = vec_norm * std + mean
    pm  = raw[:69]
    ph  = raw[69:77]
    ability_now = float(raw[77])
    ability_pot = float(raw[78])
    height      = float(raw[79])
    age         = float(raw[81])

    # 主要位置（评分最高的 3 个）
    pos_scores = [(POSITIONS[i], float(pm[i])) for i in range(15) if i in POSITIONS]
    pos_scores.sort(key=lambda x: -x[1])
    top_positions = [(n, round(v)) for n, v in pos_scores[:3] if v >= 5]

    # 突出属性（各类别取最高的 2 个）
    def top_attrs(attr_dict, n=2):
        vals = [(name, float(pm[idx])) for idx, name in attr_dict.items()]
        vals.sort(key=lambda x: -x[1])
        return [(n, round(v)) for n, v in vals[:n] if v > 0]

    return {
        "ability_now":  round(ability_now),
        "ability_pot":  round(ability_pot),
        "height_cm":    round(height),
        "age_approx":   round(age),
        "positions":    top_positions,
        "tech":         top_attrs(TECH_ATTRS),
        "mental":       top_attrs(MENTAL_ATTRS),
        "physical":     top_attrs(PHYSICAL_ATTRS),
    }


# ── 推荐器主类 ────────────────────────────────────────────────────

class Recommender:
    """
    使用训练好的 Squad VAE 进行引援推荐。

    主要接口：
        recommend(current_players, candidate_players, exclude_ids, temperature)
          → dict: {player, score, profile_desc}
    """

    def __init__(self, model_path: Path = MODEL_PATH):
        ckpt = torch.load(model_path, map_location="cpu", weights_only=False)
        self._mean: np.ndarray = ckpt["mean"]
        self._std:  np.ndarray = ckpt["std"]

        self._model = SquadVAE()
        self._model.load_state_dict(ckpt["model_state"])
        self._model.eval()

    def _normalize(self, vecs: np.ndarray) -> np.ndarray:
        return (vecs - self._mean) / self._std

    def _squad_tensor(self, players: list[dict]) -> torch.Tensor:
        vecs = np.stack([player_to_vec(p) for p in players])  # (N, 82)
        norm = self._normalize(vecs)
        return torch.tensor(norm, dtype=torch.float32).unsqueeze(0)  # (1, N, 82)

    @torch.no_grad()
    def recommend(
        self,
        current_players: list[dict],
        candidate_players: list[dict],
        exclude_ids: Optional[set] = None,
        temperature: float = 1.0,
        top_k: int = 1,
    ) -> list[dict]:
        """
        参数
        ----
        current_players:   当前阵容（原始球员），每个元素是球员 dict
        candidate_players: 候选引援数据库（全体球员或子集）
        exclude_ids:       已在阵容中的球员 ID 集合（排除）
        temperature:       采样温度（>1 更随机，<1 更保守）
        top_k:             返回 top_k 个推荐结果

        返回
        ----
        list of dict，每个包含：
            player       - 原始球员 dict
            score        - 与生成画像的余弦相似度（0-1）
            profile_desc - 生成画像的人类可读描述
        """
        if not current_players:
            return []

        exclude = exclude_ids or set()

        # 1. 生成引援画像
        squad_t = self._squad_tensor(current_players)
        self._model.train()   # 保留 dropout 的随机性
        generated, mu, logvar = self._model(squad_t, temperature=temperature)
        self._model.eval()

        gen_vec = generated[0].numpy()  # (82,)  归一化空间
        profile_desc = _describe_profile(gen_vec, self._mean, self._std)

        # 2. 在候选库中检索最相似球员
        filtered = [p for p in candidate_players
                    if p.get("id") not in exclude and p.get("id") is not None]
        if not filtered:
            return []

        cand_vecs  = np.stack([player_to_vec(p) for p in filtered])
        cand_norm  = self._normalize(cand_vecs)

        gen_n   = gen_vec / (np.linalg.norm(gen_vec) + 1e-8)
        cand_nn = cand_norm / (np.linalg.norm(cand_norm, axis=1, keepdims=True) + 1e-8)
        scores  = cand_nn @ gen_n  # (M,)

        top_idx = np.argsort(scores)[::-1][:top_k]
        results = []
        for idx in top_idx:
            results.append({
                "player":       filtered[idx],
                "score":        float(scores[idx]),
                "profile_desc": profile_desc,
            })
        return results

    @torch.no_grad()
    def recommend_multi(
        self,
        current_players: list[dict],
        candidate_players: list[dict],
        exclude_ids: Optional[set] = None,
        n_runs: int = 5,
        temperature: float = 1.2,
    ) -> list[dict]:
        """
        多次运行推荐，每次采样不同的 z，返回去重后的推荐列表。
        适合主程序调用多次以获得多样化结果。
        """
        seen_ids = set(exclude_ids or [])
        results  = []
        for _ in range(n_runs):
            recs = self.recommend(
                current_players, candidate_players,
                exclude_ids=seen_ids,
                temperature=temperature,
                top_k=1,
            )
            if recs:
                rec = recs[0]
                pid = rec["player"].get("id")
                if pid not in seen_ids:
                    seen_ids.add(pid)
                    results.append(rec)
        return results


# ── 简单命令行测试 ────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    with open(DATA_DIR / "selected_clubs.json") as f:
        selected = set(json.load(f))

    with open(DATA_DIR / "persons_24.json") as f:
        p24_all = json.load(f)["items"]
    with open(DATA_DIR / "persons_26.json") as f:
        p26_all = json.load(f)["items"]

    # 取第一个俱乐部测试
    club_id  = list(selected)[0]
    original = [p for p in p24_all if p["club_id"] == club_id]
    # 候选库：26赛季非该俱乐部的球员（模拟转会市场）
    candidates = [p for p in p26_all if p["club_id"] != club_id]

    rec = Recommender()
    results = rec.recommend_multi(
        current_players=original,
        candidate_players=candidates,
        n_runs=5,
        temperature=1.2,
    )

    print(f"\n俱乐部 {club_id} 的引援推荐（共 {len(results)} 条）：")
    for i, r in enumerate(results, 1):
        p    = r["player"]
        desc = r["profile_desc"]
        name = f"{p.get('first_name','')} {p.get('last_name','')}".strip()
        pos  = " / ".join(f"{n}({v})" for n, v in desc["positions"])
        print(f"\n#{i}  {name}  |  相似度={r['score']:.3f}")
        print(f"    能力={desc['ability_now']}  潜力={desc['ability_pot']}  "
              f"年龄≈{desc['age_approx']}  身高≈{desc['height_cm']}cm")
        print(f"    位置：{pos}")
        print(f"    技术：{desc['tech']}")
        print(f"    心理：{desc['mental']}")
        print(f"    身体：{desc['physical']}")
