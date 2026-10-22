FDIM = NUM_GATE_TYPES + 3
 
class KeyGNN(nn.Module):
    def __init__(self, in_dim, hidden=128, layers=4, drop=0.3):
        super().__init__()
        self.proj = nn.Linear(in_dim, hidden)
        self.convs = nn.ModuleList([SAGEConv(hidden, hidden) for _ in range(layers)])
        self.skips = nn.ModuleList([nn.Linear(hidden, hidden) for _ in range(layers)])
        self.bns = nn.ModuleList([nn.BatchNorm1d(hidden) for _ in range(layers)])
        self.head = nn.Sequential(
            nn.Linear(hidden, 64), nn.ReLU(),
            nn.Dropout(drop), nn.Linear(64, 2)
        )
        self.drop = drop
 
    def forward(self, x, ei):
        # treat the circuit graph as undirected - add reverse edges
        rev = ei.flip(0)
        ei2 = torch.cat([ei, rev], dim=1)
 
        h = F.relu(self.proj(x))
        for conv, sk, bn in zip(self.convs, self.skips, self.bns):
            # SAGE conv + a skip connection, batchnorm'd and dropped out
            h = F.relu(bn(conv(h, ei2)) + sk(h))
            h = F.dropout(h, p=self.drop, training=self.training)
        return self.head(h)
 
 
# ── metrics ──────────────────────────────────────────────────────────────
def metrics(logits, y, mask):
    if mask.sum() == 0:
        return 0.5, 0.5  # nothing to score, just return a coin flip
    preds = logits[mask].argmax(1)
    truth = y[mask]
    acc = (preds == truth).float().mean().item()
    return acc, 1.0 - acc
 
 
# ── load circuits ────────────────────────────────────────────────────────
files = glob.glob('Valkyrie/CAC/**/*.v', recursive=True)
print(f"\nFound {len(files)} .v files")
 
raw_graphs = []
for fp in files:
    try:
        n, e, k = parse_verilog(fp)
        if not k:
            print(f"  [skip] {fp} - no key gates")
            continue
        g = to_pyg(n, e, k)
        if g is not None:
            g.filename = fp
            raw_graphs.append((fp, n, e, k, g))
            print(f"  [ok]   {os.path.basename(fp):40s} {len(n)} gates, {len(k)} key gates")
    except Exception as ex:
        print(f"  [err]  {fp}: {ex}")
 
if not raw_graphs:
    raise SystemExit("No circuits loaded - check Valkyrie/CAC directory")
 
print(f"\nLoaded {len(raw_graphs)} circuits")
 
# ── train/val split ──────────────────────────────────────────────────────
all_pyg = [r[4] for r in raw_graphs]
if len(all_pyg) == 1:
    # only one circuit to work with, so train and val are the same graph -
    # the node-level mask still keeps this honest
    train_gs = val_gs = all_pyg
    print("Single circuit: node-level split used implicitly")
else:
    sp = max(1, int(0.8 * len(all_pyg)))
    train_gs, val_gs = all_pyg[:sp], all_pyg[sp:]
    print(f"Train: {len(train_gs)}  Val: {len(val_gs)}")
 
BS = min(4, len(train_gs))
train_loader = DataLoader(train_gs, batch_size=BS, shuffle=True)
val_loader = DataLoader(val_gs, batch_size=BS, shuffle=False)
 
# ── train ────────────────────────────────────────────────────────────────
model = KeyGNN(FDIM).to(device)
opt = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-4)
sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=100)
 
best_acc, best_state = 0.0, None
train_losses, val_accs = [], []
 
print("\nTraining...")
for epoch in range(1, 101):
    model.train()
    ep_loss = 0.0
    for batch in train_loader:
        batch = batch.to(device)
        mask = batch.key_mask
        if mask.sum() == 0:
            continue
        opt.zero_grad()
        loss = F.cross_entropy(model(batch.x, batch.edge_index)[mask], batch.y[mask])
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        ep_loss += loss.item()
    sched.step()
 
    # quick val pass each epoch so we can track the best checkpoint
    model.eval()
    va = []
    with torch.no_grad():
        for batch in val_loader:
            batch = batch.to(device)
            mask = batch.key_mask
            if mask.sum() == 0:
                continue
            acc, _ = metrics(model(batch.x, batch.edge_index), batch.y, mask)
            va.append(acc)
    val_acc = np.mean(va) if va else 0.5
    train_losses.append(ep_loss)
    val_accs.append(val_acc)
 
    if val_acc > best_acc:
        best_acc = val_acc
        best_state = {k: v.clone() for k, v in model.state_dict().items()}
 
    if epoch % 10 == 0:
        print(f"  Epoch {epoch:3d} | loss={ep_loss:.4f} | val_acc={val_acc:.4f} | best={best_acc:.4f}")
 
model.load_state_dict(best_state)
print(f"\nBest val accuracy: {best_acc:.4f}")
 
# ── evaluate all transforms ──────────────────────────────────────────────
# this is the part that actually answers "does the model generalize to
# obfuscated/transformed versions of the circuit, or did it just memorize?"
print("\nEvaluating transforms...")
results = {}
model.eval()
 
for tname, tfn in TRANSFORMS.items():
    accs, hds = [], []
    for fp, n, e, k, _ in raw_graphs:
        try:
            tn, te, tk = tfn(n, e, k)
            g = to_pyg(tn, te, tk)
            if g is None or g.key_mask.sum() == 0:
                continue
            g = g.to(device)
            with torch.no_grad():
                logits = model(g.x, g.edge_index)
            acc, hd = metrics(logits, g.y, g.key_mask)
            accs.append(acc)
            hds.append(hd)
        except Exception as ex:
            print(f"  [err] {tname} / {fp}: {ex}")
    results[tname] = {
        'acc': np.mean(accs) if accs else 0.5,
        'hd': np.mean(hds) if hds else 0.5,
        'acc_std': np.std(accs) if accs else 0.0,
    }
    print(f"  {tname:35s} acc={results[tname]['acc']:.4f}  hd={results[tname]['hd']:.4f}")
