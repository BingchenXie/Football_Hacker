"""
训练引援推荐模型。

数据：18个俱乐部，FM24→FM26 的球员变化
- 同时在24和26的球员 → 原始阵容（input）
- 仅在26的球员     → 引援（label）

模型：Squad VAE
- PlayerEncoder: 将单个球员特征映射到 embedding
- SquadEncoder:  用注意力机制聚合阵容
- VAE:           生成引援画像，随机性来自 latent space 采样
"""

import json
import sys
import random
from pathlib import Path
from datetime import date

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.optim import Adam
from torch.optim.lr_scheduler import CosineAnnealingLR

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# ── 常量 ──────────────────────────────────────────────────────────

FEATURE_DIM = 82   # 69 pm + 8 ph + 5 scalars
EMBED_DIM   = 64
LATENT_DIM  = 32
EPOCHS      = 2000
LR          = 3e-4
KL_WEIGHT   = 0.05
AUG_REPEATS = 8    # 每个俱乐部每 epoch 的数据增强次数
MIN_SQUAD   = 8    # 增强时最少保留的球员数
SAVE_PATH   = ROOT / "data" / "recommender.pt"


# ── 特征提取 ──────────────────────────────────────────────────────

REF_DATE = date(2024, 7, 1)


def calc_age(birth_date_str: str) -> float:
    try:
        bd = date.fromisoformat(str(birth_date_str))
        return (REF_DATE - bd).days / 365.25
    except Exception:
        return 25.0


def player_to_vec(p: dict) -> np.ndarray:
    """将球员 dict 转换为 82 维特征向量。"""
    pm = list(p.get("properties_main") or [])
    ph = list(p.get("properties_hidden") or [])
    pm = pm[:69] + [0] * max(0, 69 - len(pm))
    ph = ph[:8]  + [0] * max(0, 8  - len(ph))

    ability_now = float(p.get("ability_now") or 0)
    ability_pot = float(p.get("ability_potential") or 0)
    height      = float(p.get("height") or 175)
    weight      = float(p.get("weight") or 75)
    age         = calc_age(p.get("birth_date") or "")

    vec = pm + ph + [ability_now, ability_pot, height, weight, age]
    return np.array(vec, dtype=np.float32)


# ── 数据准备 ──────────────────────────────────────────────────────

def load_data():
    """返回 list of (original_vecs, signing_vecs)，每个俱乐部一条。"""
    with open(ROOT / "data" / "selected_clubs.json") as f:
        selected = set(json.load(f))

    def load_persons(year):
        with open(ROOT / "data" / f"persons_{year}.json") as f:
            return {p["id"]: p for p in json.load(f)["items"]}

    p24 = load_persons("24")
    p26 = load_persons("26")

    ids24 = {pid for pid, p in p24.items() if p["club_id"] in selected}
    ids26 = {pid for pid, p in p26.items() if p["club_id"] in selected}

    both   = ids24 & ids26
    only26 = ids26 - ids24

    # 按俱乐部分组
    from collections import defaultdict
    club_original = defaultdict(list)
    club_signings = defaultdict(list)

    for pid in both:
        club_original[p24[pid]["club_id"]].append(player_to_vec(p24[pid]))
    for pid in only26:
        club_signings[p26[pid]["club_id"]].append(player_to_vec(p26[pid]))

    dataset = []
    for cid in selected:
        orig = club_original.get(cid, [])
        sign = club_signings.get(cid, [])
        if len(orig) >= 3 and len(sign) >= 1:
            dataset.append((
                np.stack(orig),   # (N_orig, 82)
                np.stack(sign),   # (N_sign, 82)
            ))
    print(f"加载完成：{len(dataset)} 个俱乐部，原始球员总计 "
          f"{sum(len(o) for o,_ in dataset)}，引援总计 {sum(len(s) for _,s in dataset)}")
    return dataset


def normalize_dataset(dataset):
    """用全体球员数据计算均值/标准差，返回 (mean, std)。"""
    all_vecs = np.concatenate([o for o, _ in dataset] + [s for _, s in dataset], axis=0)
    mean = all_vecs.mean(axis=0)
    std  = all_vecs.std(axis=0) + 1e-6
    return mean.astype(np.float32), std.astype(np.float32)


def augment(orig_vecs: np.ndarray, n_repeats: int, min_squad: int):
    """随机采样原始阵容子集，返回多个增强样本。"""
    results = []
    n = len(orig_vecs)
    for _ in range(n_repeats):
        k = random.randint(min_squad, n)
        idx = np.random.choice(n, k, replace=False)
        results.append(orig_vecs[idx])
    return results


# ── 模型定义 ──────────────────────────────────────────────────────

class PlayerEncoder(nn.Module):
    """单个球员特征 → embedding。"""
    def __init__(self, in_dim=FEATURE_DIM, out_dim=EMBED_DIM):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_dim, 128), nn.LayerNorm(128), nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(128, out_dim), nn.LayerNorm(out_dim),
        )

    def forward(self, x):
        return self.net(x)   # (..., out_dim)


class SquadVAE(nn.Module):
    """
    Squad VAE：
      encode(squad) → (μ, logvar)
      decode(z)     → player_profile (FEATURE_DIM)
    """
    def __init__(self):
        super().__init__()
        self.player_enc = PlayerEncoder()

        # 注意力聚合
        self.attn = nn.MultiheadAttention(EMBED_DIM, num_heads=4,
                                          dropout=0.1, batch_first=True)
        self.attn_norm = nn.LayerNorm(EMBED_DIM)

        # VAE 编码器
        self.fc_mu     = nn.Linear(EMBED_DIM, LATENT_DIM)
        self.fc_logvar = nn.Linear(EMBED_DIM, LATENT_DIM)

        # VAE 解码器
        self.decoder = nn.Sequential(
            nn.Linear(LATENT_DIM, 64), nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(64, 128), nn.ReLU(),
            nn.Linear(128, FEATURE_DIM),
        )

    def encode_squad(self, squad_tensor):
        """
        squad_tensor: (B, N, FEATURE_DIM)
        返回: (μ, logvar), 各 (B, LATENT_DIM)
        """
        emb = self.player_enc(squad_tensor)           # (B, N, EMBED_DIM)
        attn_out, _ = self.attn(emb, emb, emb)
        attn_out = self.attn_norm(attn_out + emb)     # residual
        squad_repr = attn_out.mean(dim=1)             # (B, EMBED_DIM)
        return self.fc_mu(squad_repr), self.fc_logvar(squad_repr)

    def reparameterize(self, mu, logvar):
        std = torch.exp(0.5 * logvar)
        return mu + std * torch.randn_like(std)

    def decode(self, z):
        return self.decoder(z)   # (B, FEATURE_DIM)

    def forward(self, squad_tensor):
        mu, logvar = self.encode_squad(squad_tensor)
        z = self.reparameterize(mu, logvar)
        return self.decode(z), mu, logvar


# ── 损失函数 ──────────────────────────────────────────────────────

def vae_loss(generated, signings_tensor, mu, logvar):
    """
    generated:       (B, FEATURE_DIM)
    signings_tensor: (B, M, FEATURE_DIM)  — M 个真实引援
    返回标量损失。
    """
    gen_n  = F.normalize(generated, dim=-1)           # (B, F)
    sign_n = F.normalize(signings_tensor, dim=-1)     # (B, M, F)

    # cos(gen, each signing): (B, M)
    sims = torch.bmm(gen_n.unsqueeze(1), sign_n.transpose(1, 2)).squeeze(1)
    max_sim = sims.max(dim=1).values                  # (B,)

    sim_loss = -max_sim.mean()

    kl_loss = -0.5 * (1 + logvar - mu.pow(2) - logvar.exp()).mean()

    return sim_loss + KL_WEIGHT * kl_loss, sim_loss.item(), kl_loss.item()


# ── 训练 ──────────────────────────────────────────────────────────

def collate_batch(samples, mean_t, std_t, device):
    """
    samples: list of (orig_vecs, sign_vecs)
    返回 (squad_padded_tensor, signings_padded_tensor)
    squad 按最大阵容长度 pad；signings 同理。
    """
    orig_list  = [torch.tensor((o - mean_t) / std_t) for o, _ in samples]
    sign_list  = [torch.tensor((s - mean_t) / std_t) for _, s in samples]

    # pad squad
    max_o = max(o.shape[0] for o in orig_list)
    max_s = max(s.shape[0] for s in sign_list)

    B = len(samples)
    squad_t = torch.zeros(B, max_o, FEATURE_DIM)
    sign_t  = torch.zeros(B, max_s, FEATURE_DIM)

    for i, (o, s) in enumerate(zip(orig_list, sign_list)):
        squad_t[i, :o.shape[0]] = o
        sign_t [i, :s.shape[0]] = s

    return squad_t.to(device), sign_t.to(device)


def train():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"使用设备: {device}")

    dataset = load_data()
    mean_np, std_np = normalize_dataset(dataset)
    mean_t = mean_np  # will be saved; used in collate as numpy
    std_t  = std_np

    model = SquadVAE().to(device)
    optimizer = Adam(model.parameters(), lr=LR, weight_decay=1e-4)
    scheduler = CosineAnnealingLR(optimizer, T_max=EPOCHS, eta_min=1e-5)

    best_loss = float("inf")
    best_state = None

    for epoch in range(1, EPOCHS + 1):
        model.train()
        # 每个 epoch 对每个俱乐部做数据增强，组成本轮 mini-dataset
        aug_samples = []
        for orig, sign in dataset:
            squads = augment(orig, AUG_REPEATS, MIN_SQUAD)
            for sq in squads:
                aug_samples.append((sq, sign))

        random.shuffle(aug_samples)

        # 全批次一次（数据量小，直接全量）
        squad_t, sign_t = collate_batch(aug_samples, mean_t, std_t, device)

        generated, mu, logvar = model(squad_t)
        loss, sim_l, kl_l = vae_loss(generated, sign_t, mu, logvar)

        optimizer.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        scheduler.step()

        if loss.item() < best_loss:
            best_loss = loss.item()
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}

        if epoch % 100 == 0:
            print(f"Epoch {epoch:4d} | loss={loss.item():.4f} "
                  f"sim={sim_l:.4f} kl={kl_l:.4f}")

    # 保存
    torch.save({
        "model_state": best_state,
        "mean": mean_np,
        "std":  std_np,
        "feature_dim": FEATURE_DIM,
        "embed_dim":   EMBED_DIM,
        "latent_dim":  LATENT_DIM,
    }, SAVE_PATH)
    print(f"\n模型已保存至 {SAVE_PATH}（最优 loss={best_loss:.4f}）")


if __name__ == "__main__":
    torch.manual_seed(42)
    np.random.seed(42)
    random.seed(42)
    train()
